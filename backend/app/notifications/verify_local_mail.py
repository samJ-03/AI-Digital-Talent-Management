"""Local Mailpit-only end-to-end acceptance; never connects to enterprise SMTP."""
import json,time
from uuid import uuid4
import httpx
from sqlalchemy import select
from app.core.settings import Settings
from app.core.secrets import SecretCipher
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user
from app.notifications.config_service import MailConfigService
from app.notifications.schemas import MailConfigWrite
from app.notifications.models import MailConfig
from app.runtime.models import BackgroundJob

def main():
    """执行本模块声明的命令行入口。"""
    settings=Settings.load()
    if settings.environment!='dev': raise RuntimeError('Local Mailpit probe only')
    cipher=SecretCipher(settings.encryption_key.get_secret_value())
    with make_uow() as uow:
        user=uow.session.scalar(select(User).where(User.login_name=='admin'))
        if user is None: raise RuntimeError('Local administrator missing')
        actor=resolve_user(uow.session,user)
    service=lambda key:MailConfigService(make_uow,cipher,settings,key)
    cfg=service('local-mailpit-config-v1').create(actor,MailConfigWrite(smtp_host='mailpit',smtp_port=1025,tls_mode='none',sender_address='talent-local@example.com',public_base_url='http://localhost:13000'))
    recipient='local-probe-'+uuid4().hex+'@example.com'
    task=service(uuid4().hex).test(actor,int(cfg.id),recipient)
    deadline=time.monotonic()+45
    state='queued';code=None
    while time.monotonic()<deadline:
        with make_uow() as uow:
            job=uow.session.get(BackgroundJob,int(task.task_id));state=job.state;code=job.error_code
        if state in {'succeeded','failed'}: break
        time.sleep(1)
    received=False
    if state=='succeeded':
        messages=httpx.get('http://mailpit:8025/api/v1/messages',params={'limit':100},timeout=5,trust_env=False).json()['messages']
        received=any(m['Subject']=='AI Talent SMTP test '+task.task_id and any(to['Address']==recipient for to in m['To']) for m in messages)
        with make_uow() as uow: version=uow.session.get(MailConfig,int(cfg.id)).row_version
        cfg=service(uuid4().hex).activate(actor,int(cfg.id),version,'仅本地 Mailpit 测试配置验收，不代表企业SMTP送达')
    ready=state=='succeeded' and received and cfg.state=='active'
    print(json.dumps({'ready':ready,'config_id':cfg.id,'task_id':task.task_id,'task_state':state,'mailpit_received':received,'config_state':cfg.state,'error_code':code,'enterprise_smtp_used':False}))
    return 0 if ready else 1

if __name__=='__main__': raise SystemExit(main())
