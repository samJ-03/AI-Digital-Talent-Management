"""T14真实私有MinIO/隔离MySQL集成；仅合成文件，不执行模型调用。"""
from io import BytesIO
from uuid import uuid4
import pytest
from sqlalchemy import select,delete,func
from tests.integration.test_identity import identity,login
from tests.integration.test_files import PNG
from app.core.settings import Settings
from app.core.models import IdempotencyRecord
from app.files.service import FileService
from app.files.storage import S3FileStore
from app.files.models import StoredFile
from app.identity.models import Role
from app.ingestion.models import ImportBatch,ImportItem
from app.jobs.models import Job
from app.runtime.models import BackgroundJob,OutboxEvent

@pytest.fixture
def imports(identity):
    client,engine,uid,password,ids,*_=identity
    runtime=client.app.state.identity
    store=S3FileStore.from_settings(Settings.load(),bucket='talent-test-import-'+uid)
    client.app.state.file_service=FileService(store,runtime.uow_factory)
    with runtime.uow_factory() as uow:
        role=uow.session.get(Role,ids['hr_role']);role.permission_codes=sorted(set(role.permission_codes)|{'import.read','import.write','job.read'});uow.commit()
    yield identity,store
    with runtime.uow_factory() as uow:
        batches=list(uow.session.scalars(select(ImportBatch.id).where(ImportBatch.created_by.in_([ids['hr'],ids['other']]))))
        item_ids=list(uow.session.scalars(select(ImportItem.id).where(ImportItem.batch_id.in_(batches))))
        jobs=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id.in_(item_ids))))
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_type=='background_job',OutboxEvent.aggregate_id.in_(jobs)))
        uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(jobs)))
        uow.session.execute(delete(ImportItem).where(ImportItem.batch_id.in_(batches)))
        uow.session.execute(delete(ImportBatch).where(ImportBatch.id.in_(batches)))
        uow.session.execute(delete(StoredFile).where(StoredFile.bucket==store.bucket))
        uow.session.execute(delete(Job).where(Job.title.like(uid+'%')))
        uow.session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.actor_scope.in_(['hr:'+str(ids['hr']),'hr:'+str(ids['other'])])))
        uow.commit()
    if store.client.bucket_exists(store.bucket):
        for obj in store.client.list_objects(store.bucket,recursive=True): store.client.remove_object(store.bucket,obj.object_name)
        store.client.remove_bucket(store.bucket)
    store.close()

def post(imports,headers=None,key=None,files=None,data=None):
    identity,_=imports;client=identity[0]
    headers=headers or login(identity,'hr')
    return client.post('/api/v1/imports',headers={**headers,'Idempotency-Key':key or uuid4().hex},files=files or [('files',('resume.png',PNG,'image/png'))],data=data or {})

def test_partial_failure_keeps_valid_items(imports):
    response=post(imports,files=[('files',('good.png',PNG,'image/png')),('files',('bad.pdf',b'MZ-bad','application/pdf'))])
    assert response.status_code==202,response.text
    batch=response.json()['data'];client=imports[0][0]
    detail=client.get('/api/v1/imports/'+batch['id']).json()['data']
    assert batch['file_count']==2 and detail['status']=='partial_failed'
    assert [row['status'] for row in detail['items']]==['queued','failed']
    assert detail['items'][0]['file_id'] is not None and detail['items'][1]['file_id'] is None
    assert detail['items'][1]['error_code']=='INVALID_FILE_FORMAT'

def test_idempotent_batch_and_changed_payload_conflict(imports):
    headers=login(imports[0],'hr');key=uuid4().hex
    a=post(imports,headers,key);b=post(imports,headers,key)
    assert a.status_code==b.status_code==202 and a.json()['data']['id']==b.json()['data']['id']
    changed=post(imports,headers,key,files=[('files',('other.png',PNG,'image/png'))])
    assert changed.status_code==409
    with imports[0][0].app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(StoredFile).where(StoredFile.bucket==imports[1].bucket))==1

def test_library_import_no_invitation_and_only_reference_task(imports):
    response=post(imports);assert response.status_code==202,response.text
    detail=imports[0][0].get('/api/v1/imports/'+response.json()['data']['id']).json()['data']
    item=detail['items'][0]
    with imports[0][0].app.state.identity.uow_factory() as uow:
        task=uow.session.get(BackgroundJob,int(item['task_id']))
        assert task.job_type=='resume.parse' and task.input_refs=={'file_id':int(item['file_id']),'import_item_id':int(item['id'])}
        assert uow.session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type=='invite.scan'))==0

def test_file_count_limit_before_storage(imports):
    response=post(imports,files=[('files',('cv.png',PNG,'image/png')) for _ in range(51)])
    assert response.status_code==413
    with imports[0][0].app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(StoredFile).where(StoredFile.bucket==imports[1].bucket))==0

def test_per_file_byte_limit_records_failure(imports):
    imports[0][0].app.state.file_service.max_file_bytes=10
    response=post(imports);assert response.status_code==202,response.text
    detail=imports[0][0].get('/api/v1/imports/'+response.json()['data']['id']).json()['data']
    assert detail['items'][0]['error_code']=='FILE_SIZE_LIMIT' and detail['items'][0]['file_id'] is None

def test_other_department_and_admin_denied(imports):
    response=post(imports);assert response.status_code==202,response.text
    batch=response.json()['data']['id'];client=imports[0][0]
    login(imports[0],'other');assert client.get('/api/v1/imports/'+batch).status_code==404
    headers=login(imports[0],'admin');assert post(imports,headers).status_code==403

def test_missing_read_permission_rejects_before_upload(imports):
    client=imports[0][0]
    with client.app.state.identity.uow_factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role']);role.permission_codes=[p for p in role.permission_codes if p!='import.read'];uow.commit()
    response=post(imports);assert response.status_code==403
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(StoredFile).where(StoredFile.bucket==imports[1].bucket))==0

def test_list_batches_is_department_scoped(imports):
    own=post(imports);assert own.status_code==202,own.text
    client=imports[0][0];login(imports[0],'other')
    data=client.get('/api/v1/imports?page=1&page_size=10').json()['data']
    assert own.json()['data']['id'] not in [x['id'] for x in data['items']]

def test_retry_reuses_active_task_and_requeues_failed_once(imports):
    headers=login(imports[0],'hr');response=post(imports,headers);assert response.status_code==202,response.text
    client=imports[0][0];detail=client.get('/api/v1/imports/'+response.json()['data']['id']).json()['data'];item=detail['items'][0]
    url='/api/v1/import-items/'+item['id']+'/retry'
    first=client.post(url,json={'reason':'再次尝试'},headers=headers)
    assert first.status_code==202 and first.json()['data']['task_id']==item['task_id']
    with client.app.state.identity.uow_factory() as uow:
        task=uow.session.get(BackgroundJob,int(item['task_id']));task.state='failed';task.error_code='HANDLER_NOT_REGISTERED';uow.commit()
    failed=client.get('/api/v1/imports/'+response.json()['data']['id']).json()['data']
    assert failed['items'][0]['status']=='failed'
    a=client.post(url,json={'reason':'重试解析'},headers=headers);b=client.post(url,json={'reason':'重试解析'},headers=headers)
    assert a.status_code==b.status_code==202 and a.json()['data']['task_id']==b.json()['data']['task_id']
    assert a.json()['data']['task_id']!=item['task_id']

def test_upload_failure_requires_replacement(imports):
    headers=login(imports[0],'hr');response=post(imports,headers,files=[('files',('bad.pdf',b'MZ','application/pdf'))]);assert response.status_code==202,response.text
    client=imports[0][0];item=client.get('/api/v1/imports/'+response.json()['data']['id']).json()['data']['items'][0]
    retry=client.post('/api/v1/import-items/'+item['id']+'/retry',json={'reason':'重试'},headers=headers)
    assert retry.status_code==422 and retry.json()['code']=='FILE_REPLACEMENT_REQUIRED'

def actor_and_service(imports):
    from app.identity.models import User
    from app.identity.views import resolve_user
    from app.ingestion.service import ImportService
    runtime=imports[0][0].app.state.identity
    with runtime.uow_factory() as uow: actor=resolve_user(uow.session,uow.session.get(User,imports[0][4]['hr']))
    return actor,ImportService(imports[0][0].app.state.file_service,runtime.uow_factory)

def test_concurrent_create_keeps_one_batch_and_task(imports,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.files.service import UploadDescriptor
    actor,service=actor_and_service(imports);barrier=Barrier(2);original=service.files.stage;key=uuid4().hex
    def staged(actor,upload):
        result=original(actor,upload);barrier.wait(timeout=10);return result
    monkeypatch.setattr(service.files,'stage',staged)
    def create_one(_): return service.create(actor,[UploadDescriptor('cv.png','image/png',len(PNG),BytesIO(PNG))],None,key)
    with ThreadPoolExecutor(max_workers=2) as pool: values=list(pool.map(create_one,range(2)))
    assert values[0].id==values[1].id
    detail=service.get_batch(actor,int(values[0].id));assert len(detail.items)==1
    with service.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id==int(detail.items[0].id)))==1

def test_concurrent_retry_creates_one_new_task(imports):
    from concurrent.futures import ThreadPoolExecutor
    response=post(imports);assert response.status_code==202,response.text
    actor,service=actor_and_service(imports)
    item=service.get_batch(actor,int(response.json()['data']['id'])).items[0]
    with service.uow_factory() as uow:
        task=uow.session.get(BackgroundJob,int(item.task_id));task.state='failed';uow.commit()
    with ThreadPoolExecutor(max_workers=2) as pool: values=list(pool.map(lambda _:service.retry_item(actor,int(item.id),'并发重试'),range(2)))
    assert values[0].task_id==values[1].task_id and values[0].task_id!=item.task_id
    with service.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id==int(item.id)))==2

def test_retry_does_not_wait_for_worker_task_lock(imports):
    from concurrent.futures import ThreadPoolExecutor
    response=post(imports);assert response.status_code==202,response.text
    actor,service=actor_and_service(imports);item=service.get_batch(actor,int(response.json()['data']['id'])).items[0]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.uow_factory() as uow:
            uow.session.scalar(select(BackgroundJob).where(BackgroundJob.id==int(item.task_id)).with_for_update())
            future=pool.submit(service.retry_item,actor,int(item.id),'读取现有任务')
            try: result=future.result(timeout=3)
            finally: uow.rollback()
    assert result.task_id==item.task_id

def test_batch_audit_failure_rolls_back_queue_and_attachment(imports,monkeypatch):
    from app.ingestion.service import ImportService
    from app.core.errors import DomainError
    def fail(*args,**kwargs): raise DomainError('SYNTHETIC_ABORT',409,'synthetic abort')
    monkeypatch.setattr(ImportService,'audit',fail)
    response=post(imports);assert response.status_code==409
    with imports[0][0].app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(ImportBatch).where(ImportBatch.created_by==imports[0][4]['hr']))==0
        rows=list(uow.session.scalars(select(StoredFile).where(StoredFile.bucket==imports[1].bucket)))
        assert len(rows)==1 and rows[0].status=='staged'
        assert uow.session.scalar(select(func.count()).select_from(ImportItem).where(ImportItem.file_id==rows[0].id))==0

def test_cross_department_job_rejected_before_storage(imports):
    ids=imports[0][4]
    with imports[0][0].app.state.identity.uow_factory() as uow:
        job=Job(title=imports[0][2]+'-other',department_id=ids['d2'],owner_hr_id=ids['other'],headcount=1,status='draft',auto_invite_enabled=False)
        uow.session.add(job);uow.session.flush();job_id=job.id;uow.commit()
    response=post(imports,data={'job_id':str(job_id)});assert response.status_code==404
    with imports[0][0].app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(StoredFile).where(StoredFile.bucket==imports[1].bucket))==0

def test_expired_or_purged_key_cannot_create_duplicate_batch(imports):
    headers=login(imports[0],'hr');key=uuid4().hex
    response=post(imports,headers,key);assert response.status_code==202,response.text
    with imports[0][0].app.state.identity.uow_factory() as uow:
        uow.session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.request_key==key));uow.commit()
    replay=post(imports,headers,key)
    assert replay.status_code==409 and replay.json()['code']=='IMPORT_KEY_EXPIRED'

def test_internal_error_detail_is_not_exposed(imports):
    response=post(imports);assert response.status_code==202,response.text
    actor,service=actor_and_service(imports);item=service.get_batch(actor,int(response.json()['data']['id'])).items[0]
    with service.uow_factory() as uow:
        row=uow.session.get(ImportItem,int(item.id));row.status='failed';row.error_code='RAW_SQL_DIAGNOSTIC';row.error_detail_safe='synthetic-private-stack';uow.commit()
    detail=imports[0][0].get('/api/v1/imports/'+response.json()['data']['id'])
    assert 'synthetic-private-stack' not in detail.text and 'RAW_SQL_DIAGNOSTIC' not in detail.text

def test_nonfailed_item_cannot_have_null_file(imports):
    from sqlalchemy.exc import DBAPIError
    response=post(imports);assert response.status_code==202,response.text
    with imports[0][0].app.state.identity.uow_factory() as uow:
        uow.session.add(ImportItem(batch_id=int(response.json()['data']['id']),source_order=99,file_id=None,status='queued'))
        with pytest.raises(DBAPIError) as error: uow.session.flush()
        assert error.value.orig.args[0]==3819
        uow.rollback()

def migration_config(imports):
    from pathlib import Path
    from alembic.config import Config
    from sqlalchemy.engine import make_url
    url=imports[0][0].app.state.identity.settings.database_url.get_secret_value()
    assert make_url(url).database=='talent_test'
    cfg=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'));cfg.set_main_option('sqlalchemy.url',url.replace('%','%%'))
    return cfg

def test_failed_upload_blocks_lossy_downgrade_without_partial_ddl(imports):
    from alembic import command
    from sqlalchemy import inspect
    response=post(imports,files=[('files',('bad.pdf',b'MZ','application/pdf'))]);assert response.status_code==202,response.text
    with pytest.raises(RuntimeError,match='Cannot downgrade'): command.downgrade(migration_config(imports),'0006_comment_semantics')
    inspector=inspect(imports[0][1])
    assert next(c for c in inspector.get_columns('import_items') if c['name']=='file_id')['nullable'] is True
    assert any(c['name']=='ck_import_items_failed_without_file' for c in inspector.get_check_constraints('import_items'))

def test_nullable_migration_roundtrip_preserves_unsigned_fk_and_comment(imports):
    from alembic import command
    from sqlalchemy import inspect
    cfg=migration_config(imports);engine=imports[0][1]
    command.downgrade(cfg,'0006_comment_semantics')
    assert next(c for c in inspect(engine).get_columns('import_items') if c['name']=='file_id')['nullable'] is False
    command.upgrade(cfg,'head')
    column=next(c for c in inspect(engine).get_columns('import_items') if c['name']=='file_id')
    assert column['nullable'] is True and column['type'].unsigned is True and 'failed' in column['comment']
    assert any(f['constrained_columns']==['file_id'] and f['referred_table']=='stored_files' for f in inspect(engine).get_foreign_keys('import_items'))

def test_removed_company_scope_hides_owned_out_of_department_batch(imports):
    ids=imports[0][4];client=imports[0][0]
    with client.app.state.identity.uow_factory() as uow:
        job=Job(title=imports[0][2]+'-scope-change',department_id=ids['d2'],owner_hr_id=ids['other'],headcount=1,status='draft',auto_invite_enabled=False)
        uow.session.add(job);uow.session.flush();job_id=job.id
        role=uow.session.get(Role,ids['hr_role']);role.data_scope='company';uow.commit()
    response=post(imports,data={'job_id':str(job_id)});assert response.status_code==202,response.text
    batch_id=response.json()['data']['id']
    with client.app.state.identity.uow_factory() as uow:
        role=uow.session.get(Role,ids['hr_role']);role.data_scope='department';uow.commit()
    login(imports[0],'hr')
    assert client.get('/api/v1/imports/'+batch_id).status_code==404
    listing=client.get('/api/v1/imports').json()['data']
    assert batch_id not in [row['id'] for row in listing['items']]
