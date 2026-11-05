from contextlib import contextmanager
import hashlib
import json
from uuid import uuid4
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm.exc import StaleDataError
from app.audit.service import AuditService,AuditEvent
from app.core.access import AccessPolicy,ResourceScope
from app.core.errors import DomainError
from app.core.idempotency import IdempotencyService
from app.core.request_context import request_id_context
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user

class HrServiceBase:
    def __init__(self,uow_factory=make_uow,idempotency_key=None):
        self.uow_factory=uow_factory;self.idempotency_key=idempotency_key

    def authorize(self,uow,actor,permission,scope):
        if actor.actor_type!='hr': raise DomainError('PERMISSION_DENIED',403,'需要 HR 权限')
        user=uow.session.get(User,actor.user_id)
        if user is None: raise DomainError('SESSION_REQUIRED',401,'请重新登录')
        fresh=resolve_user(uow.session,user)
        if permission not in fresh.permissions: raise DomainError('PERMISSION_DENIED',403,'无操作权限')
        try: AccessPolicy().require(fresh,permission,scope)
        except DomainError:
            raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在') from None
        return fresh

    def execute(self,actor,permission,scope,operation,payload,command,response_permission=None):
        if not self.idempotency_key: raise DomainError('IDEMPOTENCY_KEY_REQUIRED',422,'此操作需要幂等键')
        with self.uow_factory() as uow:
            fresh=self.authorize(uow,actor,permission,scope)
            if response_permission: self.authorize(uow,fresh,response_permission,scope)
        def run(uow):
            current=self.authorize(uow,fresh,permission,scope)
            if response_permission: self.authorize(uow,current,response_permission,scope)
            return command(uow,current)
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
        try: return IdempotencyService(self.uow_factory).execute(fresh,operation,self.idempotency_key,digest,run)
        except DBAPIError as error:
            if error.orig.args[0] in {1062,1205,1213}: raise DomainError('RESOURCE_CONFLICT',409,'资源已被并发修改，请刷新后重试') from None
            raise

    @contextmanager
    def transaction(self,actor,permission,scope,response_permission=None):
        try:
            with self.uow_factory() as uow:
                fresh=self.authorize(uow,actor,permission,scope)
                if response_permission: self.authorize(uow,fresh,response_permission,scope)
                with uow.session.no_autoflush: yield uow,fresh
                uow.commit()
        except StaleDataError:
            raise DomainError('VERSION_CONFLICT',409,'资源已被其他操作更新') from None
        except DBAPIError as error:
            if error.orig.args[0] in {1062,1205,1213}: raise DomainError('RESOURCE_CONFLICT',409,'资源已被并发修改，请刷新后重试') from None
            raise

    def audit(self,uow,actor,action,kind,row_id,summary):
        AuditService().append(uow,actor,AuditEvent(action,ResourceScope(kind,id=row_id),summary,'success',request_id_context.get() or str(uuid4())))
