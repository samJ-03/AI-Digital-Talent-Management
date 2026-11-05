from contextlib import contextmanager
from uuid import uuid4
from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from app.audit.service import AuditService, AuditEvent
from app.core.access import AccessPolicy, ResourceScope
from app.core.errors import DomainError
from app.core.request_context import request_id_context
from app.core.uow import make_uow
from app.identity.models import User, Role, UserRole, Department
from app.identity.permissions import ADMIN_PERMISSIONS, HR_PERMISSIONS
from app.identity.schemas import UserCreate, UserPatch, DepartmentWrite, RoleWrite
from app.identity.views import resolve_user, user_view, department_view, role_view

class IdentityAdminService:
    def __init__(self,uow_factory=make_uow):
        self.uow_factory=uow_factory
        self.policy=AccessPolicy()
        self.audit=AuditService()
        self.hasher=PasswordHasher()

    @contextmanager
    def _transaction(self,actor,permission):
        self.policy.require(actor,permission,ResourceScope('system'))
        try:
            with self.uow_factory() as uow:
                # Serialize administrative grants and last-administrator checks in a stable order.
                list(uow.session.scalars(select(Role).order_by(Role.id).with_for_update()))
                user=uow.session.get(User,actor.user_id)
                if user is None:
                    raise DomainError('SESSION_REQUIRED',401,'请重新登录')
                fresh=resolve_user(uow.session,user)
                self.policy.require(fresh,permission,ResourceScope('system'))
                with uow.session.no_autoflush:
                    yield uow,fresh
                uow.commit()
        except StaleDataError:
            raise DomainError('VERSION_CONFLICT',409,'资源已被其他操作更新') from None
        except IntegrityError as error:
            if error.orig.args[0]==1062:
                raise DomainError('RESOURCE_CONFLICT',409,'账号或角色标识已存在') from None
            raise

    def _get(self,uow,model,row_id,expected_version=None):
        row=uow.session.scalar(select(model).where(model.id==row_id).with_for_update())
        if row is None:
            raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在')
        if expected_version is not None and row.row_version!=expected_version:
            raise DomainError('VERSION_CONFLICT',409,'资源已被其他操作更新')
        return row

    def _department(self,uow,department_id):
        if department_id is not None:
            row=uow.session.get(Department,department_id)
            if row is None or row.status!='active':
                raise DomainError('INVALID_DEPARTMENT',422,'部门不存在或已停用')

    def _audit(self,uow,actor,action,kind,row_id,summary):
        self.audit.append(uow,actor,AuditEvent(action,ResourceScope(kind,id=row_id),summary,'success',request_id_context.get() or str(uuid4())))

    def _validate_grants(self,uow,user,roles):
        permissions={p for r in roles if r.status=='active' for p in r.permission_codes}
        if permissions&ADMIN_PERMISSIONS and permissions&HR_PERMISSIONS:
            raise DomainError('MIXED_ROLES',422,'管理员与 HR 使用独立账号')
        if permissions&HR_PERMISSIONS:
            if user.department_id is None:
                raise DomainError('DEPARTMENT_REQUIRED',422,'HR 账号必须指定部门')
            self._department(uow,user.department_id)

    def _keep_administrator(self,uow):
        uow.session.flush()
        admins=list(uow.session.scalars(select(User).where(User.status=='active')))
        for user in admins:
            try:
                actor=resolve_user(uow.session,user)
                if actor.actor_type=='admin' and {'user.manage','role.manage'}<=actor.permissions:
                    return
            except DomainError:
                continue
        raise DomainError('LAST_ADMIN_REQUIRED',422,'必须保留一个可管理账号与角色的管理员')

    def create_user(self,actor,cmd: UserCreate):
        with self._transaction(actor,'user.manage') as (uow,fresh):
            self._department(uow,cmd.department_id)
            row=User(login_name=cmd.login_name,password_hash=self.hasher.hash(cmd.password.get_secret_value()),department_id=cmd.department_id,status=cmd.status)
            uow.session.add(row);uow.session.flush()
            self._audit(uow,fresh,'user.create','user',row.id,{'changed_fields':['login_name','department_id','status']})
            return user_view(uow.session,row)

    def update_user(self,actor,user_id: int,cmd: UserPatch,expected_version: int):
        with self._transaction(actor,'user.manage') as (uow,fresh):
            row=self._get(uow,User,user_id,expected_version)
            values=cmd.model_dump(exclude_unset=True)
            if not values:
                raise DomainError('EMPTY_UPDATE',422,'至少提供一个修改项')
            if 'status' in values and cmd.status is None or 'password' in values and cmd.password is None:
                raise DomainError('INVALID_INPUT',422,'状态和密码不可为空')
            if 'department_id' in values:
                self._department(uow,cmd.department_id)
                row.department_id=cmd.department_id
            if 'status' in values: row.status=cmd.status
            if cmd.password is not None: row.password_hash=self.hasher.hash(cmd.password.get_secret_value())
            roles=list(uow.session.scalars(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==row.id)))
            if row.status=='active': self._validate_grants(uow,row,roles)
            row.auth_version+=1
            self._keep_administrator(uow)
            self._audit(uow,fresh,'user.update','user',row.id,{'changed_fields':sorted(values)})
            return user_view(uow.session,row)

    def set_roles(self,actor,user_id: int,role_ids: list[int],expected_version: int):
        if len(role_ids)!=len(set(role_ids)) or any(i<=0 for i in role_ids):
            raise DomainError('INVALID_ROLES',422,'角色列表无效')
        with self._transaction(actor,'user.manage') as (uow,fresh):
            row=self._get(uow,User,user_id,expected_version)
            roles=list(uow.session.scalars(select(Role).where(Role.id.in_(role_ids))))
            if len(roles)!=len(role_ids) or any(r.status!='active' for r in roles):
                raise DomainError('INVALID_ROLES',422,'角色不存在或已停用')
            self._validate_grants(uow,row,roles)
            existing=list(uow.session.scalars(select(UserRole).where(UserRole.user_id==user_id)))
            for grant in existing: uow.session.delete(grant)
            uow.session.flush()
            for role_id in role_ids: uow.session.add(UserRole(user_id=user_id,role_id=role_id))
            row.auth_version+=1
            self._keep_administrator(uow)
            self._audit(uow,fresh,'user.roles','user',row.id,{'role_ids':role_ids})
            return user_view(uow.session,row)

    def upsert_department(self,actor,department_id: int|None,cmd: DepartmentWrite):
        with self._transaction(actor,'department.manage') as (uow,fresh):
            departments=list(uow.session.scalars(select(Department).order_by(Department.id).with_for_update()))
            by_id={d.id:d for d in departments}
            row=self._get(uow,Department,department_id,cmd.expected_version) if department_id else Department()
            current=cmd.parent_id
            seen=set()
            while current is not None:
                if current==department_id or current in seen:
                    raise DomainError('DEPARTMENT_CYCLE',422,'部门层级不可循环')
                seen.add(current)
                parent=by_id.get(current)
                if parent is None or parent.status!='active':
                    raise DomainError('INVALID_DEPARTMENT',422,'上级部门不存在或已停用')
                current=parent.parent_id
            row.name=cmd.name;row.parent_id=cmd.parent_id;row.status=cmd.status
            uow.session.add(row);uow.session.flush()
            self._keep_administrator(uow)
            self._audit(uow,fresh,'department.write','department',row.id,{'changed_fields':['name','parent_id','status']})
            return department_view(row)

    def upsert_role(self,actor,role_id: int|None,cmd: RoleWrite):
        with self._transaction(actor,'role.manage') as (uow,fresh):
            row=self._get(uow,Role,role_id,cmd.expected_version) if role_id else Role()
            row.code=cmd.code;row.name=cmd.name;row.permission_codes=cmd.permission_codes;row.data_scope=cmd.data_scope;row.status=cmd.status
            uow.session.add(row);uow.session.flush()
            if role_id:
                users=list(uow.session.scalars(select(User).join(UserRole,UserRole.user_id==User.id).where(UserRole.role_id==role_id).order_by(User.id).with_for_update()))
                for user in users:
                    roles=list(uow.session.scalars(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==user.id)))
                    self._validate_grants(uow,user,roles)
                    user.auth_version+=1
            self._keep_administrator(uow)
            self._audit(uow,fresh,'role.write','role',row.id,{'changed_fields':['permission_codes','data_scope','status']})
            return role_view(row)
