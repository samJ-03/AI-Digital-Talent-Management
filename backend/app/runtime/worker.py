"""持久后台任务与Outbox：注册代码固定的Celery处理器并隔离未知任务类型。"""
from celery import Celery
from app.core.idempotency import ResultRef
from app.core.settings import Settings
from app.runtime.job_service import BackgroundJobService,JobRunner

settings=Settings.load()
celery_app=Celery('ai_talent',broker=settings.redis_url.get_secret_value())
celery_app.conf.update(task_serializer='json',accept_content=['json'],result_serializer='json',
    task_default_queue='talent-dev',task_ignore_result=True,task_acks_late=True,task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,broker_connection_retry_on_startup=True,
    broker_transport_options={'global_keyprefix':'talent:broker:','visibility_timeout':600,'socket_timeout':3,'socket_connect_timeout':3},
    task_publish_retry=False,broker_connection_timeout=3)

def verify_runtime(uow,job):
    # A technical probe has no recruitment side effects and never invents business data.
    """检查运行时、依赖版本及允许的环境条件。 uow属于当前调用方事务，回调不得提交外层事务。"""
    if job.entity_type!='system': raise ValueError('Invalid diagnostic job scope')
    uow.session.flush()
    return ResultRef('background_job',job.id,200)

from app.notifications.test_handler import MailTestHandler
from app.core.secrets import SecretCipher
from app.core.uow import make_uow
mail_cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings.encryption_key else None
HANDLERS={'system.verify':verify_runtime,'mail.test':MailTestHandler(make_uow,mail_cipher,settings)}
from app.ingestion.worker import ResumeParseHandler
from app.files.service import FileService
from app.files.storage import S3FileStore
from app.ai_runtime.gateway import ModelGateway
from app.talents.profile_builder import ProfileBuilder
from app.talents.profile_service import ProfileService
from app.talents.profile_worker import ProfileBuildHandler
HANDLERS['profile.build']=ProfileBuildHandler(ProfileService(make_uow,ProfileBuilder(ModelGateway(make_uow,mail_cipher))))
if settings.minio_user and settings.minio_password:
    resume_store=S3FileStore.from_settings(settings)
    HANDLERS['resume.parse']=ResumeParseHandler(
        FileService(resume_store,make_uow,max_file_bytes=settings.max_file_bytes,max_pages=settings.max_file_pages),
        ModelGateway(make_uow,mail_cipher),make_uow)

@celery_app.task(name='talent.execute_job')
def execute_job(job_id: int) -> None:
    """把队列中的数字任务ID交给固定任务执行器。"""
    if type(job_id) is not int or job_id<=0: raise ValueError('Invalid job ID')
    JobRunner(BackgroundJobService(),HANDLERS).execute(job_id)

def publish_job(job_id: int) -> None:
    # Only a numeric task ID crosses Redis; DB remains the source of truth.
    """将已持久化任务ID发布到固定队列。"""
    with celery_app.connection_for_write() as connection:
        connection.ensure_connection(max_retries=0,timeout=3)
        execute_job.apply_async(args=[job_id],queue='talent-dev',connection=connection,retry=False)
