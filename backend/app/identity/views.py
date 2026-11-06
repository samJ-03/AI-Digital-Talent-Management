"""后台身份认证与权限：构造对外视图，控制内部字段暴露。"""
from sqlalchemy import select
from app.core.access import ActorContext
from app.core.errors import DomainError
from app.identity.models import User, Role, UserRole, Department
from app.identity.permissions import ADMIN_PERMISSIONS, HR_PERMISSIONS
from app.identity.schemas import UserView, DepartmentView, RoleView

def active_roles(session,user_id: int) -> list[Role]:
    """查询当前账号仍有效的角色。"""
    return list(session.scalars(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==user_id,Role.status=='active').order_by(Role.id)))

def resolve_user(session,user: User) -> ActorContext:
    """根据当前角色与部门重新计算账号权限。"""
    if user.status!='active':
        raise DomainError('SESSION_REQUIRED',401,'请重新登录')
    departments=set()
    if user.department_id is not None:
        current=user.department_id
        seen=set()
        while current is not None:
            if current in seen: raise DomainError('SESSION_REQUIRED',401,'请重新登录')
            seen.add(current)
            department=session.get(Department,current)
            if department is None or department.status!='active':
                raise DomainError('SESSION_REQUIRED',401,'请重新登录')
            current=department.parent_id
        departments.add(user.department_id)
    roles=active_roles(session,user.id)
    permissions=frozenset(code for role in roles for code in role.permission_codes)
    if permissions&ADMIN_PERMISSIONS and permissions&HR_PERMISSIONS:
        raise DomainError('SESSION_REQUIRED',401,'角色配置冲突，请联系管理员')
    company=frozenset(code for role in roles if role.data_scope=='company' for code in role.permission_codes)
    return ActorContext('admin' if permissions&ADMIN_PERMISSIONS else 'hr',user_id=user.id,
        department_ids=frozenset(departments),permissions=permissions,company_permissions=company)

def user_view(session,user: User) -> UserView:
    """构造user的允许字段视图。"""
    roles=active_roles(session,user.id)
    permissions=sorted({code for role in roles for code in role.permission_codes})
    return UserView(id=str(user.id),login_name=user.login_name,department_id=str(user.department_id) if user.department_id else None,
        status=user.status,role_ids=[str(r.id) for r in roles],permission_codes=permissions,
        actor_type='admin' if set(permissions)&ADMIN_PERMISSIONS else 'hr',version=user.row_version)

def department_view(row: Department) -> DepartmentView:
    """构造department的允许字段视图。"""
    return DepartmentView(id=str(row.id),name=row.name,parent_id=str(row.parent_id) if row.parent_id else None,status=row.status,version=row.row_version)

def role_view(row: Role) -> RoleView:
    """构造role的允许字段视图。"""
    return RoleView(id=str(row.id),code=row.code,name=row.name,permission_codes=sorted(row.permission_codes),data_scope=row.data_scope,status=row.status,version=row.row_version)
