"""平台开发工具：验证mail config的正常与失败场景；测试数据仅用于隔离环境。"""
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from sqlalchemy import select,delete
from tests.integration.test_identity import identity,login
from app.identity.models import Role,UserRole
from app.notifications.models import MailConfig
from app.runtime.models import BackgroundJob,OutboxEvent
from app.core.models import IdempotencyRecord

@pytest.fixture
def mail(identity):
    client,engine,uid,password,ids,*_=identity
    uows=client.app.state.identity.uow_factory
    with uows() as uow:
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==ids['admin']))
        role.permission_codes=sorted(set(role.permission_codes)|{'mail_config.manage','runtime.read'})
        uow.commit()
    if hasattr(client.app.state,'mail_runtime'):
        from cryptography.fernet import Fernet
        from app.core.secrets import SecretCipher
        client.app.state.mail_runtime.cipher=SecretCipher(Fernet.generate_key().decode())
    yield identity
    with uows() as uow:
        config_ids=list(uow.session.scalars(select(MailConfig.id).where(MailConfig.sender_address==uid+'@example.com')))
        job_ids=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='mail_config',BackgroundJob.entity_id.in_(config_ids))))
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_type=='background_job',OutboxEvent.aggregate_id.in_(job_ids)))
        uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(job_ids)))
        uow.session.execute(delete(MailConfig).where(MailConfig.id.in_(config_ids)))
        uow.session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.actor_scope=='admin:'+str(ids['admin'])))
        uow.commit()

def create(identity,headers):
    client,engine,uid,password,ids,*_=identity
    body={'smtp_host':'mailpit','smtp_port':1025,'tls_mode':'none','sender_address':uid+'@example.com','public_base_url':'http://localhost:13000'}
    response=client.post('/api/v1/admin/mail-configs',json=body,headers={**headers,'Idempotency-Key':uuid4().hex})
    assert response.status_code==201,response.text
    return response.json()['data']

def run_test_job(identity,task_id,adapter=None):
    from app.runtime.job_service import BackgroundJobService,JobRunner
    from app.notifications.test_handler import MailTestHandler
    runtime=identity[0].app.state.mail_runtime
    handler=MailTestHandler(identity[0].app.state.identity.uow_factory,runtime.cipher,runtime.settings,adapter)
    JobRunner(BackgroundJobService(identity[0].app.state.identity.uow_factory),{'mail.test':handler}).execute(int(task_id))

def queue_test(identity,headers,config_id):
    client,engine,uid,password,ids,*_=identity
    response=client.post('/api/v1/admin/mail-configs/'+config_id+'/test',json={'test_recipient':uid+'@example.com'},headers={**headers,'Idempotency-Key':uuid4().hex})
    assert response.status_code==202,response.text
    return response.json()['data']

def test_only_verified_config_active(mail):
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);cfg=create(mail,headers)
    response=client.post('/api/v1/admin/mail-configs/'+cfg['id']+'/activate',json={'reason':'activate'},headers={**headers,'If-Match':str(cfg['version']),'Idempotency-Key':uuid4().hex})
    assert response.status_code==409
    assert cfg['state']=='draft' and 'secret_ciphertext' not in cfg

def test_mailpit_actual_receive_and_frozen_revision(mail):
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);cfg=create(mail,headers);task=queue_test(mail,headers,cfg['id'])
    with client.app.state.identity.uow_factory() as uow:
        job=uow.session.get(BackgroundJob,int(task['task_id']))
        assert job.entity_id==int(cfg['id']) and job.input_refs['mail_config_id']==int(cfg['id'])
        event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key=='mail-test:'+task['task_id']))
        assert event.private_payload_ciphertext and uid+'@example.com' not in event.private_payload_ciphertext
    run_test_job(mail,task['task_id'])
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.get(MailConfig,int(cfg['id'])).state=='verified'
        assert uow.session.get(BackgroundJob,int(task['task_id'])).state=='succeeded'
        event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key=='mail-test:'+task['task_id']))
        assert event.private_payload_ciphertext is None and event.state=='sent'
    messages=httpx.get('http://mailpit:8025/api/v1/messages',params={'limit':100},timeout=5,trust_env=False).json()['messages']
    assert any(message['Subject']=='AI Talent SMTP test '+task['task_id'] and any(to['Address']==uid+'@example.com' for to in message['To']) for message in messages)

def test_activate_single_active_under_concurrency(mail):
    from app.notifications.config_service import MailConfigService
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);a=create(mail,headers);b=create(mail,headers)
    with client.app.state.identity.uow_factory() as uow:
        for cfg in (a,b): uow.session.get(MailConfig,int(cfg['id'])).state='verified'
        uow.commit()
    actor,_=client.app.state.identity.auth.require(client.cookies.get('talent_staff'))
    runtime=client.app.state.mail_runtime
    def activate(cfg):
        with client.app.state.identity.uow_factory() as uow: version=uow.session.get(MailConfig,int(cfg['id'])).row_version
        return MailConfigService(client.app.state.identity.uow_factory,runtime.cipher,runtime.settings,idempotency_key=uuid4().hex).activate(actor,int(cfg['id']),version,'concurrent test')
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(activate,(a,b)))
    with client.app.state.identity.uow_factory() as uow:
        active=list(uow.session.scalars(select(MailConfig).where(MailConfig.id.in_([int(a['id']),int(b['id'])]),MailConfig.state=='active')))
        assert len(active)==1

def test_unknown_delivery_never_automatically_resends(mail):
    from app.notifications.smtp_adapter import DeliveryResult
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);cfg=create(mail,headers);task=queue_test(mail,headers,cfg['id'])
    class Unknown:
        calls=0
        def send(self,*args):
            self.calls+=1
            return DeliveryResult('unknown',None,'SMTP_DELIVERY_UNKNOWN')
    adapter=Unknown()
    run_test_job(mail,task['task_id'],adapter)
    run_test_job(mail,task['task_id'],adapter)
    assert adapter.calls==1
    with client.app.state.identity.uow_factory() as uow:
        job=uow.session.get(BackgroundJob,int(task['task_id']))
        assert job.state=='failed' and job.error_code=='SMTP_DELIVERY_UNKNOWN'
        assert uow.session.get(MailConfig,int(cfg['id'])).state=='draft'

def test_disabled_queued_config_test_does_not_send(mail):
    from app.notifications.smtp_adapter import DeliveryResult
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);cfg=create(mail,headers);task=queue_test(mail,headers,cfg['id'])
    response=client.post('/api/v1/admin/mail-configs/'+cfg['id']+'/disable',json={'reason':'stop'},headers={**headers,'If-Match':str(cfg['version']),'Idempotency-Key':uuid4().hex})
    assert response.status_code==200,response.text
    class Forbidden:
        def send(self,*args): pytest.fail('disabled config sent a message')
    run_test_job(mail,task['task_id'],Forbidden())
    with client.app.state.identity.uow_factory() as uow: assert uow.session.get(BackgroundJob,int(task['task_id'])).state=='failed'

def test_mail_host_and_tls_policy_fail_closed(mail):
    client,engine,uid,password,ids,*_=mail
    headers=login(mail)
    body={'smtp_host':'169.254.169.254','smtp_port':1025,'tls_mode':'none','sender_address':uid+'@example.com','public_base_url':'http://localhost:13000'}
    response=client.post('/api/v1/admin/mail-configs',json=body,headers={**headers,'Idempotency-Key':uuid4().hex})
    assert response.status_code==422 and response.json()['code']=='SMTP_HOST_DENIED'


def test_crash_after_smtp_acceptance_becomes_unknown_without_resend(mail):
    from datetime import datetime,timedelta,timezone
    from app.notifications.smtp_adapter import DeliveryResult
    from app.notifications.test_handler import MailTestHandler
    from app.runtime.job_service import BackgroundJobService
    from app.runtime.scheduler import LeaseRecovery
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);cfg=create(mail,headers);task=queue_test(mail,headers,cfg['id'])
    runtime=client.app.state.mail_runtime;uows=client.app.state.identity.uow_factory
    class Accepted:
        calls=0
        def send(self,*args): self.calls+=1;return DeliveryResult('accepted','synthetic-id')
    adapter=Accepted();service=BackgroundJobService(uows)
    lease=service.claim(int(task['task_id']),'crashed-worker')
    MailTestHandler(uows,runtime.cipher,runtime.settings,adapter).prepare(lease)
    # Simulate a crash before the atomic finalize, then expire only this synthetic lease.
    with uows() as uow:
        uow.session.get(BackgroundJob,int(task['task_id'])).lease_until=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(seconds=1)
        uow.commit()
    LeaseRecovery(uows).requeue_expired(datetime.now(timezone.utc),100)
    run_test_job(mail,task['task_id'],adapter)
    assert adapter.calls==1
    with uows() as uow:
        job=uow.session.get(BackgroundJob,int(task['task_id']))
        assert job.state=='failed' and job.error_code=='SMTP_DELIVERY_UNKNOWN'

def test_switch_and_disable_preserve_notification_frozen_revision(mail):
    from app.notifications.models import Notification
    client,engine,uid,password,ids,*_=mail
    headers=login(mail);a=create(mail,headers);b=create(mail,headers)
    uows=client.app.state.identity.uow_factory
    with uows() as uow:
        for cfg in (a,b): uow.session.get(MailConfig,int(cfg['id'])).state='verified'
        uow.commit()
    def activate(cfg):
        with uows() as uow: version=uow.session.get(MailConfig,int(cfg['id'])).row_version
        response=client.post('/api/v1/admin/mail-configs/'+cfg['id']+'/activate',json={'reason':'switch test'},headers={**headers,'If-Match':str(version),'Idempotency-Key':uuid4().hex})
        assert response.status_code==200,response.text
    activate(a)
    notification_id=None
    try:
        with uows() as uow:
            row=Notification(event_key='synthetic:'+uid,purpose='exam_invite',recipient_snapshot=uid+'@example.com',mail_config_id=int(a['id']),status='pending')
            uow.session.add(row);uow.session.flush();notification_id=row.id;uow.commit()
        activate(b)
        with uows() as uow:
            row=uow.session.get(Notification,notification_id)
            assert row.mail_config_id==int(a['id']) and row.status=='failed' and row.last_error_code=='MAIL_CONFIG_DISABLED'
    finally:
        if notification_id:
            with uows() as uow: uow.session.execute(delete(Notification).where(Notification.id==notification_id));uow.commit()
