from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from app.identity.permissions import PERMISSIONS, ADMIN_PERMISSIONS, HR_PERMISSIONS

class InputModel(BaseModel):
    model_config=ConfigDict(extra='forbid')

class LoginCommand(InputModel):
    login_name: str=Field(min_length=1,max_length=100,pattern=r'^[a-zA-Z0-9_.@-]+$')
    password: SecretStr=Field(min_length=1,max_length=256)

class UserCreate(LoginCommand):
    department_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']='active'
    @field_validator('password')
    @classmethod
    def strong_password(cls,value):
        if len(value.get_secret_value())<12:
            raise ValueError('Password requires at least 12 characters')
        return value

class UserPatch(InputModel):
    department_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']|None=None
    password: SecretStr|None=Field(default=None,min_length=12,max_length=256)

class DepartmentWrite(InputModel):
    name: str=Field(min_length=1,max_length=100)
    parent_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']='active'
    expected_version: int|None=Field(default=None,exclude=True)

class DepartmentPatch(InputModel):
    name: str|None=Field(default=None,min_length=1,max_length=100)
    parent_id: int|None=Field(default=None,gt=0)
    status: Literal['active','disabled']|None=None

class RoleWrite(InputModel):
    code: str=Field(min_length=1,max_length=50,pattern=r'^[a-zA-Z0-9_.-]+$')
    name: str=Field(min_length=1,max_length=100)
    permission_codes: list[str]=Field(max_length=100)
    data_scope: Literal['department','company']
    status: Literal['active','disabled']='active'
    expected_version: int|None=Field(default=None,exclude=True)
    @field_validator('permission_codes')
    @classmethod
    def known_permissions(cls,value):
        codes=set(value)
        if not codes<=PERMISSIONS or (codes&ADMIN_PERMISSIONS and codes&HR_PERMISSIONS):
            raise ValueError('Unknown or mixed administrator/HR permissions')
        return sorted(codes)

class RolePatch(InputModel):
    code: str|None=Field(default=None,min_length=1,max_length=50,pattern=r'^[a-zA-Z0-9_.-]+$')
    name: str|None=Field(default=None,min_length=1,max_length=100)
    permission_codes: list[str]|None=Field(default=None,max_length=100)
    data_scope: Literal['department','company']|None=None
    status: Literal['active','disabled']|None=None

class SetRoles(InputModel):
    role_ids: list[int]=Field(max_length=30)
    @field_validator('role_ids')
    @classmethod
    def positive_unique(cls,value):
        if len(value)!=len(set(value)) or any(v<=0 for v in value):
            raise ValueError('Role IDs must be unique positive integers')
        return value

class UserView(BaseModel):
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
    id: str
    name: str
    parent_id: str|None
    status: str
    version: int

class RoleView(BaseModel):
    id: str
    code: str
    name: str
    permission_codes: list[str]
    data_scope: str
    status: str
    version: int

class StaffSessionView(BaseModel):
    session_id: str=Field(exclude=True,repr=False)
    csrf_token: str
    expires_at: datetime
    user: UserView
