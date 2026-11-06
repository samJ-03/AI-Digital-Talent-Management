"""平台开发工具：定义持久化模型、约束和索引。"""
from app.core.db import Base
from app.core.types import SchemaManifest
from app.identity.models import Department, User, Role, UserRole
from app.files.models import StoredFile
from app.jobs.models import Job, JobVersion
from app.ingestion.models import ImportBatch, ImportItem
from app.talents.models import Candidate, ResumeVersion, CandidateProfile, DuplicateCase
from app.recruitment.models import Application, RecruitmentEvent
from app.evaluation.models import EvaluationRun, ScreeningDetail, MatchResult
from app.assessment.models.papers import QuestionBank, Question, Paper, PaperVersion, PaperItem
from app.assessment.models.exams import ExamAttempt, ExamAnswer
from app.assessment.models.grading import ScoreReview, ScoreReport
from app.notifications.models import Notification, MailConfig
from app.knowledge.models import KnowledgeDocument, KnowledgeChunk
from app.ai_runtime.models import ModelConfig, PromptVersion, WorkflowConfig, AiRun
from app.runtime.models import BackgroundJob, OutboxEvent
from app.search.models import IndexRecord
from app.audit.models import AuditLog
from app.core.models import IdempotencyRecord

TABLE_MODELS = {
    "departments": Department,
    "users": User,
    "roles": Role,
    "user_roles": UserRole,
    "stored_files": StoredFile,
    "jobs": Job,
    "job_versions": JobVersion,
    "import_batches": ImportBatch,
    "import_items": ImportItem,
    "candidates": Candidate,
    "resume_versions": ResumeVersion,
    "candidate_profiles": CandidateProfile,
    "duplicate_cases": DuplicateCase,
    "applications": Application,
    "evaluation_runs": EvaluationRun,
    "screening_details": ScreeningDetail,
    "match_results": MatchResult,
    "recruitment_events": RecruitmentEvent,
    "question_banks": QuestionBank,
    "questions": Question,
    "papers": Paper,
    "paper_versions": PaperVersion,
    "paper_items": PaperItem,
    "exam_attempts": ExamAttempt,
    "exam_answers": ExamAnswer,
    "score_reviews": ScoreReview,
    "notifications": Notification,
    "knowledge_documents": KnowledgeDocument,
    "knowledge_chunks": KnowledgeChunk,
    "model_configs": ModelConfig,
    "prompt_versions": PromptVersion,
    "workflow_configs": WorkflowConfig,
    "background_jobs": BackgroundJob,
    "outbox_events": OutboxEvent,
    "ai_runs": AiRun,
    "index_records": IndexRecord,
    "audit_logs": AuditLog,
    "score_reports": ScoreReport,
    "idempotency_records": IdempotencyRecord,
    "mail_configs": MailConfig,
}

def register_models():
    """确保所有领域模型已导入，再返回统一元数据。"""
    return Base.metadata

def metadata_contract() -> SchemaManifest:
    """导出表、索引和外键的可核对结构契约。"""
    metadata=register_models()
    return {
        'tables':sorted(metadata.tables),
        'indexes':{name:[{'name':i.name,'columns':[c.name for c in i.columns],'unique':i.unique} for i in table.indexes] for name,table in metadata.tables.items()},
        'foreign_keys':{name:[{'column':fk.parent.name,'target':fk.target_fullname,'ondelete':fk.ondelete,'deferred':fk.use_alter} for fk in table.foreign_keys] for name,table in metadata.tables.items()}
    }
