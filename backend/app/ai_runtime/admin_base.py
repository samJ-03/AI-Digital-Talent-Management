from contextlib import contextmanager
from uuid import uuid4
from sqlalchemy.exc import IntegrityError,DBAPIError
from sqlalchemy.orm.exc import StaleDataError
from app.audit.service import AuditService,AuditEvent
from app.core.access import AccessPolicy,ResourceScope
from app.core.errors import DomainError
from app.core.request_context import request_id_context
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user

class AiAdminBase:
    def __init__(self,uow_factory=make_uow): self.uow_factory=uow_factory

    def authorize(self,uow,actor,permission):
        AccessPolicy().require(actor,permission,ResourceScope('system'))
        user=uow.session.get(User,actor.user_id)
        if user is None: raise DomainError('SESSION_REQUIRED',401,'请重新登录')
        fresh=resolve_user(uow.session,user)
        AccessPolicy().require(fresh,permission,ResourceScope('system'))
        return fresh

    @contextmanager
    def transaction(self,actor,permission):
        try:
            with self.uow_factory() as uow:
                fresh=self.authorize(uow,actor,permission)
                with uow.session.no_autoflush: yield uow,fresh
                uow.commit()
        except StaleDataError:
            raise DomainError('VERSION_CONFLICT',409,'资源已被更新') from None
        except DBAPIError as error:
            if error.orig.args[0] in {1062,1205,1213}:
                raise DomainError('CONFIG_CONFLICT',409,'配置已被并发修改，请刷新后重试') from None
            raise

    def audit(self,uow,actor,action,kind,entity_id,summary):
        AuditService().append(uow,actor,AuditEvent(action,ResourceScope(kind,id=entity_id),summary,'success',request_id_context.get() or str(uuid4())))
