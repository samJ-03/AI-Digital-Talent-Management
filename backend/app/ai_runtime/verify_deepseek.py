"""Local synthetic DeepSeek official capability check; no candidate data."""
import json
from sqlalchemy import select
from app.ai_runtime.config_service import ModelConfigService
from app.ai_runtime.capability_probe import CapabilityProbe
from app.ai_runtime.schemas import ModelConfigCreate
from app.core.secrets import SecretCipher
from app.core.settings import Settings
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user

def main():
    """执行本模块声明的命令行入口。"""
    settings=Settings.load()
    if settings.environment!='dev': raise RuntimeError('Local capability probe only')
    if not settings.deepseek_api_key or not settings.encryption_key:
        print(json.dumps({'ready':False,'error_code':'LOCAL_CREDENTIAL_NOT_CONFIGURED'}));return 1
    with make_uow() as uow:
        user=uow.session.scalar(select(User).where(User.login_name=='admin'))
        if user is None: raise RuntimeError('Local administrator missing')
        actor=resolve_user(uow.session,user)
    service=ModelConfigService(make_uow,SecretCipher(settings.encryption_key.get_secret_value()),CapabilityProbe())
    cfg=service.create_revision(actor,ModelConfigCreate(logical_key='deepseek-flash',provider_type='compatible_http',base_url='https://api.deepseek.com/v1',model_name='deepseek-flash',secret=settings.deepseek_api_key))
    result=service.test(actor,int(cfg.id))
    print(json.dumps({'ready':result.verified,'config_id':cfg.id,'requested_model':'deepseek-flash','official_endpoint':True,'json_verified':result.capabilities.get('json') is True,'returned_model':result.capabilities.get('returned_model'),'error_code':result.error_code,'synthetic_input_only':True}))
    return 0 if result.verified else 1

if __name__=='__main__': raise SystemExit(main())
