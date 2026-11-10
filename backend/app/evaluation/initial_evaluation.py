"""首次评估恢复：用持久Outbox等待邮箱、去重及当前事实画像。"""
from datetime import timedelta
from sqlalchemy import select,exists
from app.core.clock import Clock
from app.core.access import ActorContext,ResourceScope
from app.core.errors import DomainError
from app.core.uow import make_uow
from app.evaluation.service import EvaluationService
from app.evaluation.models import EvaluationRun
from app.recruitment.models import Application
from app.jobs.models import Job
from app.runtime.models import OutboxEvent
from app.runtime.job_service import utc_naive


def request_initial(uow,application_id):
    """与建档同一事务写入引用事件，每关系只有一个首次事件。"""
    key=f'application-initial:{application_id}'
    if uow.session.scalar(select(OutboxEvent.id).where(OutboxEvent.event_key==key)) is None:
        uow.session.add(OutboxEvent(event_type='application.evaluate.requested',aggregate_type='application',aggregate_id=application_id,event_key=key,payload_refs={'application_id':application_id},state='pending',next_attempt_at=utc_naive(Clock().now())))

class InitialEvaluation:
    """只恢复从未有评估的有效关系，不把历史重评变成自动邀请。"""
    def __init__(self,uow_factory=make_uow):
        self.uow_factory=uow_factory;self.service=EvaluationService(uow_factory)

    def recover_legacy(self,limit=100):
        """补齐旧建档关系的首次事件；已有运行历史不再触发。"""
        with self.service.candidates.identity_write(),self.uow_factory() as uow:
            ids=list(uow.session.scalars(select(Application.id).where(Application.relationship_state=='active',Application.stage=='evaluating',Application.current_evaluation_id.is_(None),~exists(select(EvaluationRun.id).where(EvaluationRun.application_id==Application.id)),~exists(select(OutboxEvent.id).where(OutboxEvent.event_type=='application.evaluate.requested',OutboxEvent.aggregate_id==Application.id))).order_by(Application.id).limit(limit)))
            for aid in ids:request_initial(uow,aid)
            uow.commit();return len(ids)

    def consume_due(self,limit=100):
        """受阻事件退避，避免挡住其他人才；不进行外部模型或邮件I/O。"""
        count=0;now=utc_naive(Clock().now())
        with self.service.candidates.identity_write(),self.uow_factory() as uow:
            events=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='application.evaluate.requested',OutboxEvent.state=='pending',OutboxEvent.next_attempt_at<=now).order_by(OutboxEvent.id).limit(limit).with_for_update(skip_locked=True)))
            for event in events:
                app=uow.session.get(Application,event.aggregate_id)
                if app is None or event.payload_refs!={'application_id':app.id} or app.relationship_state!='active' or app.canonical_application_id or app.ended_at or app.stage!='evaluating':event.state='cancelled';continue
                if uow.session.scalar(select(EvaluationRun.id).where(EvaluationRun.application_id==app.id).limit(1)):
                    event.state='sent';continue
                job=uow.session.get(Job,app.job_id)
                if job is None or job.status=='closed':event.state='cancelled';continue
                try:
                    actor=ActorContext('hr',user_id=job.owner_hr_id)
                    self.service.authorize(uow,actor,'evaluation.write',ResourceScope('application',id=app.id,department_id=job.department_id))
                    self.service.create_snapshot(uow,actor,app,'auto_allowed','system-initial')
                    self.service.audit(uow,ActorContext('system'),'evaluation.initial','application',app.id,{'changed_fields':['current_evaluation_id']})
                    event.state='sent';count+=1
                except DomainError:
                    event.next_attempt_at=now+timedelta(seconds=30)
            uow.commit()
        return count
