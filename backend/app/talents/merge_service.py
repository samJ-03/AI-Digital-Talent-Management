"""人工去重服务：根锁、部门授权、考试冲突预检与历史别名合并。

不修改历史candidate_id或考试application_id；目标事实指针保持不变。
计划与应用必须属于同一个事务，发现任何冲突先返回再写入，禁止部分合并。
"""
from datetime import datetime,timezone
from sqlalchemy import select,func,or_
from app.core.access import ResourceScope
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.types import Page
from app.core.uow import make_uow
from app.core.resource_scope import ResourceResolver
from app.talents.models import Candidate,DuplicateCase
from app.talents.candidate_service import CandidateService
from app.talents.identity_resolver import CanonicalResolver
from app.talents.merge_schemas import DuplicateQuery,DuplicateCaseView,MergeDecision,MergePlan,MergeResult,ApplicationMapping
from app.recruitment.models import Application
from app.assessment.models.exams import ExamAttempt
from app.runtime.models import OutboxEvent


class MergeConflict(DomainError):
    """只有全部岗位已授权后才附带关系级冲突，不返回评分或答案。"""
    def __init__(self,conflicts):
        super().__init__('MERGE_CONFLICT',409,'招聘关系存在冲突，请先选择主记录或处理活动考试',{'conflicts':list(conflicts)})


class MergePlanner:
    """绑定服务端case与当前HR；调用方必须持有T15身份短锁。"""
    def __init__(self,actor,case_id,service):
        self.actor=actor;self.case_id=case_id;self.service=service
        self._plan=None;self._transaction=None;self._session=None;self._cmd=None;self.locked_root_ids=()

    def plan(self,uow,cmd: MergeDecision) -> MergePlan:
        """根/别名/应聘/考次均按ID锁；先授权全部重叠岗位，再生成冲突。"""
        case=uow.session.get(DuplicateCase,self.case_id)
        if case is None:raise DomainError('RESOURCE_NOT_FOUND',404,'去重记录不存在')
        resolver=CanonicalResolver()
        left=resolver.resolve(uow,case.candidate_a_id);right=resolver.resolve(uow,case.candidate_b_id)
        roots=tuple(sorted({left.root_id,right.root_id}))
        self.locked_root_ids=roots
        list(uow.session.scalars(select(Candidate).where(Candidate.id.in_(roots)).order_by(Candidate.id).with_for_update().execution_options(populate_existing=True)))
        aliases=tuple(sorted(set(roots)|set(left.alias_ids)|set(right.alias_ids)))
        list(uow.session.scalars(select(Candidate).where(Candidate.id.in_(aliases)).order_by(Candidate.id).with_for_update().execution_options(populate_existing=True)))
        # Duplicate cases are locked after roots, same order for every direction.
        case=uow.session.scalar(select(DuplicateCase).where(DuplicateCase.id==self.case_id).with_for_update().execution_options(populate_existing=True))
        if case.status!='pending':raise DomainError('VERSION_CONFLICT',409,'去重记录已处理，请刷新')
        target=None;conflicts=[];mappings=[]
        if cmd.decision=='same_person':
            if cmd.target_candidate_id not in aliases:raise DomainError('INVALID_MERGE_TARGET',422,'目标必须属于当前两个身份')
            target=resolver.resolve(uow,cmd.target_candidate_id).root_id
            apps=list(uow.session.scalars(select(Application).where(Application.candidate_id.in_(aliases)).order_by(Application.id).with_for_update().execution_options(populate_existing=True)))
            groups={}
            for app in apps:groups.setdefault(app.job_id,[]).append(app)
            choices={v.job_id:v for v in cmd.application_resolutions}
            overlap={jid:rows for jid,rows in groups.items() if len(rows)>1}
            # Complete authorization precedes ALL conflict details, so an early
            # permitted group cannot disclose a later hidden department's IDs.
            for rows in overlap.values():
                for app in rows:
                    scope=ResourceResolver().resolve(uow.session,'application',app.id).scope
                    self.service.authorize(uow,self.actor,'evaluation.read',scope)
                    self.service.authorize(uow,self.actor,'recruitment.write',scope)
            if set(choices)-set(overlap):raise DomainError('INVALID_APPLICATION_RESOLUTION',422,'招聘关系选择不属于可合并岗位')
            for jid,rows in overlap.items():
                active=[a for a in rows if a.relationship_state=='active']
                ids={a.id for a in rows};choice=choices.get(jid)
                if len(active)>1:
                    if choice is None:
                        conflicts.append({'job_id':str(jid),'application_ids':[str(a.id) for a in active],'reason':'PRIMARY_REQUIRED'});continue
                    active_ids={a.id for a in active}
                    if choice.primary_application_id not in active_ids or set(choice.secondary_application_ids)!=active_ids-{choice.primary_application_id}:
                        raise DomainError('INVALID_APPLICATION_RESOLUTION',422,'必须完整指定本岗位的主次有效关系')
                    primary=choice.primary_application_id
                elif len(active)==1:
                    primary=active[0].id
                    if choice is not None:raise DomainError('INVALID_APPLICATION_RESOLUTION',422,'已有唯一主关系，无需重新选择')
                else:
                    conflicts.append({'job_id':str(jid),'reason':'INVALID_RELATIONSHIP_CHAIN'});continue
                for app in rows:
                    if app.relationship_state=='merged' and (app.canonical_application_id not in ids or app.canonical_application_id==app.id):
                        conflicts.append({'job_id':str(jid),'reason':'INVALID_RELATIONSHIP_CHAIN'})
                attempts=list(uow.session.scalars(select(ExamAttempt).where(ExamAttempt.application_id.in_(ids)).order_by(ExamAttempt.id).with_for_update().execution_options(populate_existing=True)))
                blocked=[a for a in attempts if a.application_id!=primary and self._active(a)]
                if blocked:
                    conflicts.append({'job_id':str(jid),'application_ids':sorted({str(a.application_id) for a in blocked}),'reason':'ACTIVE_ATTEMPT'});continue
                mappings.extend((jid,a.id,primary) for a in rows if a.id!=primary)
        elif len(roots)!=2:
            raise DomainError('IDENTITY_ALREADY_MERGED',409,'已合并身份不能直接判为不同人')
        plan=MergePlan(case.id,case.row_version,target,aliases,tuple(mappings),tuple(conflicts))
        self._plan=plan;self._session=uow.session;self._transaction=uow.session.get_transaction();self._cmd=cmd
        return plan

    @staticmethod
    def _active(attempt):
        """评分未定稿也属处理中；已撤销/过期的未开考邀请可以保留为历史。"""
        if attempt.state in {'in_progress','submitted','grading','pending_review'}:return True
        if attempt.state!='not_started':return False
        return attempt.invite_status not in {'revoked','expired'} and attempt.valid_until>datetime.now(timezone.utc).replace(tzinfo=None)

    def apply(self,uow,plan: MergePlan) -> MergeResult:
        """在同一已锁事务应用预检计划；不提交、不物理迁移任何历史。"""
        if plan is not self._plan or uow.session is not self._session or uow.session.get_transaction() is not self._transaction:
            raise DomainError('INVALID_MERGE_PLAN',409,'合并计划必须在原事务应用')
        if plan.conflicts:raise MergeConflict(plan.conflicts)
        case=uow.session.get(DuplicateCase,plan.case_id)
        if case.status!='pending' or case.row_version!=plan.case_version:raise DomainError('VERSION_CONFLICT',409,'去重记录已变化')
        if plan.canonical_root is not None:
            for cid in plan.aliases:
                if cid==plan.canonical_root:continue
                row=uow.session.get(Candidate,cid);row.merged_into_id=plan.canonical_root;row.status='merged'
            for jid,secondary,primary in plan.application_mappings:
                row=uow.session.get(Application,secondary);row.relationship_state='merged';row.canonical_application_id=primary
            # All clues now inside the same identity are resolved together;
            # external pending cases stay intact and continue gating the root.
            internal=list(uow.session.scalars(select(DuplicateCase).where(DuplicateCase.candidate_a_id.in_(plan.aliases),DuplicateCase.candidate_b_id.in_(plan.aliases),DuplicateCase.status=='pending').order_by(DuplicateCase.id).with_for_update()))
            for row in internal:self._decide(row,'same_person')
            affected=[plan.canonical_root]
        else:
            self._decide(case,'different_person')
            affected=list(self.locked_root_ids)
        uow.session.flush()
        for cid in affected:self._gate(uow,cid,case.id)
        uow.session.flush()
        return MergeResult(canonical_candidate_id=str(plan.canonical_root) if plan.canonical_root is not None else None,application_mappings=[ApplicationMapping(job_id=str(j),application_id=str(s),canonical_application_id=str(p)) for j,s,p in plan.application_mappings])

    def _decide(self,row,status):
        row.status=status;row.resolved_by=self.actor.user_id;row.resolution_reason=self._cmd.reason

    def _gate(self,uow,cid,case_id):
        """按根和全部别名的未决线索计算停机门，恢复事件仅一次入Outbox。"""
        row=uow.session.get(Candidate,cid)
        if row.status=='archived':return
        canonical=CanonicalResolver().resolve(uow,cid);ids=(cid,*canonical.alias_ids)
        pending=uow.session.scalar(select(DuplicateCase.id).where(DuplicateCase.status=='pending',or_(DuplicateCase.candidate_a_id.in_(ids),DuplicateCase.candidate_b_id.in_(ids))).limit(1))
        before=row.status
        row.status='duplicate_review' if pending else 'ready' if row.email_valid and row.email_normalized else 'pending_email'
        if row.status=='ready' and before!='ready':
            uow.session.add(OutboxEvent(event_type='pipeline.resume',aggregate_type='candidate',aggregate_id=cid,event_key=f'pipeline.resume:{case_id}:{cid}',payload_refs={'candidate_id':cid},state='pending'))


class DuplicateService(HrServiceBase):
    """共享去重列表与人工裁决入口，部门私有关系在planner逐项授权。"""
    def __init__(self,uow_factory=make_uow):
        super().__init__(uow_factory);self.candidates=CandidateService(uow_factory)

    def list_cases(self,actor,query: DuplicateQuery) -> Page[DuplicateCaseView]:
        """按共享talent.read分页，不展开考试、评价、岗位历史或原始联系方式。"""
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'talent.read',ResourceScope('talent',shared=True))
            stmt=select(DuplicateCase)
            if query.status:stmt=stmt.where(DuplicateCase.status==query.status)
            total=uow.session.scalar(select(func.count()).select_from(stmt.subquery()))
            rows=uow.session.scalars(stmt.order_by(DuplicateCase.id.desc()).offset((query.page-1)*query.page_size).limit(query.page_size))
            # Only identity clue labels are shared. Never forward arbitrary JSON
            # that an older producer might have filled with private observations.
            items=[DuplicateCaseView(id=str(r.id),candidate_a_id=str(r.candidate_a_id),candidate_b_id=str(r.candidate_b_id),status=r.status,evidence=[{'kind':'identity_clue','requires_manual_review':True}],resolved_by=str(r.resolved_by) if r.resolved_by else None,version=r.row_version) for r in rows]
            return Page(items=items,total=total,page=query.page,page_size=query.page_size)

    def resolve(self,actor,case_id: int,cmd: MergeDecision,expected_version: int) -> MergeResult:
        """CAS裁决与身份、关系、Outbox、审计同事务，任何异常整体回滚。"""
        scope=ResourceScope('talent',shared=True)
        with self.candidates.identity_write(),self.transaction(actor,'talent.write',scope,response_permission='talent.read') as (uow,fresh):
            planner=MergePlanner(fresh,case_id,self)
            plan=planner.plan(uow,cmd)
            if plan.case_version!=expected_version:raise DomainError('VERSION_CONFLICT',409,'去重记录已更新，请刷新')
            result=planner.apply(uow,plan)
            self.audit(uow,fresh,'talent.duplicate.resolve','candidate',plan.canonical_root or plan.aliases[0],{'reason':cmd.reason,'result':cmd.decision,'source_id':case_id,'count':len(plan.application_mappings)})
            return result
