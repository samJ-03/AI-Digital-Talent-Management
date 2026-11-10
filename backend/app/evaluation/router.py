"""API040至042：HR异步重评、部门隔离查询和有理由人工继续。"""
from fastapi import APIRouter,Depends,Header,Path,Request,Response
from app.core.types import ApiEnvelope
from app.identity.router import require_staff,require_staff_write
from app.evaluation.api_schemas import EvaluationRequest,OverrideRequest,EvaluationAccepted,EvaluationDetail
from app.evaluation.service import EvaluationService
router=APIRouter(prefix='/api/v1')

def envelope(request,response,value):
    """招聘评估响应禁止共享缓存。"""
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=value,request_id=request.state.request_id)

@router.post('/applications/{application_id}/evaluations',status_code=202,response_model=ApiEnvelope[EvaluationAccepted])
def start(cmd: EvaluationRequest,request: Request,response: Response,application_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API040：新建不可变运行，重评始终仅人工邀请。"""
    return envelope(request,response,EvaluationService(request.app.state.identity.uow_factory,idempotency_key).start(actor,application_id,cmd))

@router.get('/evaluations/{run_id}',response_model=ApiEnvelope[EvaluationDetail])
def get(request: Request,response: Response,run_id: int=Path(gt=0),actor=Depends(require_staff)):
    """API041：读取冻结版本与原始逐条件证据。"""
    return envelope(request,response,EvaluationService(request.app.state.identity.uow_factory).get(actor,run_id))

@router.post('/evaluations/{run_id}/override',response_model=ApiEnvelope[EvaluationDetail])
def override(cmd: OverrideRequest,request: Request,response: Response,run_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API042：追加人工决定，保留原始粗筛并复验技术前提。"""
    return envelope(request,response,EvaluationService(request.app.state.identity.uow_factory,idempotency_key).override(actor,run_id,cmd.reason))
