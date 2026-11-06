"""邮件配置与交付：处理本地邮件配置测试的准备与原子收尾。"""
import hashlib,json
from datetime import datetime,timezone
from sqlalchemy import select
from app.core.idempotency import ResultRef
from app.notifications.models import MailConfig
from app.notifications.policy import MailPolicy
from app.notifications.config_service import halt_pending
from app.notifications.smtp_adapter import SmtpAdapter,MailConnection,MailMessage,DeliveryResult
from app.runtime.job_service import BackgroundJobService,TerminalJobFailure,utc_naive
from app.runtime.models import OutboxEvent

class MailTestHandler:
    """Durable pre-send marker: a crash after SMTP starts becomes unknown, never an automatic resend."""
    def __init__(self,uow_factory,cipher,settings,adapter=None):
        self.uow_factory=uow_factory;self.cipher=cipher;self.settings=settings
        self.adapter=adapter or SmtpAdapter(cipher)

    def prepare(self,lease):
        """在原子收尾前准备外部I/O；不在长事务内等待供应商。"""
        connection=None;recipient=None;result=None;message_id=None
        with self.uow_factory() as uow:
            job=BackgroundJobService(self.uow_factory)._owned(uow,lease)
            message_id='<mail-test-'+str(job.id)+'-'+hashlib.sha256(job.idempotency_key.encode()).hexdigest()[:16]+'@talent.local>'
            event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key=='mail-test:'+str(job.id)).with_for_update())
            config=uow.session.get(MailConfig,job.entity_id)
            now=datetime.now(timezone.utc).replace(tzinfo=None)
            if config is None or config.state=='disabled': result=DeliveryResult('failed',None,'MAIL_CONFIG_DISABLED')
            elif event is None or event.state=='cancelled' or event.expires_at is None or event.expires_at<=now: result=DeliveryResult('failed',None,'MAIL_TEST_EXPIRED')
            elif event.state in {'processing','unknown'}: result=DeliveryResult('unknown',None,'SMTP_DELIVERY_UNKNOWN')
            elif event.state=='sent': result=DeliveryResult('accepted')
            elif event.state=='failed': result=DeliveryResult('failed',None,'SMTP_TEST_FAILED')
            else:
                MailPolicy(self.settings).require(config.smtp_host,config.smtp_port,config.tls_mode,config.public_base_url)
                if self.cipher is None or not event.private_payload_ciphertext: result=DeliveryResult('failed',None,'MAIL_TEST_EXPIRED')
                else:
                    recipient=json.loads(self.cipher.decrypt(event.private_payload_ciphertext))['recipient']
                    connection=MailConnection(config.id,config.smtp_host,config.smtp_port,config.tls_mode,config.sender_address,config.username,config.secret_ciphertext)
                    event.state='processing';event.lease_until=utc_naive(lease.lease_until)
                    uow.commit()
        if connection is not None:
            result=self.adapter.send(connection,MailMessage(recipient,'AI Talent SMTP test '+str(lease.job_id),'本地邮件配置连通性测试，不是招聘邀请。',message_id))
        def finalize(uow,job):
            event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key=='mail-test:'+str(job.id)).with_for_update())
            config=uow.session.scalar(select(MailConfig).where(MailConfig.id==job.entity_id).with_for_update())
            if event:
                event.private_payload_ciphertext=None;event.lease_until=None
                event.state='sent' if result.status=='accepted' else ('unknown' if result.status=='unknown' else 'failed')
            if config is None or config.state=='disabled': return TerminalJobFailure('MAIL_CONFIG_DISABLED')
            if result.status=='accepted':
                if config.state!='active': config.state='verified'
                return ResultRef('mail_config',config.id,200)
            if config.state=='active':
                config.state='disabled';halt_pending(uow.session,config.id)
            elif config.state!='disabled': config.state='draft'
            return TerminalJobFailure('SMTP_DELIVERY_UNKNOWN' if result.status=='unknown' else (result.error_code if result.error_code in {'MAIL_TEST_EXPIRED','MAIL_CONFIG_DISABLED'} else 'SMTP_TEST_FAILED'))
        return finalize
