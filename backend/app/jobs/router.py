"""岗位HTTP契约：HR写操作、幂等键、CAS和不缓存响应。"""
from fastapi import APIRouter,Depends,Header,Path,Request,Response
from app.core.types import ApiEnvelope
from app.identity.router import require_staff_write,expected_version
from app.jobs.schemas import JobCreate,JobPatch,JobVersionDraft,JobView,JobVersionView,ReasonCommand,StateCommand,AutomationCommand,AutomationView
from app.jobs.service import JobService

router=APIRouter(prefix='/api/v1')

def service(request,key=None):
    """使用当前应用的事务工厂和受控配置，不另建数据源。"""
    runtime=request.app.state.identity
    return JobService(runtime.uow_factory,key,runtime.settings)

def envelope(request,response,value):
    """为岗位或开关响应提供对应Job/Version的ETag。"""
    version=value.job.version if isinstance(value,AutomationView) else value.version
    response.headers['ETag']='"'+str(version)+'"'
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=value,request_id=request.state.request_id)

@router.post('/jobs',status_code=201,response_model=ApiEnvelope[JobView])
def create_job(cmd: JobCreate,request: Request,response: Response,idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API015：HR建岗，不自动开启邀请或发送邮件。"""
    return envelope(request,response,service(request,idempotency_key).create(actor,cmd))

@router.patch('/jobs/{job_id}',response_model=ApiEnvelope[JobView])
def update_job(cmd: JobPatch,request: Request,response: Response,job_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API016：以If-Match修改可变元数据，拒绝版本指针注入。"""
    return envelope(request,response,service(request).update(actor,job_id,cmd,expected_version(if_match)))

@router.post('/jobs/{job_id}/versions',status_code=201,response_model=ApiEnvelope[JobVersionView])
def draft_version(cmd: JobVersionDraft,request: Request,response: Response,job_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API018：建立独立岗位条件草稿，不覆盖当前发布标准。"""
    return envelope(request,response,service(request,idempotency_key).draft(actor,job_id,cmd))

@router.patch('/job-versions/{version_id}',response_model=ApiEnvelope[JobVersionView])
def edit_version(cmd: JobVersionDraft,request: Request,response: Response,version_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API019：CAS编辑未发布草稿，已发布内容不可改写。"""
    return envelope(request,response,service(request).edit_draft(actor,version_id,cmd,expected_version(if_match)))

@router.post('/job-versions/{version_id}/publish',response_model=ApiEnvelope[JobVersionView])
def publish_version(cmd: ReasonCommand,request: Request,response: Response,version_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API020：校验标准与试卷归属后幂等发布。"""
    return envelope(request,response,service(request,idempotency_key).publish(actor,version_id,cmd.reason))

@router.post('/jobs/{job_id}/state',response_model=ApiEnvelope[JobView])
def transition(cmd: StateCommand,request: Request,response: Response,job_id: int=Path(gt=0),if_match: str|None=Header(default=None),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API021：显式开放/暂停/关闭；重开不复活自动邀请。"""
    return envelope(request,response,service(request,idempotency_key).transition(actor,job_id,cmd.action,expected_version(if_match),cmd.reason))

@router.put('/jobs/{job_id}/automation',response_model=ApiEnvelope[AutomationView])
def automation(cmd: AutomationCommand,request: Request,response: Response,job_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API022：以CAS设置开关，只在开启时通过依赖和邀请权限门。"""
    return envelope(request,response,service(request).set_automation(actor,job_id,cmd.enabled,expected_version(if_match)))
