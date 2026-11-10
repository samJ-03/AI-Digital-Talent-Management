"""平台开发工具：组装应用、请求中间件和安全错误响应。"""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from uuid import UUID, uuid4
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.core.settings import Settings
from app.core.errors import DomainError
from app.core.types import ApiEnvelope, HealthView, ReadinessView, MonitorContext
from app.core.readiness import InfrastructureProbe

from app.identity.router import IdentityRuntime, identity_router
from app.ai_runtime.router import AiRuntime,router as ai_router
from app.assessment.paper_router import router as paper_router
from app.jobs.router import router as jobs_router
from app.notifications.router import MailRuntime,router as mail_router
from app.core.request_context import request_id_context
from app.runtime.router import router as runtime_router
from app.files.router import router as files_router
from app.ingestion.router import router as imports_router
from app.talents.router import router as talents_router
from app.talents.merge_router import router as duplicate_router
from app.talents.profile_router import router as profile_router
from app.evaluation.router import router as evaluation_router
from app.recruitment.router import router as recruitment_router
from app.files.storage import S3FileStore
from app.files.service import FileService

logger = logging.getLogger('talent.api')

def create_app(settings: Settings) -> FastAPI:
    """根据Settings装配应用、依赖、中间件和路由。"""
    probe = InfrastructureProbe(settings)
    identity = IdentityRuntime(settings)
    file_store=S3FileStore.from_settings(settings) if settings.minio_user and settings.minio_password else None
    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            probe.close()
            identity.close()
            if file_store: file_store.close()
    app = FastAPI(title='AI数字化人才平台', version='0.1.0', lifespan=lifespan, docs_url='/docs' if settings.environment != 'production' else None)
    app.state.readiness_probe = probe.check
    app.state.identity = identity
    app.state.ai_runtime=AiRuntime(identity.uow_factory,settings)
    app.state.mail_runtime=MailRuntime(identity.uow_factory,settings)
    app.state.file_service=FileService(file_store,identity.uow_factory,max_file_bytes=settings.max_file_bytes,max_pages=settings.max_file_pages) if file_store else None
    app.include_router(identity_router())
    app.include_router(runtime_router)
    app.include_router(files_router)
    app.include_router(imports_router)
    app.include_router(talents_router)
    app.include_router(duplicate_router)
    app.include_router(profile_router)
    app.include_router(ai_router)
    app.include_router(paper_router)
    app.include_router(jobs_router)
    app.include_router(evaluation_router)
    app.include_router(recruitment_router)
    app.include_router(mail_router)

    @app.middleware('http')
    async def request_identity(request: Request, call_next):
        try:
            request_id = str(UUID(request.headers.get('x-request-id','')))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        context_token=request_id_context.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(context_token)
        response.headers['X-Request-ID'] = request_id
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.url.path.startswith(('/api/v1/auth/','/api/v1/admin/')):
            response.headers['Cache-Control']='no-store'
        return response

    def error_response(request: Request, status: int, code: str, message: str, data=None):
        request_id = getattr(request.state, 'request_id', str(uuid4()))
        return JSONResponse(status_code=status, content={'code':code,'message':message,'data':data,'request_id':request_id}, headers={'X-Request-ID':request_id})

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return error_response(request, error.http_status, error.code, error.message, error.safe_details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        details = [{'field':'.'.join(map(str,e['loc'])), 'type':e['type']} for e in error.errors()]
        return error_response(request,422,'INVALID_INPUT','请求参数不符合要求',{'field_errors':details})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        codes = {401:'SESSION_REQUIRED',403:'PERMISSION_DENIED',404:'RESOURCE_NOT_FOUND',405:'METHOD_NOT_ALLOWED'}
        return error_response(request,error.status_code,codes.get(error.status_code,'HTTP_ERROR'),'请求无法完成')

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logger.error('request_failed request_id=%s error_type=%s', getattr(request.state,'request_id','unknown'), type(error).__name__)
        return error_response(request,500,'INTERNAL_ERROR','服务暂时无法完成请求')

    def require_monitor(request: Request) -> MonitorContext:
        supplied = request.headers.get('x-monitor-token','').encode('utf-8')
        expected = settings.monitor_token.get_secret_value().encode('utf-8')
        if not secrets.compare_digest(supplied, expected):
            raise DomainError('MONITOR_UNAUTHORIZED',401,'需要监控身份验证')
        return MonitorContext()

    @app.get('/api/v1/health/live', response_model=ApiEnvelope[HealthView])
    def health_live(request: Request):
        return ApiEnvelope(data=HealthView(alive=True),request_id=request.state.request_id)

    @app.get('/api/v1/health/ready', response_model=ApiEnvelope[ReadinessView])
    def health_ready(request: Request, ctx: MonitorContext = Depends(require_monitor)):
        try:
            checks = app.state.readiness_probe()
            dependencies = {'mysql':checks.get('mysql') is True,'redis':checks.get('redis') is True}
        except Exception:
            dependencies = {'mysql':False,'redis':False}
        ready = all(dependencies.values())
        envelope = ApiEnvelope(code='OK' if ready else 'DEPENDENCY_UNAVAILABLE',message='就绪' if ready else '核心依赖未就绪',data=ReadinessView(ready=ready,dependencies=dependencies),request_id=request.state.request_id)
        return JSONResponse(status_code=200 if ready else 503,content=envelope.model_dump())

    return app

def build_app() -> FastAPI:
    """从进程环境创建供ASGI服务器加载的应用实例。"""
    return create_app(Settings.load())
