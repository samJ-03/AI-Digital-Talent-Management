from sqlalchemy import select
from app.core.access import AccessPolicy,ResourceScope
from app.core.errors import DomainError
from app.runtime.models import BackgroundJob

class RuntimeAdminQueries:
    def __init__(self,uow_factory): self.uow_factory=uow_factory
    def report(self,actor,task_id=None):
        if actor.actor_type!='admin': raise DomainError('PERMISSION_DENIED',403,'需要管理员权限')
        AccessPolicy().require(actor,'runtime.read',ResourceScope('runtime'))
        with self.uow_factory() as uow:
            query=select(BackgroundJob).order_by(BackgroundJob.created_at.desc(),BackgroundJob.id.desc()).limit(20)
            if task_id is not None: query=query.where(BackgroundJob.id==task_id)
            rows=list(uow.session.scalars(query))
            return {'tasks':[{'id':str(r.id),'job_type':r.job_type,'state':r.state,'entity_type':r.entity_type,'entity_id':str(r.entity_id),'attempt_count':r.attempt_count,
                'error_code':r.error_code if r.error_code in {'HANDLER_FAILED','HANDLER_NOT_REGISTERED','SMTP_TEST_FAILED','SMTP_DELIVERY_UNKNOWN','MAIL_CONFIG_DISABLED','MAIL_TEST_EXPIRED','ATTEMPT_LIMIT'} else None} for r in rows]}
