from datetime import datetime,timedelta,timezone
import hashlib,json
from uuid import uuid4
from sqlalchemy import select,func,update
from app.ai_runtime.admin_base import AiAdminBase
from app.ai_runtime.models import WorkflowConfig
from app.core.errors import DomainError
from app.core.idempotency import IdempotencyService,ResultRef
from app.core.types import TaskAccepted
from app.notifications.models import MailConfig,Notification
from app.notifications.policy import MailPolicy
from app.runtime.job_service import BackgroundJobService,JobSpec
from app.runtime.models import OutboxEvent
from app.notifications.schemas import MaskedMailConfig

def mail_view(row):
    return MaskedMailConfig(id=str(row.id),revision_no=row.revision_no,smtp_host=row.smtp_host,smtp_port=row.smtp_port,tls_mode=row.tls_mode,
        sender_address=row.sender_address,username_configured=bool(row.username),secret_configured=bool(row.secret_ciphertext),public_base_url=row.public_base_url,state=row.state,version=row.row_version)

def halt_pending(session,config_id):
    session.execute(update(Notification).where(Notification.mail_config_id==config_id,Notification.status=='pending').values(
        status='failed',last_error_code='MAIL_CONFIG_DISABLED',row_version=Notification.row_version+1))

class MailConfigService(AiAdminBase):
    def __init__(self,uow_factory,cipher,settings,idempotency_key=None):
        super().__init__(uow_factory);self.cipher=cipher;self.settings=settings;self.key=idempotency_key

    def _execute(self,actor,operation,payload,command):
        if not self.key: raise DomainError('IDEMPOTENCY_KEY_REQUIRED',422,'此操作需要幂等键')
        with self.uow_factory() as uow: self.authorize(uow,actor,'mail_config.manage')
        def run(uow):
            fresh=self.authorize(uow,actor,'mail_config.manage')
            return command(uow,fresh)
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        return IdempotencyService(self.uow_factory).execute(actor,operation,self.key,digest,run)

    def get(self,actor,config_id):
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'mail_config.manage')
            row=uow.session.get(MailConfig,config_id)
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'邮件配置不存在')
            return mail_view(row)

    def create(self,actor,cmd):
        MailPolicy(self.settings).require(cmd.smtp_host,cmd.smtp_port,cmd.tls_mode,cmd.public_base_url)
        if cmd.secret and self.cipher is None: raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用')
        payload=cmd.model_dump(mode='json',exclude={'secret'})
        payload['secret_fingerprint']=self.cipher.fingerprint(cmd.secret.get_secret_value()) if cmd.secret else None
        def command(uow,fresh):
            list(uow.session.scalars(select(WorkflowConfig).order_by(WorkflowConfig.id).with_for_update()))
            revision=(uow.session.scalar(select(func.max(MailConfig.revision_no))) or 0)+1
            row=MailConfig(revision_no=revision,smtp_host=cmd.smtp_host,smtp_port=cmd.smtp_port,tls_mode=cmd.tls_mode,sender_address=str(cmd.sender_address),
                username=cmd.username,secret_ciphertext=self.cipher.encrypt(cmd.secret.get_secret_value()) if cmd.secret else None,public_base_url=cmd.public_base_url.rstrip('/'),state='draft')
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'mail_config.create','mail_config',row.id,{'revision':revision})
            return ResultRef('mail_config',row.id,201)
        result=self._execute(actor,'mail_config.create',payload,command)
        return self.get(actor,result.entity_id)

    def test(self,actor,config_id: int,recipient: str):
        if self.cipher is None: raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用')
        def command(uow,fresh):
            row=uow.session.scalar(select(MailConfig).where(MailConfig.id==config_id).with_for_update())
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'邮件配置不存在')
            if row.state=='disabled': raise DomainError('MAIL_CONFIG_DISABLED',409,'已停用配置不能新增发送，请创建新修订')
            MailPolicy(self.settings).require(row.smtp_host,row.smtp_port,row.tls_mode,row.public_base_url)
            job_id=BackgroundJobService().enqueue(uow,JobSpec('mail.test','mail_config',config_id,'mail-test:'+uuid4().hex,{'mail_config_id':config_id}))
            expires=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(minutes=10)
            uow.session.add(OutboxEvent(event_type='mail.test.payload',aggregate_type='background_job',aggregate_id=job_id,event_key='mail-test:'+str(job_id),payload_refs={'mail_config_id':config_id},
                private_payload_ciphertext=self.cipher.encrypt(json.dumps({'recipient':recipient})),expires_at=expires,state='pending'))
            self.audit(uow,fresh,'mail_config.test','mail_config',config_id,{'source_id':job_id})
            return ResultRef('background_job',job_id,202)
        result=self._execute(actor,'mail_config.test',{'config_id':config_id,'recipient_fingerprint':self.cipher.fingerprint(recipient)},command)
        return TaskAccepted(task_id=str(result.entity_id),state='queued',poll_url='/api/v1/admin/runtime?task_id='+str(result.entity_id))

    def _change(self,actor,config_id,expected_version,reason,activate):
        if not reason.strip(): raise DomainError('REASON_REQUIRED',422,'原因不可为空')
        def command(uow,fresh):
            list(uow.session.scalars(select(WorkflowConfig).order_by(WorkflowConfig.id).with_for_update()))
            rows=list(uow.session.scalars(select(MailConfig).order_by(MailConfig.id).with_for_update()))
            target=next((r for r in rows if r.id==config_id),None)
            if target is None: raise DomainError('RESOURCE_NOT_FOUND',404,'邮件配置不存在')
            if target.row_version!=expected_version: raise DomainError('VERSION_CONFLICT',409,'邮件配置已更新')
            if activate:
                if target.state not in {'verified','active'}: raise DomainError('MAIL_CONFIG_NOT_VERIFIED',409,'邮件配置尚未通过实际测试')
                MailPolicy(self.settings).require(target.smtp_host,target.smtp_port,target.tls_mode,target.public_base_url)
                for row in rows:
                    if row.id!=target.id and row.state=='active': row.state='disabled';halt_pending(uow.session,row.id)
                target.state='active'
            else:
                target.state='disabled';halt_pending(uow.session,target.id)
            self.audit(uow,fresh,'mail_config.activate' if activate else 'mail_config.disable','mail_config',config_id,{'reason':reason,'state':target.state})
            return ResultRef('mail_config',config_id,200)
        result=self._execute(actor,'mail_config.activate' if activate else 'mail_config.disable',{'id':config_id,'version':expected_version,'reason':reason},command)
        return self.get(actor,result.entity_id)

    def activate(self,actor,config_id,expected_version,reason): return self._change(actor,config_id,expected_version,reason,True)
    def disable(self,actor,config_id,expected_version,reason): return self._change(actor,config_id,expected_version,reason,False)
