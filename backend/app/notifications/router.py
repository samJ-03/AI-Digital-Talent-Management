from fastapi import APIRouter,Depends,Header,Path,Request,Response
from app.ai_runtime.router import envelope
from app.core.secrets import SecretCipher
from app.core.types import ApiEnvelope,TaskAccepted
from app.identity.router import require_staff_write,expected_version
from app.notifications.config_service import MailConfigService
from app.notifications.schemas import MailConfigWrite,MaskedMailConfig,TestRecipient,MailAction

class MailRuntime:
    def __init__(self,uow_factory,settings):
        self.uow_factory=uow_factory;self.settings=settings
        self.cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings.encryption_key else None
    def service(self,key): return MailConfigService(self.uow_factory,self.cipher,self.settings,key)

router=APIRouter(prefix='/api/v1/admin')

@router.post('/mail-configs',status_code=201,response_model=ApiEnvelope[MaskedMailConfig])
def create_mail_config(cmd: MailConfigWrite,request: Request,response: Response,idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.mail_runtime.service(idempotency_key).create(actor,cmd),response)

@router.post('/mail-configs/{config_id}/test',status_code=202,response_model=ApiEnvelope[TaskAccepted])
def test_mail_config(cmd: TestRecipient,request: Request,config_id: int=Path(gt=0),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.mail_runtime.service(idempotency_key).test(actor,config_id,str(cmd.test_recipient)))

@router.post('/mail-configs/{config_id}/activate',response_model=ApiEnvelope[MaskedMailConfig])
def activate_mail_config(cmd: MailAction,request: Request,response: Response,config_id: int=Path(gt=0),if_match: str|None=Header(default=None),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.mail_runtime.service(idempotency_key).activate(actor,config_id,expected_version(if_match),cmd.reason),response)

@router.post('/mail-configs/{config_id}/disable',response_model=ApiEnvelope[MaskedMailConfig])
def disable_mail_config(cmd: MailAction,request: Request,response: Response,config_id: int=Path(gt=0),if_match: str|None=Header(default=None),idempotency_key: str|None=Header(default=None),actor=Depends(require_staff_write)):
    return envelope(request,request.app.state.mail_runtime.service(idempotency_key).disable(actor,config_id,expected_version(if_match),cmd.reason),response)
