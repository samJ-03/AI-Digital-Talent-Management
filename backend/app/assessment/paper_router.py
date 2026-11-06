"""题库、试卷与考试：实现paper router领域协作。"""
from fastapi import APIRouter,Depends,Header,Path,Request,Response
from app.core.types import ApiEnvelope
from app.identity.router import require_staff,require_staff_write,expected_version
from app.assessment.schemas import QuestionBankCreate,QuestionDraft,ReviseQuestion,ReasonCommand,PaperCreate,PaperVersionDraft,QuestionBankView,QuestionView,PaperView,PaperVersionView
from app.assessment.question_service import QuestionService
from app.assessment.paper_service import PaperService

router=APIRouter(prefix='/api/v1')

def service(request,cls,key=None):
    """从当前HTTP请求构造领域服务。"""
    return cls(request.app.state.identity.uow_factory,key)

def envelope(request,response,value):
    """封装标准响应和请求链路标识。"""
    response.headers['ETag']='"'+str(value.version)+'"'
    response.headers['Cache-Control']='private, no-store'
    return ApiEnvelope(data=value,request_id=request.state.request_id)

@router.post('/question-banks',status_code=201,response_model=ApiEnvelope[QuestionBankView])
def create_bank(cmd: QuestionBankCreate,request: Request,response: Response,idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """创建当前授权部门的题库。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,QuestionService,idempotency_key).create_bank(actor,cmd))

@router.post('/questions',status_code=201,response_model=ApiEnvelope[QuestionView])
def create_question(cmd: QuestionDraft,request: Request,response: Response,idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：创建question，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,QuestionService,idempotency_key).create(actor,cmd))

@router.post('/questions/{question_id}/revisions',status_code=201,response_model=ApiEnvelope[QuestionView])
def revise_question(cmd: ReviseQuestion,request: Request,response: Response,question_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：修订question，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    draft=QuestionDraft.model_validate(cmd.model_dump(exclude={'reason'}))
    return envelope(request,response,service(request,QuestionService,idempotency_key).revise(actor,question_id,draft,cmd.reason))

@router.post('/questions/{question_id}/approve',response_model=ApiEnvelope[QuestionView])
def approve_question(cmd: ReasonCommand,request: Request,response: Response,question_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：批准question，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,QuestionService,idempotency_key).approve(actor,question_id,cmd.reason))

@router.post('/papers',status_code=201,response_model=ApiEnvelope[PaperView])
def create_paper(cmd: PaperCreate,request: Request,response: Response,idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：创建paper，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,PaperService,idempotency_key).create(actor,cmd))

@router.post('/papers/{paper_id}/versions',status_code=201,response_model=ApiEnvelope[PaperVersionView])
def draft_paper(cmd: PaperVersionDraft,request: Request,response: Response,paper_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：起草paper，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,PaperService,idempotency_key).draft_version(actor,paper_id,cmd))

@router.patch('/paper-versions/{version_id}',response_model=ApiEnvelope[PaperVersionView])
def edit_paper(cmd: PaperVersionDraft,request: Request,response: Response,version_id: int=Path(gt=0),if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：编辑paper，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,PaperService).edit_draft(actor,version_id,cmd,expected_version(if_match)))

@router.get('/paper-versions/{version_id}',response_model=ApiEnvelope[PaperVersionView])
def get_paper_version(request: Request,response: Response,version_id: int=Path(gt=0),actor=Depends(require_staff)):
    """HTTP入口：读取paper version，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,PaperService).get_version(actor,version_id))

@router.post('/paper-versions/{version_id}/publish',response_model=ApiEnvelope[PaperVersionView])
def publish_paper(cmd: ReasonCommand,request: Request,response: Response,version_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    """HTTP入口：发布paper，依赖当前请求的认证与字段校验。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
    return envelope(request,response,service(request,PaperService,idempotency_key).publish(actor,version_id,cmd.reason))
