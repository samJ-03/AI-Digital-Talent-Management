"""岗位画像匹配：冻结来源、外部生成与条件化原子提交分离。"""
from dataclasses import dataclass
from pydantic import BaseModel,model_validator
from sqlalchemy import select
from app.core.uow import make_uow
from app.core.errors import DomainError
from app.core.access import ActorContext
from app.ai_runtime.models import WorkflowConfig,AiRun,ModelConfig
from app.ai_runtime.generation_types import AiConfigSnapshot,Evidence
from app.ai_runtime.graphs import FixedGraphRunner
from app.evaluation.models import EvaluationRun,MatchResult
from app.evaluation.service import EvaluationService,fingerprint
from app.evaluation.match_scoring import MatchDraft,MatchEvidenceValidator,MatchScorer
from app.jobs.models import JobVersion
from app.jobs.schemas import MatchWeights
from app.talents.models import ResumeVersion
from app.talents.profile_builder import fact_catalog
from app.search.index_service import default_gateway

class MatchView(BaseModel):
    """匹配结果供HR辅助决策；失败和未知均无总分。"""
    id: str
    evaluation_run_id: str
    state: str
    total_score: str|None
    dimensions: list[dict]
    strengths: list[dict]
    gaps: list[dict]
    evidence: list[dict]

@dataclass(frozen=True)
class PreparedMatch:
    """外部调用后的不可变草稿；最终提交必须复验来源、配置和AI记录。"""
    run_id: int
    context_hash: str
    config: AiConfigSnapshot|None
    ai_run_id: int|None
    draft: dict|None
    failure: str|None
    model_hash: str|None=None

class MatchService:
    """同一run只有一个结果；worker在有效租约下提交，无自动发卷能力。"""
    def __init__(self,uow_factory=make_uow,gateway=None):
        self.uow_factory=uow_factory;self.gateway=gateway;self.evaluations=EvaluationService(uow_factory)

    def _view(self,row):
        return MatchView(id=str(row.id),evaluation_run_id=str(row.evaluation_run_id),state=row.state,total_score=f'{row.total_score:.2f}' if row.total_score is not None else None,dimensions=row.dimension_scores,strengths=row.strengths,gaps=row.gaps,evidence=row.evidence)

    def _config(self,uow):
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='match').with_for_update().execution_options(populate_existing=True))
        if flow is None or not flow.enabled or not flow.model_config_id or not flow.prompt_version_id:raise DomainError('MATCH_CONFIG_UNAVAILABLE',409,'岗位匹配流程未启用')
        self._model_hash(uow,flow.model_config_id)
        return AiConfigSnapshot(flow.model_config_id,flow.prompt_version_id,flow.timeout_seconds,flow.max_retries,flow.config_revision)

    def _model_hash(self,uow,model_id):
        """复测可独立修改实际模型，不能只核对workflow revision。"""
        model=uow.session.get(ModelConfig,model_id,populate_existing=True,with_for_update=True)
        if model is None or not model.enabled or not all(model.capabilities.get(k) is True for k in ['verified','text','json']):raise DomainError('MATCH_CONFIG_UNAVAILABLE',409,'匹配模型未就绪')
        return fingerprint([model.id,model.revision_no,model.provider_type,model.base_url,model.model_name,model.model_digest,model.capabilities,model.enabled,model.secret_ciphertext])

    def _eligible(self,uow,run):
        if run.state!='matching' or run.screening_result!='pass' and not run.override_by or not self.evaluations._current(uow,run):raise DomainError('MATCH_SOURCE_STALE',409,'当前评估不可匹配')
        actor=ActorContext('hr',user_id=run.screening_context['initiator_user_id'])
        self.evaluations.authorize(uow,actor,'evaluation.write',self.evaluations._scope(uow,run.application_id))

    def _evidence(self,uow,run):
        resume=uow.session.get(ResumeVersion,run.resume_version_id);version=uow.session.get(JobVersion,run.job_version_id)
        catalog=fact_catalog(self.evaluations.candidates._resume_view(resume))
        # 身份姓名不参与评分；联系方式从未进入catalog。
        evidence=[v for k,v in catalog.items() if k!='identity.name']
        evidence.append(Evidence(source_type='job_version',source_id=str(version.id),locator='description',quote=version.description))
        if version.conditions:
            import json
            evidence.append(Evidence(source_type='job_version',source_id=str(version.id),locator='conditions',quote=json.dumps(version.conditions,ensure_ascii=False,sort_keys=True)))
        return evidence

    def prepare(self,run_id):
        """只从冻结简历及岗位版本构造授权证据；不读取部门考试或面试。"""
        context_hash='';config=None;model_hash=None
        try:
            with self.uow_factory() as uow:
                run=uow.session.get(EvaluationRun,run_id)
                if run is None:raise DomainError('RESOURCE_NOT_FOUND',404,'评估不存在')
                context_hash=fingerprint(run.screening_context)
                existing=uow.session.scalar(select(MatchResult).where(MatchResult.evaluation_run_id==run_id))
                if existing:return PreparedMatch(run_id,context_hash,None,None,None,'EXISTING')
                self._eligible(uow,run);config=self._config(uow);model_hash=self._model_hash(uow,config.model_config_id);evidence=self._evidence(uow,run)
                refs=[{'source_type':'resume_version','source_id':str(run.resume_version_id)},{'source_type':'job_version','source_id':str(run.job_version_id)}]
            allowed={v.model_dump_json() for v in evidence}
            class BoundMatch(MatchDraft):
                @model_validator(mode='after')
                def authorized_sources(self):
                    if any(v.model_dump_json() not in allowed for v in self.citations):raise ValueError('Foreign citation')
                    for item in [*self.dimensions,*self.strengths,*self.gaps]:
                        if any(v.model_dump_json() not in allowed for v in item.evidence):raise ValueError('Foreign evidence')
                    return self
            result=FixedGraphRunner(self.gateway or default_gateway(self.uow_factory),{'match':BoundMatch}).run('match',{'input_refs':refs,'evidence':[v.model_dump(mode='json') for v in evidence],'output_schema':MatchDraft.model_json_schema()},config)
            return PreparedMatch(run_id,context_hash,config,result.ai_run_id,result.output,None,model_hash)
        except (DomainError,ValueError,TypeError):return PreparedMatch(run_id,context_hash,config,None,None,'MATCH_UNAVAILABLE',model_hash)

    def finalize(self,uow,prepared):
        """在原租约事务中写一次；迟到或配置变化只留下需人工复核的结果。"""
        run=uow.session.scalar(select(EvaluationRun).where(EvaluationRun.id==prepared.run_id).with_for_update())
        if run is None:raise DomainError('RESOURCE_NOT_FOUND',404,'评估不存在')
        existing=uow.session.scalar(select(MatchResult).where(MatchResult.evaluation_run_id==run.id))
        if existing:return self._view(existing)
        state='needs_review';total=None;dimensions=[];strengths=[];gaps=[];evidence=[];ai_id=None
        try:
            self._eligible(uow,run)
            if prepared.failure or fingerprint(run.screening_context)!=prepared.context_hash or self._config(uow)!=prepared.config or self._model_hash(uow,prepared.config.model_config_id)!=prepared.model_hash:raise DomainError('MATCH_SOURCE_STALE',409,'匹配期间来源或配置已变化')
            ai=uow.session.get(AiRun,prepared.ai_run_id)
            refs=[{'source_type':'resume_version','source_id':str(run.resume_version_id)},{'source_type':'job_version','source_id':str(run.job_version_id)}]
            if ai is None or ai.state!='succeeded' or ai.task_type!='match' or ai.source_refs!=refs or ai.model_config_id!=prepared.config.model_config_id or ai.prompt_version_id!=prepared.config.prompt_version_id or ai.validated_output!=prepared.draft:raise DomainError('MATCH_OUTPUT_INVALID',409,'匹配运行来源不一致')
            draft=MatchDraft.model_validate(prepared.draft);validation=MatchEvidenceValidator().validate(draft,self._evidence(uow,run));unknown=set(validation.unknown_dimensions)
            dimensions=[{**d.model_dump(mode='json'),'score':None if d.name in unknown else str(d.score) if d.score is not None else None} for d in draft.dimensions]
            ai_id=ai.id;evidence=[e.model_dump(mode='json') for e in draft.citations]
            if validation.valid:
                total=MatchScorer().aggregate(draft.dimensions,MatchWeights.model_validate(uow.session.get(JobVersion,run.job_version_id).match_weights));state='valid'
                strengths=[c.model_dump(mode='json') for c in draft.strengths];gaps=[c.model_dump(mode='json') for c in draft.gaps]
        except (DomainError,ValueError,TypeError,KeyError):pass
        result=MatchResult(evaluation_run_id=run.id,ai_run_id=ai_id,total_score=total,dimension_scores=dimensions,strengths=strengths,gaps=gaps,evidence=evidence,state=state)
        uow.session.add(result);uow.session.flush()
        if self.evaluations._current(uow,run):run.state='matched' if state=='valid' else 'needs_review';run.error_code=None if state=='valid' else 'MATCH_NEEDS_REVIEW'
        return self._view(result)

    def match(self,run_id):
        """内部命令入口，外部调用无数据库锁，最终提交使用身份短锁。"""
        prepared=self.prepare(run_id)
        with self.evaluations.candidates.identity_write(),self.uow_factory() as uow:
            result=self.finalize(uow,prepared);uow.commit();return result
