"""Local-only authorized synthetic DashScope capability probe."""
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
    if settings.environment!='dev': raise RuntimeError('Local probe only')
    if not settings.dashscope_api_key or not settings.encryption_key:
        print(json.dumps({'ready':False,'error_code':'LOCAL_CREDENTIAL_NOT_CONFIGURED'}));return 1
    with make_uow() as uow:
        user=uow.session.scalar(select(User).where(User.login_name=='admin'))
        if user is None: raise RuntimeError('Local administrator account missing')
        actor=resolve_user(uow.session,user)
    service=ModelConfigService(make_uow,SecretCipher(settings.encryption_key.get_secret_value()),CapabilityProbe())
    row=service.create_revision(actor,ModelConfigCreate(logical_key='dashscope-embedding',provider_type='compatible_http',
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',model_name='text-embedding-v3',embedding_dimension=1024,secret=settings.dashscope_api_key))
    tested=service.test(actor,int(row.id))
    print(json.dumps({'ready':tested.verified,'config_id':row.id,'model':'text-embedding-v3','embedding_dimension':tested.embedding_dimension,
        'model_digest_available':tested.model_digest is not None,'error_code':tested.error_code,'synthetic_inputs_only':True,'llm_called':False}))
    return 0 if tested.verified else 1

if __name__=='__main__': raise SystemExit(main())
