"""HR人才修改接口：CSRF、CAS、幂等和敏感响应禁缓存。"""
from fastapi import APIRouter, Depends, Header, Path, Request, Response
from app.identity.router import require_staff_write, expected_version
from app.core.types import ApiEnvelope
from app.talents.candidate_service import CandidateService
from app.talents.schemas import ContactsPatch, ResumeCorrection, Command, TalentView, ResumeVersionView

router=APIRouter(prefix='/api/v1/talents')


def service(request,key=None):
    """复用当前应用事务工厂，不另建数据库配置。"""
    return CandidateService(request.app.state.identity.uow_factory,key)


def envelope(request,response,value):
    """返回版本ETag且禁止缓存联系方式和简历内容。"""
    response.headers['ETag']='"'+str(value.version)+'"'
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=value,request_id=request.state.request_id)


@router.patch('/{candidate_id}/contacts',response_model=ApiEnvelope[TalentView])
def contacts(cmd: ContactsPatch,request: Request,response: Response,candidate_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API029：HR补齐联系方式，格式有效并不表示邮箱控制权已核验。"""
    return envelope(request,response,service(request).update_contacts(actor,candidate_id,cmd,expected_version(if_match)))


@router.post('/{candidate_id}/resume-corrections',status_code=202,response_model=ApiEnvelope[ResumeVersionView])
def correction(cmd: ResumeCorrection,request: Request,response: Response,candidate_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API030：追加简历版本，ready时请求重建画像，不直接发信。"""
    return envelope(request,response,service(request,idempotency_key).correct_resume(actor,candidate_id,cmd))


@router.post('/{candidate_id}/archive',response_model=ApiEnvelope[TalentView])
def archive(cmd: Command,request: Request,response: Response,candidate_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """API035：CAS归档并保留历史。"""
    return envelope(request,response,service(request).archive(actor,candidate_id,cmd.reason,expected_version(if_match)))
