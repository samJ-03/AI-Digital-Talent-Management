from fastapi import APIRouter,Depends,Header,Path,Request,Response
from app.core.secrets import SecretCipher
from app.core.types import ApiEnvelope
from app.ai_runtime.capability_probe import CapabilityProbe
from app.ai_runtime.config_service import ModelConfigService,WorkflowConfigService
from app.ai_runtime.prompt_service import PromptService
from app.ai_runtime.schemas import ModelConfigCreate,PromptCreate,PublishCommand,WorkflowWrite,TaskType,MaskedModelConfig,CapabilityTest,PromptView,WorkflowView
from app.identity.router import require_staff,require_staff_write,expected_version

class AiRuntime:
    def __init__(self,uow_factory,settings):
        self.uow_factory=uow_factory
        self.cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings.encryption_key else None
        self.probe=CapabilityProbe()
    def models(self): return ModelConfigService(self.uow_factory,self.cipher,self.probe)
    def prompts(self,key=None): return PromptService(self.uow_factory,key)
    def workflows(self): return WorkflowConfigService(self.uow_factory)

router=APIRouter(prefix='/api/v1/admin')

def envelope(request,value,response=None):
    if response is not None and hasattr(value,'version'): response.headers['ETag']='"'+str(value.version)+'"'
    return ApiEnvelope(data=value,request_id=request.state.request_id)

@router.post('/model-configs',status_code=201,response_model=ApiEnvelope[MaskedModelConfig])
def create_model_config(cmd: ModelConfigCreate,request: Request,response: Response,actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.ai_runtime.models().create_revision(actor,cmd),response)

@router.post('/model-configs/{config_id}/test',response_model=ApiEnvelope[CapabilityTest])
def test_model_config(request: Request,config_id: int=Path(gt=0),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.ai_runtime.models().test(actor,config_id))

@router.get('/workflows',response_model=ApiEnvelope[list[WorkflowView]])
def get_workflows(request: Request,actor=Depends(require_staff)):
    return envelope(request,request.app.state.ai_runtime.workflows().list(actor))

@router.put('/workflows/{task_type}',response_model=ApiEnvelope[WorkflowView])
def configure_workflow(task_type: TaskType,cmd: WorkflowWrite,request: Request,response: Response,if_match: str|None=Header(default=None),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.ai_runtime.workflows().configure(actor,task_type,cmd,expected_version(if_match)),response)

@router.post('/prompts',status_code=201,response_model=ApiEnvelope[PromptView])
def create_prompt(cmd: PromptCreate,request: Request,response: Response,actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.ai_runtime.prompts().create(actor,cmd),response)

@router.post('/prompts/{prompt_id}/publish',response_model=ApiEnvelope[PromptView])
def publish_prompt(cmd: PublishCommand,request: Request,response: Response,prompt_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.ai_runtime.prompts(idempotency_key).publish(actor,prompt_id,cmd.reason),response)
