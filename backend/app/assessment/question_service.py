"""题库、试卷与考试：管理题库、题目修订和人工批准。"""
from uuid import uuid4
from sqlalchemy import select
from app.core.access import ResourceScope
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.core.resource_scope import ResourceResolver
from app.identity.models import Department
from app.knowledge.models import KnowledgeDocument,KnowledgeChunk
from app.assessment.models.papers import QuestionBank,Question
from app.assessment.schemas import QuestionDraft,QuestionBankCreate
from app.assessment.views import bank_view,question_view

class QuestionService(HrServiceBase):
    """QuestionService：题库、试卷与考试中的协作类型。"""
    def _bank_scope(self,bank_id):
        with self.uow_factory() as uow:
            bank=uow.session.get(QuestionBank,bank_id)
            if bank is None: raise DomainError('RESOURCE_NOT_FOUND',404,'题库不存在')
            return ResourceScope('question_bank',id=bank.id,department_id=bank.department_id)

    def _question_scope(self,question_id):
        with self.uow_factory() as uow:
            bank_id=uow.session.scalar(select(Question.bank_id).where(Question.id==question_id))
            if bank_id is None: raise DomainError('RESOURCE_NOT_FOUND',404,'题目不存在')
        return self._bank_scope(bank_id)

    def validate_sources(self,uow,actor,sources):
        """校验题目来源引用的结构与完整性。 actor为服务端解析的操作者，资源范围仍由服务层验证。uow属于当前调用方事务，回调不得提交外层事务。"""
        for source in sources:
            kind=source.source_type;source_id=source.source_id
            if kind=='knowledge_chunk':
                chunk=uow.session.get(KnowledgeChunk,source_id)
                if chunk is None: raise DomainError('RESOURCE_NOT_FOUND',404,'引用来源不存在')
                doc_id=chunk.document_id
                if source.quote and source.quote not in chunk.content: raise DomainError('INVALID_SOURCE_QUOTE',422,'引用片段与来源不一致')
            else: doc_id=source_id
            ResourceResolver().require(uow.session,actor,'knowledge_document',doc_id)
            doc=uow.session.get(KnowledgeDocument,doc_id)
            if doc.state!='published': raise DomainError('SOURCE_NOT_PUBLISHED',409,'引用资料尚未发布')
            if kind=='knowledge_document' and source.quote:
                content=list(uow.session.scalars(select(KnowledgeChunk.content).where(KnowledgeChunk.document_id==doc_id)))
                if not any(source.quote in text for text in content): raise DomainError('INVALID_SOURCE_QUOTE',422,'引用片段与来源不一致')

    def _create_row(self,uow,actor,cmd,logical_key,revision):
        bank=uow.session.get(QuestionBank,cmd.bank_id)
        if bank is None or bank.status!='active': raise DomainError('BANK_NOT_ACTIVE',409,'题库不可用')
        self.validate_sources(uow,actor,cmd.reference_sources)
        refs=[{**r.model_dump(mode='json'),'source_id':str(r.source_id)} for r in cmd.reference_sources]
        row=Question(bank_id=cmd.bank_id,logical_key=logical_key,revision_no=revision,question_type=cmd.type,stem=cmd.stem,
            options=[o.model_dump() for o in cmd.options] if cmd.options else None,answer_key=cmd.answer_key,rubric=cmd.rubric,reference_sources=refs,state='draft')
        uow.session.add(row);uow.session.flush()
        self.audit(uow,actor,'question.create','question',row.id,{'revision':revision})
        return row

    def get(self,actor,question_id):
        """读取指定私有对象或会话。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        scope=self._question_scope(question_id)
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'question.read',scope)
            return question_view(uow.session.get(Question,question_id))

    def create_bank(self,actor,cmd: QuestionBankCreate):
        """创建当前授权部门的题库。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        scope=ResourceScope('question_bank',department_id=cmd.department_id)
        def command(uow,fresh):
            department=uow.session.get(Department,cmd.department_id)
            if department is None or department.status!='active': raise DomainError('INVALID_DEPARTMENT',422,'部门不存在或已停用')
            row=QuestionBank(department_id=cmd.department_id,name=cmd.name,created_by=fresh.user_id,status='active')
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'question_bank.create','question_bank',row.id,{'department_id':row.department_id})
            return ResultRef('question_bank',row.id,201)
        result=self.execute(actor,'question.write',scope,'question_bank.create',cmd.model_dump(mode='json'),command)
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'question.write',scope)
            return bank_view(uow.session.get(QuestionBank,result.entity_id))

    def create(self,actor,cmd: QuestionDraft):
        """创建经过校验的领域对象，并返回其视图。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        scope=self._bank_scope(cmd.bank_id)
        def command(uow,fresh):
            row=self._create_row(uow,fresh,cmd,str(uuid4()),1)
            return ResultRef('question',row.id,201)
        result=self.execute(actor,'question.write',scope,'question.create',cmd.model_dump(mode='json'),command,response_permission='question.read')
        return self.get(actor,result.entity_id)

    def revise(self,actor,question_id: int,cmd: QuestionDraft,reason: str):
        """创建题目新修订，保留历史修订。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        if not reason.strip(): raise DomainError('REASON_REQUIRED',422,'修订原因不可为空')
        scope=self._question_scope(question_id)
        if cmd.bank_id!=scope.id: raise DomainError('QUESTION_BANK_IMMUTABLE',422,'修订不能跨题库移动题目')
        def command(uow,fresh):
            original=uow.session.get(Question,question_id)
            rows=list(uow.session.scalars(select(Question).where(Question.logical_key==original.logical_key).order_by(Question.revision_no,Question.id).with_for_update()))
            revision=max(q.revision_no for q in rows)+1
            row=self._create_row(uow,fresh,cmd,original.logical_key,revision)
            self.audit(uow,fresh,'question.revise','question',row.id,{'reason':reason,'previous_version':question_id,'revision':revision})
            return ResultRef('question',row.id,201)
        result=self.execute(actor,'question.write',scope,'question.revise',{'question_id':question_id,'draft':cmd.model_dump(mode='json'),'reason':reason},command,response_permission='question.read')
        return self.get(actor,result.entity_id)

    def approve(self,actor,question_id: int,reason: str):
        """批准已校验的题目修订。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        if not reason.strip(): raise DomainError('REASON_REQUIRED',422,'审核原因不可为空')
        scope=self._question_scope(question_id)
        def command(uow,fresh):
            row=uow.session.scalar(select(Question).where(Question.id==question_id).with_for_update())
            cmd=QuestionDraft(bank_id=row.bank_id,type=row.question_type,stem=row.stem,options=row.options,answer_key=row.answer_key,rubric=row.rubric,reference_sources=row.reference_sources)
            self.validate_sources(uow,fresh,cmd.reference_sources)
            if row.state=='archived': raise DomainError('QUESTION_ARCHIVED',409,'题目已归档')
            if row.state!='approved':
                row.state='approved'
                self.audit(uow,fresh,'question.approve','question',row.id,{'reason':reason})
            return ResultRef('question',row.id,200)
        result=self.execute(actor,'question.write',scope,'question.approve',{'question_id':question_id,'reason':reason},command,response_permission='question.read')
        return self.get(actor,result.entity_id)
