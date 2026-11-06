"""后台身份认证与权限：校验后台登录、注销和会话失效。"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from sqlalchemy import select
from uuid import uuid4
from app.audit.service import AuditService, AuditEvent
from app.core.access import ResourceScope
from app.core.request_context import request_id_context
from app.core.errors import DomainError
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.schemas import LoginCommand, StaffSessionView, UserView
from app.identity.session_store import StaffSessionStore
from app.identity.views import resolve_user, user_view

class AuthService:
    """AuthService：后台身份认证与权限中的协作类型。"""
    def __init__(self,store: StaffSessionStore,uow_factory=make_uow):
        self.store=store
        self.uow_factory=uow_factory
        self.hasher=PasswordHasher()
        # Missing accounts still incur the same password verification work.
        self.dummy_hash=self.hasher.hash('unused-'+__import__('secrets').token_urlsafe(32))

    def login(self,cmd: LoginCommand) -> StaffSessionView:
        """校验凭据并建立受保护的后台会话。"""
        self.store.limit('account',cmd.login_name.casefold(),10)
        with self.uow_factory() as uow:
            user=uow.session.scalar(select(User).where(User.login_name==cmd.login_name))
            try:
                valid=self.hasher.verify(user.password_hash if user else self.dummy_hash,cmd.password.get_secret_value())
            except (VerifyMismatchError,VerificationError,InvalidHashError):
                valid=False
            if not valid or user is None or user.status!='active':
                raise DomainError('LOGIN_FAILED',401,'账号或密码错误')
            actor=resolve_user(uow.session,user)
            view=user_view(uow.session,user)
            sid,data=self.store.create(user.id,user.auth_version)
            try:
                AuditService().append(uow,actor,AuditEvent('auth.login',ResourceScope('user',id=user.id),{'result':'session_created'},'success',request_id_context.get() or str(uuid4())))
                uow.commit()
            except Exception:
                self.store.delete(sid)
                raise
            return StaffSessionView(session_id=sid,csrf_token=data.csrf_token,expires_at=data.expires_at,user=view)

    def require(self,session_id: str):
        """验证权限或地址策略，不满足时失败关闭。"""
        data=self.store.get(session_id)
        with self.uow_factory() as uow:
            user=uow.session.get(User,data.user_id)
            if user is None or user.auth_version!=data.auth_version:
                raise DomainError('SESSION_REQUIRED',401,'请重新登录')
            return resolve_user(uow.session,user),data

    def me(self,actor) -> UserView:
        """返回当前已认证后台账号的允许字段。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        with self.uow_factory() as uow:
            user=uow.session.get(User,actor.user_id)
            if user is None:
                raise DomainError('SESSION_REQUIRED',401,'请重新登录')
            resolve_user(uow.session,user)
            return user_view(uow.session,user)

    def logout(self,session_id: str) -> None:
        """撤销当前后台会话并清理认证Cookie。"""
        actor,data=self.require(session_id)
        self.store.delete(session_id)
        with self.uow_factory() as uow:
            AuditService().append(uow,actor,AuditEvent('auth.logout',ResourceScope('user',id=actor.user_id),{'result':'session_revoked'},'success',request_id_context.get() or str(uuid4())))
            uow.commit()
