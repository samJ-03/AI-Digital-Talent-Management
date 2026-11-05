import secrets
from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import ValidationError
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.errors import DomainError
from app.core.types import ApiEnvelope, PageQuery
from app.core.uow import SqlAlchemyUow
from app.identity.auth_service import AuthService
from app.identity.admin_service import IdentityAdminService
from app.identity.queries import IdentityQueries
from app.identity.session_store import StaffSessionStore
from app.identity.schemas import LoginCommand, UserCreate, UserPatch, DepartmentWrite, DepartmentPatch, RoleWrite, RolePatch, SetRoles
from app.identity.models import Department, Role

COOKIE='talent_staff'

class IdentityRuntime:
    def __init__(self,settings):
        self.settings=settings
        self.engine=create_engine(settings.database_url.get_secret_value(),pool_pre_ping=True,pool_recycle=1800)
        self.factory=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.uow_factory=lambda:SqlAlchemyUow(self.factory)
        self.redis=Redis.from_url(settings.redis_url.get_secret_value(),socket_timeout=3,socket_connect_timeout=3)
        self.store=StaffSessionStore(self.redis,settings.session_namespace)
        self.auth=AuthService(self.store,self.uow_factory)
        self.admin=IdentityAdminService(self.uow_factory)
        self.queries=IdentityQueries(self.uow_factory)

    def close(self):
        self.redis.close()
        self.engine.dispose()

def require_staff(request: Request):
    runtime=request.app.state.identity
    sid=request.cookies.get(COOKIE,'')
    actor,session=runtime.auth.require(sid)
    request.state.staff_session=session
    request.state.staff_actor=actor
    return actor

def check_origin(request: Request):
    origin=request.headers.get('origin')
    if origin and origin not in request.app.state.identity.settings.trusted_origins:
        raise DomainError('ORIGIN_DENIED',403,'请求来源未获允许')
    if request.headers.get('sec-fetch-site')=='cross-site':
        raise DomainError('ORIGIN_DENIED',403,'请求来源未获允许')

def require_staff_write(request: Request,actor=Depends(require_staff)):
    check_origin(request)
    supplied=request.headers.get('x-csrf-token','')
    if not secrets.compare_digest(supplied,request.state.staff_session.csrf_token):
        raise DomainError('CSRF_REQUIRED',403,'需要有效的 CSRF 校验')
    return actor

def expected_version(value: str|None) -> int:
    if value is None:
        raise DomainError('VERSION_REQUIRED',428,'修改前需要提供资源版本')
    text=value.strip('"')
    if not text.isascii() or not text.isdigit() or len(text)>10 or int(text)<1:
        raise DomainError('INVALID_VERSION',422,'资源版本无效')
    return int(text)

def envelope(request,value):
    return ApiEnvelope(data=value,request_id=request.state.request_id)

def versioned(request,response,value):
    response.headers['ETag']='"'+str(value.version)+'"'
    return envelope(request,value)

def identity_router() -> APIRouter:
    router=APIRouter(prefix='/api/v1')

    @router.post('/auth/login')
    def login(cmd: LoginCommand,request: Request,response: Response):
        check_origin(request)
        runtime=request.app.state.identity
        runtime.store.limit('address',request.client.host if request.client else 'unknown',100)
        result=runtime.auth.login(cmd)
        old=request.cookies.get(COOKIE)
        if old: runtime.store.delete(old)
        response.set_cookie(COOKIE,result.session_id,max_age=runtime.store.TTL,httponly=True,secure=runtime.settings.environment=='production',samesite='lax',path='/api/v1')
        response.headers['Cache-Control']='no-store'
        return envelope(request,result)

    @router.get('/auth/me')
    def me(request: Request,response: Response,actor=Depends(require_staff)):
        view=request.app.state.identity.auth.me(actor)
        view.csrf_token=request.state.staff_session.csrf_token
        response.headers['Cache-Control']='no-store'
        return versioned(request,response,view)

    @router.post('/auth/logout')
    def logout(request: Request,response: Response,actor=Depends(require_staff_write)):
        request.app.state.identity.auth.logout(request.cookies.get(COOKIE,''))
        response.delete_cookie(COOKIE,path='/api/v1',httponly=True,secure=request.app.state.identity.settings.environment=='production',samesite='lax')
        return envelope(request,{'acknowledged':True})

    @router.get('/admin/users')
    def get_admin_users(request: Request,page: int=1,page_size: int=20,actor=Depends(require_staff)):
        try: query=PageQuery(page=page,page_size=page_size)
        except ValidationError: raise DomainError('INVALID_INPUT',422,'分页参数无效') from None
        return envelope(request,request.app.state.identity.queries.users(actor,query))

    @router.post('/admin/users',status_code=201)
    def create_admin_user(cmd: UserCreate,request: Request,response: Response,actor=Depends(require_staff_write)):
        return versioned(request,response,request.app.state.identity.admin.create_user(actor,cmd))

    @router.patch('/admin/users/{user_id}')
    def update_admin_user(user_id: int,cmd: UserPatch,request: Request,response: Response,if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
        return versioned(request,response,request.app.state.identity.admin.update_user(actor,user_id,cmd,expected_version(if_match)))

    @router.put('/admin/users/{user_id}/roles')
    def set_admin_user_roles(user_id: int,cmd: SetRoles,request: Request,response: Response,if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
        return versioned(request,response,request.app.state.identity.admin.set_roles(actor,user_id,cmd.role_ids,expected_version(if_match)))

    @router.get('/admin/departments')
    def get_admin_departments(request: Request,actor=Depends(require_staff)):
        return envelope(request,request.app.state.identity.queries.departments(actor))

    @router.post('/admin/departments',status_code=201)
    def create_admin_department(cmd: DepartmentWrite,request: Request,response: Response,actor=Depends(require_staff_write)):
        return versioned(request,response,request.app.state.identity.admin.upsert_department(actor,None,cmd))

    @router.patch('/admin/departments/{department_id}')
    def update_admin_department(department_id: int,cmd: DepartmentPatch,request: Request,response: Response,if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
        runtime=request.app.state.identity
        version=expected_version(if_match)
        # Read only after the same authorization used for the mutation.
        visible={int(d.id):d for d in runtime.queries.departments(actor)}
        row=visible.get(department_id)
        if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在')
        data={'name':row.name,'parent_id':int(row.parent_id) if row.parent_id else None,'status':row.status}
        data.update(cmd.model_dump(exclude_unset=True))
        try: write=DepartmentWrite(**data,expected_version=version)
        except ValidationError: raise DomainError('INVALID_INPUT',422,'部门参数无效') from None
        return versioned(request,response,runtime.admin.upsert_department(actor,department_id,write))

    @router.get('/admin/roles')
    def get_admin_roles(request: Request,actor=Depends(require_staff)):
        return envelope(request,request.app.state.identity.queries.roles(actor))

    @router.post('/admin/roles',status_code=201)
    def create_admin_role(cmd: RoleWrite,request: Request,response: Response,actor=Depends(require_staff_write)):
        return versioned(request,response,request.app.state.identity.admin.upsert_role(actor,None,cmd))

    @router.patch('/admin/roles/{role_id}')
    def update_admin_role(role_id: int,cmd: RolePatch,request: Request,response: Response,if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
        runtime=request.app.state.identity
        version=expected_version(if_match)
        visible={int(r.id):r for r in runtime.queries.roles(actor)}
        row=visible.get(role_id)
        if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在')
        data=row.model_dump(exclude={'id','version'})
        data.update(cmd.model_dump(exclude_unset=True))
        try: write=RoleWrite(**data,expected_version=version)
        except ValidationError: raise DomainError('INVALID_INPUT',422,'角色参数无效') from None
        return versioned(request,response,runtime.admin.upsert_role(actor,role_id,write))

    return router
