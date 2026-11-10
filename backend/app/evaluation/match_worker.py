"""T21固定匹配处理器与T19匹配事件交付；不持锁调用供应商。"""
from sqlalchemy import select
from app.core.uow import make_uow
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.runtime.models import OutboxEvent
from app.runtime.job_service import BackgroundJobService,JobSpec
from app.evaluation.models import EvaluationRun
from app.evaluation.match_service import MatchService

class MatchHandler:
    """prepare执行模型I/O，finalize复用有效任务租约事务。"""
    def __init__(self,service):self.service=service

    def finalization_context(self):
        """覆盖来源复验、匹配结果和任务提交。"""
        return self.service.evaluations.candidates.identity_write()

    def prepare(self,lease):
        """持久引用一致后才允许发起模型调用。"""
        with self.service.uow_factory() as uow:
            job=BackgroundJobService(self.service.uow_factory)._owned(uow,lease);refs=dict(job.input_refs);run=uow.session.get(EvaluationRun,refs.get('evaluation_id'))
            if run is None or job.job_type!='application.match' or job.entity_type!='application' or job.entity_id!=run.application_id or refs!={'evaluation_id':run.id}:raise DomainError('INVALID_OUTPUT',422,'匹配任务引用无效')
            run_id=run.id
        prepared=self.service.prepare(run_id)
        def finalize(uow,job):
            if job.input_refs!=refs:raise DomainError('INVALID_OUTPUT',422,'匹配任务引用已变化')
            result=self.service.finalize(uow,prepared);return ResultRef('match_result',int(result.id),200)
        return finalize

class MatchDispatch:
    """把T19引用事件可靠转换成持久任务，同run不重复调用。"""
    def __init__(self,uow_factory=make_uow):self.uow_factory=uow_factory;self.service=MatchService(uow_factory)

    def consume_due(self,limit=100):
        """模型未启用时保留事件，不把配置缺失当候选人不合格。"""
        from app.runtime.job_service import utc_naive
        from app.core.clock import Clock
        with self.service.evaluations.candidates.identity_write(),self.uow_factory() as uow:
            try:self.service._config(uow)
            except DomainError:return 0
            events=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='evaluation.match.requested',OutboxEvent.state=='pending',OutboxEvent.next_attempt_at<=utc_naive(Clock().now())).order_by(OutboxEvent.id).limit(limit).with_for_update(skip_locked=True)))
            count=0
            for event in events:
                run=uow.session.get(EvaluationRun,event.aggregate_id)
                if run is None or event.payload_refs!={'evaluation_id':run.id}:event.state='cancelled';continue
                try:self.service._eligible(uow,run)
                except DomainError:event.state='cancelled';continue
                BackgroundJobService(self.uow_factory).enqueue(uow,JobSpec('application.match','application',run.application_id,f'application-match:{run.id}',{'evaluation_id':run.id}))
                event.state='sent';count+=1
            uow.commit();return count
