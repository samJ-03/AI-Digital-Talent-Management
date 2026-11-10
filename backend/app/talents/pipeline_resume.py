"""同事务消费去重/联系人恢复事件，并幂等恢复旧未注册画像任务。"""
from sqlalchemy import select,or_,exists,func
from datetime import timedelta
from app.core.clock import Clock
from app.core.errors import DomainError
from app.core.uow import make_uow
from app.ai_runtime.models import WorkflowConfig,ModelConfig,PromptVersion
from app.runtime.models import BackgroundJob,OutboxEvent
from app.runtime.job_service import BackgroundJobService,JobSpec,utc_naive
from app.talents.models import Candidate
from app.talents.profile_schemas import ProfileOutput
from app.talents.profile_service import ProfileService
from app.talents.identity_resolver import CanonicalResolver
from app.talents.profile_jobs import active_profile_job


class PipelineResume:
    """只生产固定任务及引用，不调用模型；配置关闭时保留待处理事件。"""
    def __init__(self,uow_factory=make_uow,clock=None):
        self.uow_factory=uow_factory;self.clock=clock or Clock();self.profiles=ProfileService(uow_factory);self.tasks=BackgroundJobService(uow_factory)

    def _config(self,uow):
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='profile'))
        if flow is None or not flow.enabled:return None
        model=uow.session.get(ModelConfig,flow.model_config_id) if flow.model_config_id else None
        prompt=uow.session.get(PromptVersion,flow.prompt_version_id) if flow.prompt_version_id else None
        if model is None or not model.enabled or not all(model.capabilities.get(k) is True for k in ['verified','text','json']):return None
        if prompt is None or prompt.task_type!='profile' or prompt.status!='published' or prompt.output_schema!=ProfileOutput.model_json_schema():return None
        return flow

    def recover_legacy(self,limit=100):
        """旧缺处理器/配置失败可按新配置修订恢复一次，真实输出失败不自动复活。"""
        if not 1<=limit<=1000:raise ValueError('Invalid recovery limit')
        with self.profiles.candidates.identity_write(),self.uow_factory() as uow:
            config=self._config(uow)
            if config is None:return 0
            revision=config.config_revision
            key=func.concat('pipeline.resume:legacy:',BackgroundJob.id,':config:',str(revision))
            recorded=exists(select(OutboxEvent.id).where(OutboxEvent.event_key==key))
            stamp=BackgroundJob.input_refs['profile_revision'].as_integer()
            jobs=list(uow.session.scalars(select(BackgroundJob).where(BackgroundJob.job_type=='profile.build',BackgroundJob.entity_type=='candidate',BackgroundJob.state=='failed',BackgroundJob.error_code.in_(['HANDLER_NOT_REGISTERED','PROFILE_CONFIG_UNAVAILABLE']),or_(stamp.is_(None),stamp!=revision),~recorded).order_by(BackgroundJob.id).limit(limit).with_for_update(skip_locked=True)))
            for job in jobs:
                uow.session.add(OutboxEvent(event_type='pipeline.resume',aggregate_type='candidate',aggregate_id=job.entity_id,event_key=f'pipeline.resume:legacy:{job.id}:config:{revision}',payload_refs={'candidate_id':job.entity_id},state='pending'))
            uow.commit();return len(jobs)

    def consume_due(self,limit=100):
        """恢复事件与任务入队同事务，消费者重复调用不重复生成画像任务。"""
        if not 1<=limit<=1000:raise ValueError('Invalid consume limit')
        now=utc_naive(self.clock.now());handled=0
        with self.profiles.candidates.identity_write(),self.uow_factory() as uow:
            rows=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='pipeline.resume',OutboxEvent.state.in_(['pending','failed']),or_(OutboxEvent.next_attempt_at.is_(None),OutboxEvent.next_attempt_at<=now)).order_by(OutboxEvent.id).limit(limit).with_for_update(skip_locked=True)))
            config=self._config(uow)
            for event in rows:
                if event.aggregate_type!='candidate' or event.payload_refs!={'candidate_id':event.aggregate_id} or event.private_payload_ciphertext is not None:
                    event.state='cancelled';handled+=1;continue
                try:
                    identity=CanonicalResolver().resolve(uow,event.aggregate_id);row=uow.session.get(Candidate,identity.root_id)
                    if row.status=='archived' or row.current_resume_version_id is None:event.state='cancelled';handled+=1;continue
                    if row.status!='ready' or config is None:
                        event.next_attempt_at=now+timedelta(seconds=30);continue
                    current=self.profiles.current(uow,row.id,row.current_resume_version_id)
                    if current is None:
                        if active_profile_job(uow.session,row.id,row.current_resume_version_id) is None:self.tasks.enqueue(uow,JobSpec('profile.build','candidate',row.id,f'profile.build:{row.id}:{row.current_resume_version_id}:resume:{event.id}',{'candidate_id':row.id,'resume_version_id':row.current_resume_version_id,'profile_revision':config.config_revision}))
                    event.state='sent';event.next_attempt_at=None;handled+=1
                except DomainError as error:
                    if error.code=='PROFILE_NOT_READY':
                        event.next_attempt_at=now+timedelta(seconds=30);continue
                    event.state='cancelled';handled+=1
            uow.commit();return handled
