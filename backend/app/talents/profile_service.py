"""共享画像服务：来源复验、不可变版本、延迟结果保护及部门私有投影。"""
from copy import deepcopy
from dataclasses import dataclass
from sqlalchemy import select,func,or_
from app.core.access import ActorContext,ResourceScope,AccessPolicy
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.core.uow import make_uow
from app.ai_runtime.models import AiRun,WorkflowConfig
from app.ai_runtime.generation_types import AiConfigSnapshot
from app.files.models import StoredFile
from app.talents.models import Candidate,ResumeVersion,CandidateProfile,DuplicateCase
from app.talents.candidate_service import CandidateService
from app.talents.identity_resolver import CanonicalResolver
from app.talents.profile_builder import ProfileBuilder,fact_catalog,bound_output,draft_from_output,output_from_evidence
from app.talents.profile_schemas import ProfileOutput,ProfileView,ProfileRevision,AuthorizedApplicationView
from app.recruitment.models import Application,RecruitmentEvent
from app.jobs.models import Job
from app.assessment.models.exams import ExamAttempt
from app.assessment.models.grading import ScoreReport


@dataclass(frozen=True)
class PreparedProfile:
    """外部I/O前冻结来源和当前指针，用于阻止迟到结果覆盖新版本。"""
    candidate_id: int
    resume_id: int
    candidate_version: int
    resume_version: int
    profile_id: int|None
    facts: dict
    config: AiConfigSnapshot
    draft: object


class ProfileService(HrServiceBase):
    """公开命令拥有事务，worker通过prepare/finalize复用任务事务。"""
    def __init__(self,uow_factory=make_uow,builder=None,idempotency_key=None):
        super().__init__(uow_factory,idempotency_key);self.builder=builder;self.candidates=CandidateService(uow_factory)

    def _resume(self,uow,cid,rid,lock=False):
        identity=CanonicalResolver().resolve(uow,cid)
        stmt=select(Candidate).where(Candidate.id==identity.root_id)
        if lock:stmt=stmt.with_for_update().execution_options(populate_existing=True)
        row=uow.session.scalar(stmt)
        if row.status!='ready' or not row.email_valid or not row.email_normalized:raise DomainError('PROFILE_NOT_READY',409,'人才尚未满足自动画像前提')
        ids=(identity.root_id,*identity.alias_ids)
        if uow.session.scalar(select(DuplicateCase.id).where(DuplicateCase.status=='pending',or_(DuplicateCase.candidate_a_id.in_(ids),DuplicateCase.candidate_b_id.in_(ids))).limit(1)):raise DomainError('PROFILE_NOT_READY',409,'人才仍有未决重复线索')
        if row.current_resume_version_id!=rid:raise DomainError('PROFILE_SOURCE_STALE',409,'当前简历已变化')
        resume=uow.session.get(ResumeVersion,rid)
        if resume is None or resume.candidate_id not in {identity.root_id,*identity.alias_ids}:raise DomainError('PROFILE_SOURCE_INVALID',409,'简历不属于本人才')
        file=uow.session.get(StoredFile,resume.file_id)
        if file is None or file.status!='ready':raise DomainError('PROFILE_SOURCE_INVALID',409,'原始文件不可用')
        return row,resume

    def _config(self,uow):
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='profile'))
        if flow is None or not flow.enabled or not flow.model_config_id or not flow.prompt_version_id:raise DomainError('PROFILE_CONFIG_UNAVAILABLE',409,'画像流程尚未启用')
        return AiConfigSnapshot(flow.model_config_id,flow.prompt_version_id,flow.timeout_seconds,flow.max_retries,flow.config_revision)

    def prepare(self,candidate_id,resume_version_id):
        """模型调用只使用本次简历视图；不查询或传入任何部门私有记录。"""
        with self.uow_factory() as uow:
            row,resume=self._resume(uow,candidate_id,resume_version_id);config=self._config(uow)
            view=self.candidates.resume_view(resume);snapshot=(row.id,resume.id,row.row_version,resume.row_version,row.current_profile_id,deepcopy(resume.structured_data))
        if self.builder is None:
            from app.core.settings import Settings
            from app.core.secrets import SecretCipher
            from app.ai_runtime.gateway import ModelGateway
            settings=Settings.load();cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings.encryption_key else None
            builder=ProfileBuilder(ModelGateway(self.uow_factory,cipher))
        else:builder=self.builder
        draft=builder.build(view,config)
        return PreparedProfile(*snapshot,config,draft)

    def finalize(self,uow,prepared):
        """必须在身份短锁和原任务事务内调用；不提交外层事务。"""
        row,resume=self._resume(uow,prepared.candidate_id,prepared.resume_id,True)
        if (row.row_version,resume.row_version,row.current_profile_id,resume.structured_data)!=(prepared.candidate_version,prepared.resume_version,prepared.profile_id,prepared.facts):raise DomainError('PROFILE_SOURCE_STALE',409,'画像生成期间资料已更新')
        if self._config(uow)!=prepared.config:raise DomainError('AI_CONFIG_STALE',409,'画像配置已更新')
        run=uow.session.get(AiRun,prepared.draft.ai_run_id)
        if (run is None or run.state!='succeeded' or run.task_type!='profile' or run.validated_output!=prepared.draft.validated_output or run.source_refs!=[{'source_type':'resume_version','source_id':str(resume.id)}]):raise DomainError('PROFILE_SOURCE_INVALID',409,'画像运行证据不匹配')
        output=bound_output(fact_catalog(self.candidates.resume_view(resume))).model_validate(run.validated_output)
        draft=draft_from_output(output,run.id)
        return self._insert(uow,row,resume,draft,None)

    def _insert(self,uow,row,resume,draft,confirmed_by,actor=None,reason=None,previous_version=None):
        version=(uow.session.scalar(select(func.max(CandidateProfile.version_no)).where(CandidateProfile.candidate_id==row.id)) or 0)+1
        profile=CandidateProfile(candidate_id=row.id,resume_version_id=resume.id,version_no=version,summary=draft.summary,skills=draft.skills,experiences=draft.experiences,evidence=draft.evidence,source_record_refs=[{'source_type':'resume_version','source_id':str(resume.id)}],ai_run_id=draft.ai_run_id,confirmed_by=confirmed_by)
        uow.session.add(profile);uow.session.flush();row.current_profile_id=profile.id;uow.session.flush()
        summary={'version':version,'source_id':resume.id}
        if reason is not None:summary.update(reason=reason,previous_version=previous_version)
        self.audit(uow,actor or ActorContext('system'),'profile.generate' if confirmed_by is None else 'profile.revise','candidate',row.id,summary)
        return profile

    def generate(self,candidate_id: int,resume_version_id: int) -> ProfileView:
        """内部系统入口，生成共享事实；没有HR权限时不附带私有视图。"""
        with self.uow_factory() as uow:
            existing=self.current(uow,candidate_id,resume_version_id)
            if existing is not None:return self._view(uow,existing,[])
        prepared=self.prepare(candidate_id,resume_version_id)
        with self.candidates.identity_write(),self.uow_factory() as uow:
            profile=self.finalize(uow,prepared);view=self._view(uow,profile,[]);uow.commit();return view

    def current(self,uow,candidate_id,resume_version_id):
        """同一当前简历已有可核查画像时复用，保留HR当前版本且不再付费生成。"""
        row,_=self._resume(uow,candidate_id,resume_version_id)
        profile=uow.session.get(CandidateProfile,row.current_profile_id) if row.current_profile_id else None
        if profile is not None and profile.resume_version_id==resume_version_id:
            self._validate(uow,profile);return profile
        return None

    def _validate(self,uow,profile):
        resume=uow.session.get(ResumeVersion,profile.resume_version_id)
        if resume is None or CanonicalResolver().resolve(uow,resume.candidate_id).root_id!=CanonicalResolver().resolve(uow,profile.candidate_id).root_id:raise DomainError('PROFILE_SOURCE_INVALID',409,'画像简历归属不一致')
        if profile.source_record_refs!=[{'source_type':'resume_version','source_id':str(resume.id)}]:raise DomainError('PROFILE_SOURCE_INVALID',409,'共享画像含不受支持的来源')
        catalog=fact_catalog(self.candidates.resume_view(resume));output=output_from_evidence(profile.evidence,catalog)
        draft=draft_from_output(output)
        if (draft.summary,draft.skills,draft.experiences)!=(profile.summary,profile.skills,profile.experiences):raise DomainError('PROFILE_SOURCE_INVALID',409,'画像事实与来源不一致')
        if profile.ai_run_id:
            run=uow.session.get(AiRun,profile.ai_run_id)
            if run is None or run.task_type!='profile' or run.state!='succeeded' or run.source_refs!=profile.source_record_refs:raise DomainError('PROFILE_SOURCE_INVALID',409,'画像模型运行记录无效')
            verified=draft_from_output(bound_output(catalog).model_validate(run.validated_output))
            if (verified.summary,verified.skills,verified.experiences,verified.evidence)!=(draft.summary,draft.skills,draft.experiences,draft.evidence):raise DomainError('PROFILE_SOURCE_INVALID',409,'画像模型来源不一致')
        elif profile.confirmed_by is None:raise DomainError('PROFILE_SOURCE_INVALID',409,'人工画像缺少确认者')
        return resume,output

    def _view(self,uow,profile,views):
        self._validate(uow,profile)
        return ProfileView(id=str(profile.id),candidate_id=str(profile.candidate_id),resume_version_id=str(profile.resume_version_id),version_no=profile.version_no,summary=profile.summary,skills=profile.skills,experiences=profile.experiences,evidence=profile.evidence,source_record_refs=profile.source_record_refs,ai_run_id=str(profile.ai_run_id) if profile.ai_run_id else None,confirmed_by=str(profile.confirmed_by) if profile.confirmed_by else None,version=profile.row_version,authorized_application_views=views)

    def _private_views(self,uow,actor,identity):
        result=[];ids=(identity.root_id,*identity.alias_ids)
        for app,job in uow.session.execute(select(Application,Job).join(Job,Job.id==Application.job_id).where(Application.candidate_id.in_(ids)).order_by(Application.id)):
            scope=ResourceScope('application',id=app.id,department_id=job.department_id)
            def allowed(permission):
                try:AccessPolicy().require(actor,permission,scope);return True
                except DomainError:return False
            if not any(allowed(p) for p in ['evaluation.read','exam.read','recruitment.read']):continue
            exams=[];notes=[]
            if allowed('exam.read'):
                stmt=select(ExamAttempt,ScoreReport).join(ScoreReport,ScoreReport.id==ExamAttempt.current_score_report_id).where(ExamAttempt.application_id==app.id,ExamAttempt.state=='finalized',ScoreReport.attempt_id==ExamAttempt.id)
                exams=[{'attempt_id':str(a.id),'score_report_id':str(s.id),'total_score':str(s.total_score),'report_version':s.version_no} for a,s in uow.session.execute(stmt)]
            if allowed('recruitment.read'):
                notes=[{'event_id':str(e.id),'event_type':e.event_type,'content':e.content} for e in uow.session.scalars(select(RecruitmentEvent).where(RecruitmentEvent.application_id==app.id,RecruitmentEvent.event_type.like('interview.%')).order_by(RecruitmentEvent.id))]
            result.append(AuthorizedApplicationView(application_id=str(app.id),job_id=str(job.id),department_id=job.department_id,stage=app.stage,relationship_state=app.relationship_state,canonical_application_id=str(app.canonical_application_id) if app.canonical_application_id else None,exam_results=exams,interview_events=notes,radar=None))
        return result

    def get(self,actor,candidate_id: int,version_id: int|None=None) -> ProfileView:
        """每次读取重新验证权限，按根聚合历史但绝不持久化私有附加信息。"""
        scope=ResourceScope('talent',id=candidate_id,shared=True)
        with self.uow_factory() as uow:
            fresh=self.authorize(uow,actor,'profile.read',scope);self.authorize(uow,fresh,'talent.read',scope)
            identity=CanonicalResolver().resolve(uow,candidate_id);row=uow.session.get(Candidate,identity.root_id)
            pid=version_id or row.current_profile_id
            profile=uow.session.get(CandidateProfile,pid) if pid else None
            if profile is None or profile.candidate_id not in {identity.root_id,*identity.alias_ids}:raise DomainError('RESOURCE_NOT_FOUND',404,'画像版本不存在')
            return self._view(uow,profile,self._private_views(uow,fresh,identity))

    def revise(self,actor,candidate_id: int,cmd: ProfileRevision) -> ProfileView:
        """人工选择现有简历事实形成新版本，禁止写入私有评价或模型预测。"""
        scope=ResourceScope('talent',id=candidate_id,shared=True)
        def command(uow,fresh):
            self.authorize(uow,fresh,'talent.read',scope)
            identity=CanonicalResolver().resolve(uow,candidate_id);row=self.candidates._row(uow,identity.root_id)
            if row.status=='archived':raise DomainError('CANDIDATE_ARCHIVED',409,'已归档人才不能修订画像')
            if row.current_profile_id!=cmd.base_profile_id:raise DomainError('VERSION_CONFLICT',409,'当前画像已更新')
            old=uow.session.get(CandidateProfile,cmd.base_profile_id);resume,output=self._validate(uow,old)
            if row.current_resume_version_id!=resume.id:raise DomainError('PROFILE_SOURCE_STALE',409,'画像所用简历已过期')
            catalog=fact_catalog(self.candidates.resume_view(resume));data=output.model_dump(mode='json')
            if set(cmd.changes)-{'summary_claims','skills','experiences'}:raise DomainError('INVALID_PROFILE_REVISION',422,'不支持的画像修订字段')
            try:
                for group,values in cmd.changes.items():
                    claims=[]
                    for value in values:
                        choices=[source for path,source in catalog.items() if source.quote==value and (group=='summary_claims' or group=='skills' and path.startswith('skills.') or group=='experiences' and path.startswith(('education.','employment.','projects.')))]
                        if not choices:raise ValueError()
                        claims.append({'text':value,'source':choices[0].model_dump(mode='json')})
                    data[group]=claims
                data['citations']=[]
                for group in ['summary_claims','skills','experiences']:
                    for claim in data[group]:
                        if claim['source'] not in data['citations']:data['citations'].append(claim['source'])
                revised=bound_output(catalog).model_validate(data)
            except (ValueError,TypeError):raise DomainError('INVALID_PROFILE_REVISION',422,'画像内容必须来自本简历的完整事实') from None
            profile=self._insert(uow,row,resume,draft_from_output(revised),fresh.user_id,fresh,cmd.reason,old.version_no)
            return ResultRef('candidate_profile',profile.id,200)
        with self.candidates.identity_write():result=self.execute(actor,'profile.write',scope,'profile.revise',{'candidate_id':candidate_id,**cmd.model_dump(mode='json')},command,response_permission='profile.read')
        return self.get(actor,candidate_id,result.entity_id)
