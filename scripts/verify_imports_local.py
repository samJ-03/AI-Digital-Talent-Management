"""在本地开发库以合成文件验收T14受理，不执行AI或发送邮件。"""
from pathlib import Path
import sys,json,base64
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select
from sqlalchemy.engine import make_url
from app.core.settings import Settings
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user
from app.files.service import FileService,UploadDescriptor
from app.files.storage import S3FileStore
from app.ingestion.service import ImportService
from app.runtime.models import BackgroundJob
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
def main():
    """只写入明确标为synthetic的本项目批次，不读取后台账号密码。"""
    settings=Settings.load()
    if sys.argv[1:]!=['--allow-dev-write'] or settings.environment!='dev' or make_url(settings.database_url.get_secret_value()).database!='talent_dev':
        raise RuntimeError('Explicit local talent_dev write confirmation required')
    with make_uow() as uow:
        user=uow.session.scalar(select(User).where(User.login_name=='hr-tech'))
        if user is None: raise RuntimeError('Local HR bootstrap required')
        actor=resolve_user(uow.session,user)
    store=S3FileStore.from_settings(settings)
    try:
        files=FileService(store,make_uow,max_file_bytes=settings.max_file_bytes,max_pages=settings.max_file_pages)
        service=ImportService(files,make_uow)
        def uploads():
            return [UploadDescriptor('synthetic-t14-good.png','image/png',len(PNG),BytesIO(PNG)),UploadDescriptor('synthetic-t14-bad.pdf','application/pdf',2,BytesIO(b'MZ'))]
        a=service.create(actor,uploads(),None,'synthetic-t14-local-v1')
        b=service.create(actor,uploads(),None,'synthetic-t14-local-v1')
        detail=service.get_batch(actor,int(a.id))
        good,bad=detail.items
        checks={'same_batch_replay':a.id==b.id,'two_items':len(detail.items)==2,'partial_failure':detail.status=='partial_failed',
            'valid_file_and_task':good.file_id is not None and good.task_id is not None,
            'invalid_file_explicit':bad.file_id is None and bad.status=='failed' and bad.error_code=='INVALID_FILE_FORMAT','no_job_import':detail.job_id is None}
        with make_uow() as uow:
            tasks=list(uow.session.scalars(select(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id==int(good.id))))
            checks['one_reference_only_task']=len(tasks)==1 and set(tasks[0].input_refs)=={'file_id','import_item_id'} and tasks[0].job_type=='resume.parse'
        print(json.dumps({'ready':all(checks.values()),'batch_id':a.id,'checks':checks,'actual_item_states':[i.status for i in detail.items],'boundary':'T14 acceptance only; T15 handler/materialization not yet implemented'},indent=2))
        return 0 if all(checks.values()) else 1
    finally: store.close()
if __name__=='__main__': raise SystemExit(main())
