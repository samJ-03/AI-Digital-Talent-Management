"""去重HTTP入口：仅HR、写操作CSRF、裁决If-Match与禁缓存。"""
from fastapi import APIRouter,Depends,Header,Path,Query,Request,Response
from typing import Literal
from app.identity.router import require_staff,require_staff_write,expected_version
from app.core.types import ApiEnvelope,Page
from app.talents.merge_schemas import DuplicateQuery,DuplicateCaseView,MergeDecision,MergeResult
from app.talents.merge_service import DuplicateService

router=APIRouter(prefix='/api/v1/duplicates')


@router.get('',response_model=ApiEnvelope[Page[DuplicateCaseView]])
def list_cases(request: Request,response: Response,status: Literal['pending','same_person','different_person']|None=None,page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=100),actor=Depends(require_staff)):
    """API033：只列共享线索，不把部门私有结果加入去重列表。"""
    response.headers['Cache-Control']='private, no-store'
    data=DuplicateService(request.app.state.identity.uow_factory).list_cases(actor,DuplicateQuery(status=status,page=page,page_size=page_size))
    return ApiEnvelope(data=data,request_id=request.state.request_id)


@router.post('/{case_id}/resolve',response_model=ApiEnvelope[MergeResult])
def resolve(cmd: MergeDecision,request: Request,response: Response,case_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API034：版本冲突、权限和活动考试预检失败都不得部分合并。"""
    response.headers['Cache-Control']='private, no-store'
    data=DuplicateService(request.app.state.identity.uow_factory).resolve(actor,case_id,cmd,expected_version(if_match))
    return ApiEnvelope(data=data,request_id=request.state.request_id)
