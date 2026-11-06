"""后台身份认证与权限：执行授权后的只读查询与投影。"""
from sqlalchemy import select, func
from app.core.access import AccessPolicy, ResourceScope
from app.core.types import Page, PageQuery
from app.core.uow import make_uow
from app.identity.models import User, Department, Role
from app.identity.schemas import UserView, DepartmentView, RoleView
from app.identity.views import user_view, department_view, role_view

class IdentityQueries:
    """IdentityQueries：后台身份认证与权限中的协作类型。"""
    def __init__(self,uow_factory=make_uow):
        self.uow_factory=uow_factory
        self.policy=AccessPolicy()

    def users(self,actor,query: PageQuery) -> Page[UserView]:
        """返回允许展示的后台账号字段。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        self.policy.require(actor,'user.manage',ResourceScope('user'))
        with self.uow_factory() as uow:
            rows=list(uow.session.scalars(select(User).order_by(User.created_at.desc(),User.id.desc()).offset((query.page-1)*query.page_size).limit(query.page_size)))
            total=uow.session.scalar(select(func.count()).select_from(User))
            return Page(items=[user_view(uow.session,row) for row in rows],total=total,page=query.page,page_size=query.page_size)

    def departments(self,actor) -> list[DepartmentView]:
        """返回授权范围内的部门信息。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        self.policy.require(actor,'department.manage',ResourceScope('department'))
        with self.uow_factory() as uow:
            return [department_view(row) for row in uow.session.scalars(select(Department).order_by(Department.id))]

    def roles(self,actor) -> list[RoleView]:
        """返回可管理的角色及显式权限。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        self.policy.require(actor,'role.manage',ResourceScope('role'))
        with self.uow_factory() as uow:
            return [role_view(row) for row in uow.session.scalars(select(Role).order_by(Role.id))]
