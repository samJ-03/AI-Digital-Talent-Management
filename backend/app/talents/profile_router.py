"""画像HTTP入口：共享事实读取、受控人工新版本与禁缓存。"""
from fastapi import APIRouter,Depends,Header,Path,Query,Request,Response
from app.identity.router import require_staff,require_staff_write
from app.core.types import ApiEnvelope
from app.talents.profile_schemas import ProfileRevision,ProfileView
from app.talents.profile_service import ProfileService

router=APIRouter(prefix='/api/v1/talents')


def envelope(request,response,value):
    """响应可能含授权私有记录，禁止浏览器共享缓存。"""
    response.headers['Cache-Control']='private, no-store';response.headers['ETag']='"'+str(value.version)+'"'
    return ApiEnvelope(data=value,request_id=request.state.request_id)


@router.get('/{candidate_id}/profile',response_model=ApiEnvelope[ProfileView])
def get_profile(request: Request,response: Response,candidate_id: int=Path(gt=0),version_id: int|None=Query(None,gt=0),actor=Depends(require_staff)):
    """API043：当前或历史画像，附加信息逐岗位按当前权限生成。"""
    return envelope(request,response,ProfileService(request.app.state.identity.uow_factory).get(actor,candidate_id,version_id))


@router.post('/{candidate_id}/profile-revisions',response_model=ApiEnvelope[ProfileView])
def revise_profile(cmd: ProfileRevision,request: Request,response: Response,candidate_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API044：人工编排完整简历事实，不覆盖原AI版本。"""
    return envelope(request,response,ProfileService(request.app.state.identity.uow_factory,idempotency_key=idempotency_key).revise(actor,candidate_id,cmd))
