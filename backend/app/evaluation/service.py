"""评估应用服务：版本快照、确定性粗筛、迟到保护与有理由人工覆盖。"""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.hr_service import HrServiceBase
from app.core.access import ActorContext,ResourceScope
from app.core.clock import Clock
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user
from app.jobs.models import Job,JobVersion
from app.recruitment.models import Application,RecruitmentEvent
from app.talents.models import Candidate,ResumeVersion,CandidateProfile
from app.talents.candidate_service import CandidateService
from app.talents.identity_resolver import CanonicalResolver
from app.talents.profile_service import ProfileService
from app.evaluation.models import EvaluationRun,ScreeningDetail,MatchResult
from app.evaluation.rules import ScreeningEngine
from app.ingestion.extraction_types import ResumeFacts
from app.evaluation.api_schemas import EvaluationView,EvaluationDetail,EvaluationAccepted
from app.runtime.models import BackgroundJob,OutboxEvent
from app.runtime.job_service import BackgroundJobService,JobSpec,utc_naive


def fingerprint(value):
    """只存内容摘要，避免在上下文重复保存原始履历。"""
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()


class EvaluationService(HrServiceBase):
    """命令拥有事务；筛选回调复用worker租约事务且不提交。"""
    def __init__(self,uow_factory=make_uow,idempotency_key=None):
        super().__init__(uow_factory,idempotency_key)
        self.candidates=CandidateService(uow_factory);self.profiles=ProfileService(uow_factory)

    def _scope(self,uow,application_id):
        app=uow.session.get(Application,application_id)
        job=uow.session.get(Job,app.job_id) if app else None
        if job is None:raise DomainError('RESOURCE_NOT_FOUND',404,'应聘关系不存在')
        return ResourceScope('application',id=application_id,department_id=job.department_id)

    def _sources(self,uow,app,requested_resume=None):
        if app.relationship_state!='active' or app.canonical_application_id or app.stage in {'hired','rejected','withdrawn'} or app.ended_at:
            raise DomainError('APPLICATION_NOT_ACTIVE',409,'应聘关系不可继续评估')
        identity=CanonicalResolver().resolve(uow,app.candidate_id,True)
        candidate=uow.session.get(Candidate,identity.root_id)
        rid=candidate.current_resume_version_id
        if not rid or requested_resume is not None and requested_resume!=rid:raise DomainError('EVALUATION_SOURCE_STALE',409,'只能评估当前简历和画像')
        profile=self.profiles.current(uow,candidate.id,rid)
        if profile is None:raise DomainError('PROFILE_NOT_READY',409,'需先完成当前简历的事实画像')
        job=uow.session.scalar(select(Job).where(Job.id==app.job_id).with_for_update().execution_options(populate_existing=True))
        version=uow.session.get(JobVersion,job.current_version_id) if job.current_version_id else None
        if job.status!='open' or version is None or version.job_id!=job.id or version.status!='published':raise DomainError('JOB_NOT_READY',409,'岗位未开放或缺少发布标准')
        resume=uow.session.get(ResumeVersion,rid)
        return candidate,resume,profile,job,version

    def _hashes(self,resume,profile,version):
        return {'resume':fingerprint([resume.id,resume.structured_data,resume.field_sources]),'profile':fingerprint([profile.id,profile.summary,profile.skills,profile.experiences,profile.evidence,profile.source_record_refs,profile.ai_run_id,profile.confirmed_by]),'job':fingerprint([version.id,version.description,version.conditions,version.match_weights,version.invite_threshold,version.paper_version_id,version.invite_valid_hours,version.mail_template])}

    def create_snapshot(self,uow,actor,app,mode,initiated_by,requested_resume=None):
        """在调用方事务冻结来源并保存任务；不执行模型、不发邀请。"""
        candidate,resume,profile,job,version=self._sources(uow,app,requested_resume)
        self.authorize(uow,actor,'evaluation.write',ResourceScope('application',id=app.id,department_id=job.department_id))
        context={'as_of':Clock().now().astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat(),'normalization_revision':'screening-core-v1','dictionary_revision':'core-major-v1','relevant_employment_indices':None,'source_hashes':self._hashes(resume,profile,version),'initiator_user_id':actor.user_id,'initiated_by':initiated_by}
        run=EvaluationRun(application_id=app.id,resume_version_id=resume.id,profile_id=profile.id,job_version_id=version.id,state='pending',invitation_mode=mode,screening_context=context)
        uow.session.add(run);uow.session.flush();app.current_evaluation_id=run.id
        tid=BackgroundJobService(self.uow_factory).enqueue(uow,JobSpec('application.evaluate','application',app.id,f'evaluation:{run.id}',{'evaluation_id':run.id,'candidate_id':candidate.id,'job_id':job.id,'resume_version_id':resume.id,'profile_id':profile.id,'job_version_id':version.id}))
        return run,tid

    def start(self,actor,application_id,cmd):
        """人工重评只切换当前评估，不重置阶段、轮次或既有考试。"""
        with self.candidates.identity_write():
            with self.uow_factory() as uow:scope=self._scope(uow,application_id)
            def command(uow,fresh):
                app=uow.session.scalar(select(Application).where(Application.id==application_id).with_for_update())
                run,tid=self.create_snapshot(uow,fresh,app,'manual_only','hr-reevaluate',cmd.resume_version_id)
                self.audit(uow,fresh,'evaluation.start','application',app.id,{'reason':cmd.reason,'source_id':run.id})
                return ResultRef('evaluation',run.id,202)
            ref=self.execute(actor,'evaluation.write',scope,'evaluation.start',{'application_id':application_id,**cmd.model_dump()},command,'evaluation.read')
            with self.uow_factory() as uow:
                self.authorize(uow,actor,'evaluation.read',self._scope(uow,application_id))
                tid=uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.idempotency_key==f'evaluation:{ref.entity_id}'))
                return EvaluationAccepted(evaluation_id=str(ref.entity_id),task_id=str(tid),state='queued',poll_url=f'/api/v1/tasks/{tid}')

    def _current(self,uow,run):
        app=uow.session.get(Application,run.application_id)
        if app is None or app.current_evaluation_id!=run.id:return False
        try:
            _,resume,profile,_,version=self._sources(uow,app)
            return (resume.id,profile.id,version.id)==(run.resume_version_id,run.profile_id,run.job_version_id) and self._hashes(resume,profile,version)==run.screening_context.get('source_hashes')
        except DomainError:return False

    def _view(self,uow,run):
        return EvaluationView(id=str(run.id),application_id=str(run.application_id),resume_version_id=str(run.resume_version_id),profile_id=str(run.profile_id),job_version_id=str(run.job_version_id),state=run.state,screening_result=run.screening_result,invitation_mode=run.invitation_mode,is_current=self._current(uow,run),error_code=run.error_code)

    def _match_request(self,uow,run):
        key=f'evaluation-match:{run.id}'
        if uow.session.scalar(select(OutboxEvent.id).where(OutboxEvent.event_key==key)) is None:
            uow.session.add(OutboxEvent(event_type='evaluation.match.requested',aggregate_type='evaluation',aggregate_id=run.id,event_key=key,payload_refs={'evaluation_id':run.id},state='pending',next_attempt_at=utc_naive(Clock().now())))

    def screen_in(self,uow,run_id):
        """使用冻结来源计算一次；旧运行仅保存历史，绝不推进当前流程。"""
        run=uow.session.scalar(select(EvaluationRun).where(EvaluationRun.id==run_id).with_for_update())
        if run is None:raise DomainError('RESOURCE_NOT_FOUND',404,'评估不存在')
        if run.screening_result is not None or run.state=='evaluation_failed':return self._view(uow,run)
        context=run.screening_context
        resume=uow.session.get(ResumeVersion,run.resume_version_id);profile=uow.session.get(CandidateProfile,run.profile_id);version=uow.session.get(JobVersion,run.job_version_id)
        try:
            if not context or context.get('normalization_revision')!='screening-core-v1' or context.get('dictionary_revision')!='core-major-v1' or self._hashes(resume,profile,version)!=context.get('source_hashes'):raise DomainError('EVALUATION_SOURCE_STALE',409,'冻结来源或规则不可验证')
            self.profiles._validate(uow,profile)
            actor=ActorContext('hr',user_id=context['initiator_user_id'])
            self.authorize(uow,actor,'evaluation.write',self._scope(uow,run.application_id))
            facts=ResumeFacts.model_validate(resume.structured_data)
            report=ScreeningEngine(as_of=date.fromisoformat(context['as_of']),dictionary_revision=context['dictionary_revision'],relevant_employment_indices=context.get('relevant_employment_indices')).evaluate(facts,version.conditions)
        except (DomainError,ValueError,KeyError,TypeError):
            run.state='evaluation_failed';run.error_code='EVALUATION_SOURCE_UNAVAILABLE';return self._view(uow,run)
        run.screening_context={**context,'condition_reasons':{d.condition_key:d.reason_code for d in report.details}}
        run.screening_result=report.result
        for detail in report.details:
            uow.session.add(ScreeningDetail(evaluation_run_id=run.id,condition_key=detail.condition_key,required=detail.required,expected=detail.expected,actual=detail.actual,result=detail.result,evidence=[e.model_dump(mode='json') for e in detail.evidence]))
        run.state={'pass':'matching','fail':'screened_out','unknown':'needs_review'}[report.result]
        if self._current(uow,run):
            if report.result=='pass':self._match_request(uow,run)
        else:run.error_code='EVALUATION_SUPERSEDED'
        uow.session.flush();return self._view(uow,run)

    def screen(self,run_id):
        """内部调试入口；worker调用screen_in以保持租约原子性。"""
        with self.candidates.identity_write(),self.uow_factory() as uow:
            result=self.screen_in(uow,run_id);uow.commit();return result

    def override(self,actor,run_id,reason):
        """追加人工继续决定，原始三态结果、逐条件证据永不覆盖。"""
        with self.candidates.identity_write():
            with self.uow_factory() as uow:
                run=uow.session.get(EvaluationRun,run_id)
                if run is None:raise DomainError('RESOURCE_NOT_FOUND',404,'评估不存在')
                scope=self._scope(uow,run.application_id)
            if not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise DomainError('INVALID_REASON',422,'需要有效人工理由')
            def command(uow,fresh):
                run=uow.session.scalar(select(EvaluationRun).where(EvaluationRun.id==run_id).with_for_update())
                if not self._current(uow,run) or run.screening_result not in {'fail','unknown'} or run.state not in {'screened_out','needs_review'} or run.override_by:raise DomainError('EVALUATION_OVERRIDE_BLOCKED',409,'评估已变化或不满足人工继续前提')
                run.override_by=fresh.user_id;run.override_reason=reason.strip();run.invitation_mode='manual_only';run.state='matching'
                uow.session.add(RecruitmentEvent(application_id=run.application_id,event_type='evaluation.override',actor_id=fresh.user_id,content={'evaluation_id':run.id,'reason':reason.strip(),'decision':'continue','original_result':run.screening_result}))
                self.audit(uow,fresh,'evaluation.override','application',run.application_id,{'reason':reason.strip(),'source_id':run.id});self._match_request(uow,run)
                return ResultRef('evaluation',run.id,200)
            self.execute(actor,'evaluation.write',scope,'evaluation.override',{'run_id':run_id,'reason':reason},command,'evaluation.read')
            return self.get(actor,run_id)

    def get(self,actor,run_id):
        """每次读取复验部门权限，只投影此运行的覆盖事件和匹配白名单。"""
        with self.uow_factory() as uow:
            run=uow.session.get(EvaluationRun,run_id)
            if run is None:raise DomainError('RESOURCE_NOT_FOUND',404,'评估不存在')
            self.authorize(uow,actor,'evaluation.read',self._scope(uow,run.application_id))
            details=list(uow.session.scalars(select(ScreeningDetail).where(ScreeningDetail.evaluation_run_id==run.id).order_by(ScreeningDetail.id)))
            events=list(uow.session.scalars(select(RecruitmentEvent).where(RecruitmentEvent.application_id==run.application_id,RecruitmentEvent.event_type=='evaluation.override').order_by(RecruitmentEvent.id)))
            match=uow.session.scalar(select(MatchResult).where(MatchResult.evaluation_run_id==run.id))
            return EvaluationDetail(**self._view(uow,run).model_dump(),screening_context=deepcopy(run.screening_context),conditions=[{'key':d.condition_key,'required':d.required,'expected':d.expected,'actual':d.actual,'result':d.result,'evidence':d.evidence,'reason_code':run.screening_context.get('condition_reasons',{}).get(d.condition_key)} for d in details],match={k:getattr(match,k) for k in ('state','total_score','dimension_scores','strengths','gaps','evidence')} if match else None,override_events=[{'id':str(e.id),'actor_id':str(e.actor_id),**e.content} for e in events if e.content.get('evaluation_id')==run.id])
