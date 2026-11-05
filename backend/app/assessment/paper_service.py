from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal,ROUND_FLOOR
from sqlalchemy import select,func
from pydantic import ValidationError
from app.core.access import ResourceScope
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.identity.models import Department
from app.assessment.models.papers import Paper,PaperVersion,PaperItem,Question,QuestionBank
from app.assessment.schemas import PaperCreate,PaperVersionDraft,QuestionDraft
from app.assessment.question_service import QuestionService
from app.assessment.views import paper_view,version_view

class PaperService(HrServiceBase):
    def _scope(self,paper_id):
        with self.uow_factory() as uow:
            row=uow.session.get(Paper,paper_id)
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'试卷不存在')
            return ResourceScope('paper',id=row.id,department_id=row.department_id)

    def _version_scope(self,version_id):
        with self.uow_factory() as uow:
            paper_id=uow.session.scalar(select(PaperVersion.paper_id).where(PaperVersion.id==version_id))
            if paper_id is None: raise DomainError('RESOURCE_NOT_FOUND',404,'试卷版本不存在')
        return self._scope(paper_id)

    def get_version(self,actor,version_id):
        scope=self._version_scope(version_id)
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'paper.read',scope)
            return version_view(uow.session,uow.session.get(PaperVersion,version_id))

    def create(self,actor,cmd: PaperCreate):
        scope=ResourceScope('paper',department_id=cmd.department_id)
        def command(uow,fresh):
            department=uow.session.get(Department,cmd.department_id)
            if department is None or department.status!='active': raise DomainError('INVALID_DEPARTMENT',422,'部门不存在或已停用')
            row=Paper(department_id=cmd.department_id,name=cmd.name,created_by=fresh.user_id,status='active')
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'paper.create','paper',row.id,{'department_id':row.department_id})
            return ResultRef('paper',row.id,201)
        result=self.execute(actor,'paper.write',scope,'paper.create',cmd.model_dump(mode='json'),command)
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'paper.write',scope)
            return paper_view(uow.session.get(Paper,result.entity_id))

    def _source(self,uow,actor,question_id,department_id):
        source=uow.session.get(Question,question_id)
        if source is None: raise DomainError('RESOURCE_NOT_FOUND',404,'来源题目不存在')
        bank=uow.session.get(QuestionBank,source.bank_id)
        self.authorize(uow,actor,'question.read',ResourceScope('question_bank',id=bank.id,department_id=bank.department_id))
        if bank.department_id!=department_id: raise DomainError('QUESTION_DEPARTMENT_MISMATCH',422,'试卷题目必须来自同一部门题库')
        if bank.status!='active' or source.state=='archived': raise DomainError('QUESTION_UNAVAILABLE',409,'来源题库或题目不可用')
        try:
            draft=QuestionDraft(bank_id=source.bank_id,type=source.question_type,stem=source.stem,options=source.options,
                answer_key=source.answer_key,rubric=source.rubric,reference_sources=source.reference_sources)
        except ValidationError: raise DomainError('QUESTION_STANDARD_INVALID',409,'来源题目评分标准不完整') from None
        QuestionService(self.uow_factory).validate_sources(uow,actor,draft.reference_sources)
        return source

    def _frozen_rubric(self,source,max_score):
        rubric=deepcopy(source.rubric)
        if source.question_type=='short_answer':
            criteria=rubric['criteria']
            weights=[Decimal(str(c['weight'])) for c in criteria]
            total=sum(weights);units=int(max_score*100)
            raw=[Decimal(units)*w/total for w in weights]
            allocated=[int(n.to_integral_value(rounding=ROUND_FLOOR)) for n in raw]
            remaining=units-sum(allocated)
            order=sorted(range(len(raw)),key=lambda i:(-(raw[i]-allocated[i]),i))
            for i in order[:remaining]: allocated[i]+=1
            for criterion,cents in zip(criteria,allocated): criterion['max_score']=format(Decimal(cents)/100,'.2f')
        return rubric

    def _items(self,uow,actor,version,paper,cmd):
        for spec in sorted(cmd.items,key=lambda i:i.position_no):
            source=self._source(uow,actor,spec.source_question_id,paper.department_id)
            uow.session.add(PaperItem(paper_version_id=version.id,source_question_id=source.id,position_no=spec.position_no,
                question_type=source.question_type,stem=source.stem,options=deepcopy(source.options),max_score=spec.max_score,
                answer_key=deepcopy(source.answer_key),rubric=self._frozen_rubric(source,spec.max_score),reference_sources=deepcopy(source.reference_sources)))

    def draft_version(self,actor,paper_id: int,cmd: PaperVersionDraft):
        scope=self._scope(paper_id)
        def command(uow,fresh):
            paper=uow.session.scalar(select(Paper).where(Paper.id==paper_id).with_for_update())
            if paper.status!='active': raise DomainError('PAPER_UNAVAILABLE',409,'试卷已归档')
            revision=(uow.session.scalar(select(func.max(PaperVersion.version_no)).where(PaperVersion.paper_id==paper_id)) or 0)+1
            row=PaperVersion(paper_id=paper_id,version_no=revision,duration_minutes=cmd.duration_minutes,
                reference_pass_score=cmd.reference_pass_score,total_score=sum((i.max_score for i in cmd.items),Decimal('0')),status='draft')
            uow.session.add(row);uow.session.flush()
            self._items(uow,fresh,row,paper,cmd)
            self.audit(uow,fresh,'paper.draft','paper_version',row.id,{'revision':revision,'count':len(cmd.items)})
            return ResultRef('paper_version',row.id,201)
        result=self.execute(actor,'paper.write',scope,'paper.draft',{'paper_id':paper_id,'draft':cmd.model_dump(mode='json')},command,response_permission='paper.read')
        return self.get_version(actor,result.entity_id)

    def edit_draft(self,actor,version_id: int,cmd: PaperVersionDraft,expected_version: int):
        scope=self._version_scope(version_id)
        with self.transaction(actor,'paper.write',scope,response_permission='paper.read') as (uow,fresh):
            row=uow.session.scalar(select(PaperVersion).where(PaperVersion.id==version_id).with_for_update())
            if row.status!='draft': raise DomainError('PAPER_PUBLISHED_IMMUTABLE',409,'已发布试卷不可修改，请建立新版本')
            if row.row_version!=expected_version: raise DomainError('VERSION_CONFLICT',409,'试卷草稿已被其他操作更新')
            paper=uow.session.get(Paper,row.paper_id)
            items=list(uow.session.scalars(select(PaperItem).where(PaperItem.paper_version_id==version_id)))
            for item in items: uow.session.delete(item)
            # Release the version/position unique slots before inserting the replacement draft.
            uow.session.flush()
            self._items(uow,fresh,row,paper,cmd)
            row.duration_minutes=cmd.duration_minutes;row.reference_pass_score=cmd.reference_pass_score
            row.total_score=sum((i.max_score for i in cmd.items),Decimal('0'))
            row.row_version+=1
            uow.session.flush()
            self.audit(uow,fresh,'paper.edit','paper_version',row.id,{'changed_fields':['items','duration_minutes','reference_pass_score']})
            view=version_view(uow.session,row)
        return view

    def publish(self,actor,version_id: int,reason: str):
        if not reason.strip(): raise DomainError('REASON_REQUIRED',422,'发布原因不可为空')
        scope=self._version_scope(version_id)
        def command(uow,fresh):
            row=uow.session.scalar(select(PaperVersion).where(PaperVersion.id==version_id).with_for_update())
            if row.status=='published': return ResultRef('paper_version',row.id,200)
            paper=uow.session.get(Paper,row.paper_id)
            items=list(uow.session.scalars(select(PaperItem).where(PaperItem.paper_version_id==version_id).order_by(PaperItem.position_no)))
            if not items or row.duration_minutes<1: raise DomainError('PAPER_INCOMPLETE',409,'试卷题目或时长不完整')
            total=sum((i.max_score for i in items),Decimal('0'))
            if total<=0 or total>Decimal('9999.99') or row.reference_pass_score is not None and row.reference_pass_score>total:
                raise DomainError('PAPER_SCORE_INVALID',409,'试卷分值不完整')
            for item in items:
                if item.source_question_id is None: raise DomainError('QUESTION_NOT_APPROVED',409,'试卷存在未审核题目')
                source=self._source(uow,fresh,item.source_question_id,paper.department_id)
                if source.state!='approved': raise DomainError('QUESTION_NOT_APPROVED',409,'全部题目必须经过 HR 审核')
            row.total_score=total;row.status='published';row.published_by=fresh.user_id;row.published_at=datetime.now(timezone.utc).replace(tzinfo=None)
            self.audit(uow,fresh,'paper.publish','paper_version',row.id,{'reason':reason,'revision':row.version_no})
            return ResultRef('paper_version',row.id,200)
        result=self.execute(actor,'paper.write',scope,'paper.publish',{'version_id':version_id,'reason':reason},command,response_permission='paper.read')
        return self.get_version(actor,result.entity_id)
