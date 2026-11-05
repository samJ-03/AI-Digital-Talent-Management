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
    if job.entity_type!='system': raise ValueError('Invalid diagnostic job scope')
    uow.session.flush()
    return ResultRef('background_job',job.id,200)

HANDLERS={'system.verify':verify_runtime}

@celery_app.task(name='talent.execute_job')
def execute_job(job_id: int) -> None:
    if type(job_id) is not int or job_id<=0: raise ValueError('Invalid job ID')
    JobRunner(BackgroundJobService(),HANDLERS).execute(job_id)

def publish_job(job_id: int) -> None:
    # Only a numeric task ID crosses Redis; DB remains the source of truth.
    with celery_app.connection_for_write() as connection:
        connection.ensure_connection(max_retries=0,timeout=3)
        execute_job.apply_async(args=[job_id],queue='talent-dev',connection=connection,retry=False)
