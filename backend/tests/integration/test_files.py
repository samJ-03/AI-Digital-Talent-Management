"""平台开发工具：验证files的正常与失败场景；测试数据仅用于隔离环境。"""
import base64
import io
import os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import httpx
import pytest
from alembic import command as migration
from alembic.config import Config
from pypdf import PdfWriter
from sqlalchemy import create_engine,select,delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.access import ActorContext
from app.core.clock import FrozenClock
from app.core.errors import DomainError
from app.core.settings import Settings
from app.core.uow import SqlAlchemyUow
from app.identity.models import User,Department
from app.audit.models import AuditLog
from app.files.models import StoredFile
from app.files.storage import S3FileStore
from app.files.service import FileService,UploadDescriptor
from app.knowledge.models import KnowledgeDocument

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')

@pytest.fixture
def files():
    url=os.environ['TALENT_TEST_DATABASE_URL']
    assert make_url(url).database=='talent_test'
    cfg=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'));cfg.set_main_option('sqlalchemy.url',url.replace('%','%%'));migration.upgrade(cfg,'head')
    engine=create_engine(url,pool_pre_ping=True)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    uows=lambda:SqlAlchemyUow(factory)
    uid=uuid4().hex[:20]
    with uows() as uow:
        a=Department(name=uid+'-a');b=Department(name=uid+'-b')
        uow.session.add_all([a,b]);uow.session.flush()
        user=User(login_name=uid,password_hash='synthetic-not-login',department_id=a.id)
        uow.session.add(user);uow.session.flush()
        ids=(user.id,a.id,b.id);uow.commit()
    store=S3FileStore.from_settings(Settings.load(),bucket='talent-test-'+uid)
    clock=FrozenClock(datetime.now(timezone.utc))
    service=FileService(store,uows,clock)
    actor=ActorContext('hr',user_id=ids[0],department_ids=frozenset({ids[1]}),permissions=frozenset({'import.write','knowledge.read','talent.read'}))
    yield service,store,uows,clock,actor,ids
    with uows() as uow:
        file_ids=list(uow.session.scalars(select(StoredFile.id).where(StoredFile.bucket==store.bucket)))
        uow.session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.file_id.in_(file_ids)))
        uow.session.execute(delete(StoredFile).where(StoredFile.id.in_(file_ids)))
        uow.session.execute(delete(AuditLog).where(AuditLog.actor_user_id==ids[0]))
        uow.session.execute(delete(User).where(User.id==ids[0]))
        uow.session.execute(delete(Department).where(Department.id.in_(ids[1:])))
        uow.commit()
    assert store.bucket=='talent-test-'+uid
    if store.client.bucket_exists(store.bucket):
        for obj in store.client.list_objects(store.bucket,recursive=True): store.client.remove_object(store.bucket,obj.object_name)
        store.client.remove_bucket(store.bucket)
    store.close()
    engine.dispose()

def upload(data=PNG,name='resume.png',mime='image/png',size=None):
    return UploadDescriptor(name,mime,len(data) if size is None else size,io.BytesIO(data))

def test_extension_mime_mismatch_rejected(files):
    service,store,uows,clock,actor,ids=files
    for body in [upload(b'MZ-executable','resume.pdf','application/pdf'),upload(PNG,'resume.pdf','application/pdf'),upload(PNG,'resume.png','application/pdf')]:
        with pytest.raises(DomainError) as error: service.stage(actor,body)
        assert error.value.http_status==422

def test_private_bucket_no_anonymous_get(files):
    service,store,uows,clock,actor,ids=files
    view=service.stage(actor,upload())
    with uows() as uow: row=uow.session.get(StoredFile,int(view.id));key=row.object_key
    endpoint=Settings.load().minio_endpoint
    if endpoint.startswith('minio:'): endpoint='minio:9000'
    response=httpx.get('http://'+endpoint+'/'+store.bucket+'/'+key,timeout=5,trust_env=False)
    assert response.status_code in {401,403}
    grant=service.authorized_download(actor,int(view.id))
    try: assert grant.stream.read()==PNG
    finally: grant.stream.close()

def test_path_traversal_filename_safe(files):
    service,store,uows,clock,actor,ids=files
    view=service.stage(actor,upload(name='../other/../../resume.png'))
    with uows() as uow:
        row=uow.session.get(StoredFile,int(view.id))
        assert row.object_key.startswith('staged/')
        assert '..' not in row.object_key and 'resume' not in row.object_key
        assert row.original_name=='../other/../../resume.png'
    assert view.sha256 and view.size==len(PNG)

def test_cross_department_exam_file_denied_even_to_original_uploader(files):
    service,store,uows,clock,actor,ids=files
    view=service.stage(actor,upload())
    with uows() as uow:
        row=uow.session.get(StoredFile,int(view.id));row.status='ready'
        uow.session.add(KnowledgeDocument(logical_key=str(uuid4()),version_no=1,file_id=row.id,title='private rubric',category='rubric',scope='department',department_id=ids[2]))
        uow.commit()
    with pytest.raises(DomainError) as error: service.authorized_download(actor,int(view.id))
    assert error.value.http_status==404
    other=ActorContext('hr',user_id=ids[0],department_ids=frozenset({ids[2]}),permissions=frozenset({'knowledge.read'}))
    grant=service.authorized_download(other,int(view.id))
    grant.stream.close()

def test_size_checked_from_actual_stream_not_client_claim(files):
    service,store,uows,clock,actor,ids=files
    with pytest.raises(DomainError) as error: service.stage(actor,upload(size=20*1024*1024+1))
    assert error.value.http_status==413
    with pytest.raises(DomainError) as error: service.stage(actor,upload(PNG+b'x'*(20*1024*1024),size=1))
    assert error.value.http_status==413

def test_pdf_page_limit(files):
    service,store,uows,clock,actor,ids=files
    writer=PdfWriter()
    for _ in range(101): writer.add_blank_page(width=72,height=72)
    out=io.BytesIO();writer.write(out)
    with pytest.raises(DomainError) as error: service.stage(actor,upload(out.getvalue(),'resume.pdf','application/pdf'))
    assert error.value.http_status==413

def test_orphan_cleanup_preserves_referenced_and_recent_files(files):
    service,store,uows,clock,actor,ids=files
    old=service.stage(actor,upload(name='old.png'))
    linked=service.stage(actor,upload(name='linked.png'))
    recent=service.stage(actor,upload(name='recent.png'))
    with uows() as uow:
        for file_id in [old.id,linked.id]: uow.session.get(StoredFile,int(file_id)).created_at=clock.now().replace(tzinfo=None)-timedelta(days=2)
        uow.session.add(KnowledgeDocument(logical_key=str(uuid4()),version_no=1,file_id=int(linked.id),title='keep',category='reference',scope='company'))
        uow.commit()
    assert service.cleanup_orphans(clock.now()-timedelta(days=1))==1
    with uows() as uow:
        assert uow.session.get(StoredFile,int(old.id)).status=='deleted'
        assert uow.session.get(StoredFile,int(linked.id)).status=='staged'
        assert uow.session.get(StoredFile,int(recent.id)).status=='staged'
    grant=service.authorized_download(actor,int(recent.id));grant.stream.close()

def test_admin_and_candidate_cannot_stage_hr_files(files):
    service,store,uows,clock,actor,ids=files
    for denied in [ActorContext('admin',user_id=ids[0],permissions=frozenset({'user.manage'})),ActorContext('candidate',candidate_id=1,attempt_id=1,permissions=frozenset({'exam.answer'}))]:
        with pytest.raises(DomainError) as error: service.stage(denied,upload())
        assert error.value.http_status==403


@pytest.mark.parametrize('kind',['pdf','docx'])
def test_valid_document_roundtrip(files,kind):
    service,store,uows,clock,actor,ids=files
    out=io.BytesIO()
    if kind=='pdf':
        writer=PdfWriter();writer.add_blank_page(width=72,height=72);writer.write(out)
        mime='application/pdf'
    else:
        from docx import Document
        document=Document();document.add_paragraph('Synthetic resume');document.save(out)
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    raw=out.getvalue()
    view=service.stage(actor,upload(raw,'synthetic.'+kind,mime))
    grant=service.authorized_download(actor,int(view.id))
    try: assert grant.stream.read()==raw
    finally: grant.stream.close()

def test_docx_macro_and_archive_entry_bomb_rejected(files):
    import zipfile
    service,store,uows,clock,actor,ids=files
    for many in (False,True):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as package:
            package.writestr('[Content_Types].xml','<Types/>')
            package.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
            if many:
                for index in range(5000): package.writestr('word/file'+str(index),'')
            else: package.writestr('word/vbaProject.bin',b'synthetic marker')
        with pytest.raises(DomainError) as error: service.stage(actor,upload(out.getvalue(),'resume.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
        assert error.value.http_status==(413 if many else 422)

def test_untracked_old_object_reconciled_after_grace(files):
    service,store,uows,clock,actor,ids=files
    key='staged/'+uuid4().hex
    store.put(key,io.BytesIO(PNG),'image/png')
    clock.instant+=timedelta(days=2)
    assert service.cleanup_orphans(clock.now()-timedelta(days=1))==1
    with pytest.raises(DomainError) as error: store.get(key)
    assert error.value.http_status==404

def test_storage_public_policy_is_refused(files,monkeypatch):
    service,store,uows,clock,actor,ids=files
    store.ensure_private_bucket()
    monkeypatch.setattr(store.client,'get_bucket_policy',lambda bucket:'{"Statement": [{"Principal": "*"}]}')
    with pytest.raises(DomainError) as error: service.stage(actor,upload())
    assert error.value.code=='UNSAFE_BUCKET_POLICY'

def test_proxy_download_contract_and_staff_role_guard(files):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.identity.router import require_staff
    service,store,uows,clock,actor,ids=files
    view=service.stage(actor,upload(name='../合成简历.png'))
    settings=Settings(environment='test',database_url=os.environ['TALENT_TEST_DATABASE_URL'],redis_url=os.environ['TALENT_REDIS_URL'],monitor_token='test-monitor')
    app=create_app(settings);app.state.file_service=service
    app.dependency_overrides[require_staff]=lambda:actor
    with TestClient(app) as client:
        response=client.get('/api/v1/files/'+view.id+'/download')
        assert response.status_code==200 and response.content==PNG
        assert response.headers['Content-Type']=='image/png'
        assert response.headers['Cache-Control']=='private, no-store'
        assert response.headers['Content-Disposition'].startswith("attachment; filename*=UTF-8''")
        assert '..' not in response.headers['Content-Disposition']
        app.dependency_overrides[require_staff]=lambda:ActorContext('admin',user_id=ids[0],permissions=frozenset({'user.manage'}))
        assert client.get('/api/v1/files/'+view.id+'/download').status_code==403
        app.dependency_overrides.clear()
        client.cookies.set('talent_exam','fake-candidate-session')
        assert client.get('/api/v1/files/'+view.id+'/download').status_code==401
