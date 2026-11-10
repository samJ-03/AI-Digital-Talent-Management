"""应聘关系服务：身份根与历史别名共用每岗位唯一的有效关系。"""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from app.core.access import ResourceScope
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.core.uow import make_uow
from app.jobs.models import Job
from app.recruitment.models import Application,RecruitmentEvent
from app.talents.models import Candidate
from app.talents.identity_resolver import CanonicalResolver
from app.evaluation.service import EvaluationService
from app.runtime.models import BackgroundJob

class AddCandidates(BaseModel):
    """只接受人才库选择，不允许客户端设置招聘阶段。"""
    model_config=ConfigDict(extra='forbid')
    candidate_ids: list[int]=Field(min_length=1,max_length=50)
    source: Literal['talent_pool']='talent_pool'

class ApplicationView(BaseModel):
    """复用关系不重新发起评估；受阻新关系等待来源准备。"""
    id: str
    candidate_id: str
    job_id: str
    stage: str
    current_evaluation_id: str|None
    task_ids: list[str]

class ApplicationService(HrServiceBase):
    """串行身份写锁覆盖幂等提交，避免别名并发建立重复关系。"""
    def __init__(self,uow_factory=make_uow,idempotency_key=None):
        super().__init__(uow_factory,idempotency_key);self.evaluations=EvaluationService(uow_factory)

    def add_candidates(self,actor,job_id,candidate_ids,source):
        """原子加入一批人才；只有新关系启动首次评估。"""
        if source!='talent_pool' or not candidate_ids or len(candidate_ids)>50 or any(type(v) is not int or v<=0 for v in candidate_ids):raise DomainError('INVALID_INPUT',422,'人才选择无效')
        with self.evaluations.candidates.identity_write():
            with self.uow_factory() as uow:
                job=uow.session.get(Job,job_id)
                if job is None:raise DomainError('RESOURCE_NOT_FOUND',404,'岗位不存在')
                scope=ResourceScope('job',id=job_id,department_id=job.department_id)
            def command(uow,fresh):
                job=uow.session.scalar(select(Job).where(Job.id==job_id).with_for_update())
                if job.status!='open' or not job.current_version_id:raise DomainError('JOB_NOT_READY',409,'岗位未开放或未发布')
                self.authorize(uow,fresh,'evaluation.write',scope)
                roots={CanonicalResolver().resolve(uow,cid).root_id for cid in candidate_ids}
                list(uow.session.scalars(select(Candidate).where(Candidate.id.in_(roots)).order_by(Candidate.id).with_for_update()))
                for cid in sorted(roots):
                    identity=CanonicalResolver().resolve(uow,cid);allids=(cid,*identity.alias_ids)
                    existing=uow.session.scalar(select(Application).where(Application.candidate_id.in_(allids),Application.job_id==job_id,Application.relationship_state=='active',Application.canonical_application_id.is_(None)).with_for_update())
                    if existing:continue
                    row=uow.session.get(Candidate,cid)
                    if row.status=='archived':raise DomainError('CANDIDATE_ARCHIVED',409,'已归档人才不可加入招聘')
                    app=Application(candidate_id=cid,job_id=job_id,source=source,stage='evaluating',relationship_state='active',current_round=1)
                    uow.session.add(app);uow.session.flush()
                    uow.session.add(RecruitmentEvent(application_id=app.id,event_type='application.created',actor_id=fresh.user_id,content={'source':source}))
                    try:self.evaluations.create_snapshot(uow,fresh,app,'auto_allowed','hr-add')
                    except DomainError as error:
                        if error.code not in {'PROFILE_NOT_READY','PROFILE_SOURCE_INVALID','EVALUATION_SOURCE_STALE'}:raise
                        from app.evaluation.initial_evaluation import request_initial
                        if row.status=='ready' and row.email_valid and row.email_normalized:self.evaluations.candidates._enqueue_profile(uow,row)
                        request_initial(uow,app.id)
                self.audit(uow,fresh,'application.add','job',job_id,{'changed_fields':['applications']})
                return ResultRef('job',job_id,202)
            self.execute(actor,'recruitment.write',scope,'application.add',{'job_id':job_id,'candidate_ids':candidate_ids,'source':source},command,'recruitment.read')
            with self.uow_factory() as uow:
                self.authorize(uow,actor,'recruitment.read',scope);views=[];seen=set()
                for cid in candidate_ids:
                    identity=CanonicalResolver().resolve(uow,cid)
                    if identity.root_id in seen:continue
                    seen.add(identity.root_id)
                    app=uow.session.scalar(select(Application).where(Application.job_id==job_id,Application.candidate_id.in_((identity.root_id,*identity.alias_ids)),Application.relationship_state=='active',Application.canonical_application_id.is_(None)))
                    if app is None:raise DomainError('RESOURCE_CONFLICT',409,'招聘关系已变化')
                    tids=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='application',BackgroundJob.entity_id==app.id,BackgroundJob.job_type=='application.evaluate',BackgroundJob.input_refs['evaluation_id'].as_integer()==app.current_evaluation_id))) if app.current_evaluation_id else []
                    views.append(ApplicationView(id=str(app.id),candidate_id=str(identity.root_id),job_id=str(job_id),stage=app.stage,current_evaluation_id=str(app.current_evaluation_id) if app.current_evaluation_id else None,task_ids=[str(t) for t in tids]))
                return views
