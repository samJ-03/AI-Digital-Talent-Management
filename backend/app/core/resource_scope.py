from dataclasses import dataclass
from app.core.access import ResourceScope,AccessPolicy,PermissionDenied
from app.core.errors import DomainError
from app.identity.models import User
from app.jobs.models import Job
from app.ingestion.models import ImportBatch,ImportItem
from app.talents.models import Candidate,ResumeVersion,CandidateProfile
from app.recruitment.models import Application
from app.assessment.models.exams import ExamAttempt
from app.assessment.models.papers import QuestionBank,PaperVersion,Paper
from app.knowledge.models import KnowledgeDocument
from app.notifications.models import Notification,MailConfig

@dataclass(frozen=True,slots=True)
class ResourceGrant:
    permission: str
    scope: ResourceScope

class ResourceResolver:
    """Derive access from persisted domain links, never client-supplied department IDs."""
    def _get(self,session,model,entity_id):
        row=session.get(model,entity_id)
        if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在')
        return row

    def resolve(self,session,kind: str,entity_id: int) -> ResourceGrant:
        if kind=='candidate':
            self._get(session,Candidate,entity_id)
            return ResourceGrant('talent.read',ResourceScope('talent',id=entity_id,shared=True))
        if kind in {'resume_version','candidate_profile'}:
            model=ResumeVersion if kind=='resume_version' else CandidateProfile
            row=self._get(session,model,entity_id)
            return self.resolve(session,'candidate',row.candidate_id)
        if kind=='application':
            app=self._get(session,Application,entity_id)
            job=self._get(session,Job,app.job_id)
            return ResourceGrant('evaluation.read',ResourceScope('application',id=entity_id,department_id=job.department_id))
        if kind=='exam_attempt':
            attempt=self._get(session,ExamAttempt,entity_id)
            app=self._get(session,Application,attempt.application_id)
            job=self._get(session,Job,app.job_id)
            return ResourceGrant('exam.read',ResourceScope('exam_attempt',id=entity_id,department_id=job.department_id))
        if kind=='import_item':
            item=self._get(session,ImportItem,entity_id)
            return self.resolve(session,'import_batch',item.batch_id)
        if kind=='import_batch':
            batch=self._get(session,ImportBatch,entity_id)
            department_id=self._get(session,Job,batch.job_id).department_id if batch.job_id else self._get(session,User,batch.created_by).department_id
            return ResourceGrant('import.read',ResourceScope('import_batch',id=entity_id,department_id=department_id))
        if kind=='knowledge_document':
            doc=self._get(session,KnowledgeDocument,entity_id)
            return ResourceGrant('knowledge.read',ResourceScope('knowledge',id=entity_id,department_id=doc.department_id,shared=doc.scope=='company' and doc.department_id is None))
        if kind=='question_bank':
            bank=self._get(session,QuestionBank,entity_id)
            return ResourceGrant('question.read',ResourceScope('question_bank',id=entity_id,department_id=bank.department_id))
        if kind=='paper_version':
            version=self._get(session,PaperVersion,entity_id)
            paper=self._get(session,Paper,version.paper_id)
            return ResourceGrant('paper.read',ResourceScope('paper',id=paper.id,department_id=paper.department_id))
        if kind=='notification':
            notification=self._get(session,Notification,entity_id)
            if notification.attempt_id: return self.resolve(session,'exam_attempt',notification.attempt_id)
            return self.resolve(session,'mail_config',notification.mail_config_id)
        if kind=='mail_config':
            self._get(session,MailConfig,entity_id)
            return ResourceGrant('mail_config.manage',ResourceScope('mail_config',id=entity_id))
        raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在')

    def require(self,session,actor,kind: str,entity_id: int) -> ResourceGrant:
        grant=self.resolve(session,kind,entity_id)
        try: AccessPolicy().require(actor,grant.permission,grant.scope)
        except PermissionDenied:
            raise DomainError('RESOURCE_NOT_FOUND',404,'资源不存在') from None
        return grant
