"""后台身份认证与权限：定义输入输出类型、字段约束及序列化边界。"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from app.identity.permissions import PERMISSIONS, ADMIN_PERMISSIONS, HR_PERMISSIONS

class InputModel(BaseModel):
    """InputModel：后台身份认证与权限中的输入输出数据契约。"""
    model_config=ConfigDict(extra='forbid')

class LoginCommand(InputModel):
    """LoginCommand：后台身份认证与权限中的输入输出数据契约。"""
    login_name: str=Field(min_length=1,max_length=100,pattern=r'^[a-zA-Z0-9_.@-]+$')
    password: SecretStr=Field(min_length=1,max_length=256)

class UserCreate(LoginCommand):
    """UserCreate：后台身份认证与权限中的协作类型。"""
    department_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']='active'
    @field_validator('password')
    @classmethod
    def strong_password(cls,value):
        """校验后台密码强度，禁止空值或弱口令。"""
        if len(value.get_secret_value())<12:
            raise ValueError('Password requires at least 12 characters')
        return value

class UserPatch(InputModel):
    """UserPatch：后台身份认证与权限中的输入输出数据契约。"""
    department_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']|None=None
    password: SecretStr|None=Field(default=None,min_length=12,max_length=256)

class DepartmentWrite(InputModel):
    """DepartmentWrite：后台身份认证与权限中的输入输出数据契约。"""
    name: str=Field(min_length=1,max_length=100)
    parent_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']='active'
    expected_version: int|None=Field(default=None,exclude=True)

class DepartmentPatch(InputModel):
    """DepartmentPatch：后台身份认证与权限中的输入输出数据契约。"""
    name: str|None=Field(default=None,min_length=1,max_length=100)
    parent_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']|None=None

class RoleWrite(InputModel):
    """RoleWrite：后台身份认证与权限中的输入输出数据契约。"""
    code: str=Field(min_length=1,max_length=50,pattern=r'^[a-zA-Z0-9_.-]+$')
    name: str=Field(min_length=1,max_length=100)
    permission_codes: list[str]=Field(max_length=100)
    data_scope: Literal['department','company']
    status: Literal['active','disabled']='active'
    expected_version: int|None=Field(default=None,exclude=True)
    @field_validator('permission_codes')
    @classmethod
    def known_permissions(cls,value):
        """拒绝不在显式权限集合中的权限码。"""
        codes=set(value)
        if not codes<=PERMISSIONS or (codes&ADMIN_PERMISSIONS and codes&HR_PERMISSIONS):
            raise ValueError('Unknown or mixed administrator/HR permissions')
        return sorted(codes)

class RolePatch(InputModel):
    """RolePatch：后台身份认证与权限中的输入输出数据契约。"""
    code: str|None=Field(default=None,min_length=1,max_length=50,pattern=r'^[a-zA-Z0-9_.-]+$')
    name: str|None=Field(default=None,min_length=1,max_length=100)
    permission_codes: list[str]|None=Field(default=None,max_length=100)
    data_scope: Literal['department','company']|None=None
    status: Literal['active','disabled']|None=None

class SetRoles(InputModel):
    """SetRoles：后台身份认证与权限中的输入输出数据契约。"""
    role_ids: list[int]=Field(max_length=30)
    @field_validator('role_ids')
    @classmethod
    def positive_unique(cls,value):
        """校验正数列表及重复项约束。"""
        if len(value)!=len(set(value)) or any(v<=0 for v in value):
            raise ValueError('Role IDs must be unique positive integers')
        return value

class UserView(BaseModel):
    """UserView：后台身份认证与权限中的输入输出数据契约。"""
    id: str
    login_name: str
    department_id: str|None
    status: str
    role_ids: list[str]
    permission_codes: list[str]
    actor_type: str
    version: int
    csrf_token: str|None=None

class DepartmentView(BaseModel):
    """DepartmentView：后台身份认证与权限中的输入输出数据契约。"""
    id: str
    name: str
    parent_id: str|None
    status: str
    version: int

class RoleView(BaseModel):
    """RoleView：后台身份认证与权限中的输入输出数据契约。"""
    id: str
    code: str
    name: str
    permission_codes: list[str]
    data_scope: str
    status: str
    version: int

class StaffSessionView(BaseModel):
    """StaffSessionView：后台身份认证与权限中的输入输出数据契约。"""
    session_id: str=Field(exclude=True,repr=False)
    csrf_token: str
    expires_at: datetime
    user: UserView
