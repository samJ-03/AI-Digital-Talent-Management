"""T20语义搜索与岗位推荐HTTP入口，无招聘写副作用。"""
from fastapi import APIRouter,Depends,Path,Query,Request,Response
from app.identity.router import require_staff,require_staff_write
from app.core.types import ApiEnvelope
from app.search.schemas import TalentSearchQuery,TalentFilter,SemanticSearchResult,Recommendation
from app.search.talent_search import TalentSearchService
router=APIRouter(prefix='/api/v1')

def service(request):
    """可注入测试服务，生产默认使用当前事务工厂和受控设置。"""
    return getattr(request.app.state,'talent_search',None) or TalentSearchService(request.app.state.identity.uow_factory)

@router.post('/talents/search',response_model=ApiEnvelope[SemanticSearchResult])
def search(cmd: TalentSearchQuery,request: Request,response: Response,actor=Depends(require_staff_write)):
    """API032：自然语言找人，索引故障明确503。"""
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=service(request).search(actor,cmd),request_id=request.state.request_id)

@router.get('/jobs/{job_id}/recommendations',response_model=ApiEnvelope[list[Recommendation]])
def recommend(request: Request,response: Response,job_id: int=Path(gt=0),page_size: int=Query(20,ge=1,le=100),skills: list[str]=Query(default=[]),education: str|None=Query(None,max_length=100),major: str|None=Query(None,max_length=200),actor=Depends(require_staff)):
    """API036：只读推荐；GET不会补建索引或加入招聘。"""
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=service(request).recommend(actor,job_id,TalentFilter(skills=skills,education=education,major=major,page_size=page_size)),request_id=request.state.request_id)
