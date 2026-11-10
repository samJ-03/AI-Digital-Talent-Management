"""招聘关系入口：API037批量选择人才加入岗位。"""
from fastapi import APIRouter,Depends,Header,Path,Request,Response
from app.core.types import ApiEnvelope
from app.identity.router import require_staff_write
from app.recruitment.application_service import ApplicationService,AddCandidates,ApplicationView
router=APIRouter(prefix='/api/v1')

@router.post('/jobs/{job_id}/applications',status_code=202,response_model=ApiEnvelope[list[ApplicationView]])
def add_candidates(cmd: AddCandidates,request: Request,response: Response,job_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """新关系异步评估，已有规范关系复用且不重复自动触发。"""
    value=ApplicationService(request.app.state.identity.uow_factory,idempotency_key).add_candidates(actor,job_id,cmd.candidate_ids,cmd.source)
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=value,request_id=request.state.request_id)
