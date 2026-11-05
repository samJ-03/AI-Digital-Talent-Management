from pydantic import BaseModel
from app.core.errors import DomainError
from app.core.resource_scope import ResourceResolver
from app.core.uow import make_uow
from app.runtime.models import BackgroundJob

SAFE_ERROR_CODES=frozenset({'UNKNOWN_JOB_TYPE','ATTEMPT_LIMIT','HANDLER_FAILED','HANDLER_NOT_REGISTERED','DEPENDENCY_UNAVAILABLE','INVALID_OUTPUT'})

class TaskView(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    state: str
    progress: dict[str,str]
    error_code: str|None
    retryable: bool

class RuntimeQueries:
    def __init__(self,uow_factory=make_uow):
        self.uow_factory=uow_factory
        self.resources=ResourceResolver()

    def task(self,actor,task_id: int) -> TaskView:
        # API098 is HR-only. Administrators use a separate sanitized runtime view.
        if actor.actor_type!='hr':
            raise DomainError('PERMISSION_DENIED',403,'无操作权限')
        with self.uow_factory() as uow:
            job=uow.session.get(BackgroundJob,task_id)
            if job is None: raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在')
            self.resources.require(uow.session,actor,job.entity_type,job.entity_id)
            code=job.error_code if job.error_code in SAFE_ERROR_CODES else None
            return TaskView(id=str(job.id),entity_type=job.entity_type,entity_id=str(job.entity_id),state=job.state,
                progress={'stage':job.state},error_code=code,retryable=job.state=='retry')
