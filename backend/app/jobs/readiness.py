"""岗位自动邀请的依赖门；只做本地检查，不调用模型或SMTP。"""
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select
from app.ai_runtime.models import WorkflowConfig,ModelConfig,PromptVersion
from app.ai_runtime.endpoint_policy import EndpointPolicy
from app.assessment.models.papers import Paper,PaperVersion,PaperItem
from app.notifications.models import MailConfig
from app.notifications.policy import MailPolicy
from app.core.secrets import SecretCipher
from app.core.errors import DomainError
from app.jobs.models import JobVersion
from app.jobs.schemas import Readiness

@dataclass(frozen=True)
class LockedDependencies:
    """持有当前读的强引用，避免ORM弱引用回收后重读旧事务快照。"""
    workflows: dict[str,WorkflowConfig]
    models: dict[int,ModelConfig]
    prompts: dict[int,PromptVersion]
    mail_configs: list[MailConfig]

def lock_dependencies(session) -> LockedDependencies:
    """按固定顺序锁定配置并刷新已加载实体；调用者须持有结果到提交。"""
    def locked(query):
        return list(session.scalars(query.with_for_update().execution_options(populate_existing=True)))
    workflows=locked(select(WorkflowConfig).order_by(WorkflowConfig.id))
    mail=locked(select(MailConfig).order_by(MailConfig.id))
    model_ids={w.model_config_id for w in workflows if w.model_config_id}
    prompt_ids={w.prompt_version_id for w in workflows if w.prompt_version_id}
    models=locked(select(ModelConfig).where(ModelConfig.id.in_(model_ids)).order_by(ModelConfig.id))
    prompts=locked(select(PromptVersion).where(PromptVersion.id.in_(prompt_ids)).order_by(PromptVersion.id))
    return LockedDependencies({w.task_type:w for w in workflows},{m.id:m for m in models},{p.id:p for p in prompts},mail)

class AutomationReadiness:
    """检查冻结引用及有效配置；后续真正邀考/发信时仍须复验资格。"""
    def __init__(self,settings):
        self.settings=settings
        self.cipher=SecretCipher(settings.encryption_key.get_secret_value()) if settings and settings.encryption_key else None

    def _model_ready(self,session,task,dependencies=None):
        """开启使用锁定配置；普通读取仅作提示，不作为开启授权。"""
        workflow=dependencies.workflows.get(task) if dependencies is not None else session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type==task))
        if workflow is None or not workflow.enabled or not workflow.model_config_id: return False
        if not 5<=workflow.timeout_seconds<=180 or not 0<=workflow.max_retries<=2: return False
        model=dependencies.models.get(workflow.model_config_id) if dependencies is not None else session.get(ModelConfig,workflow.model_config_id)
        if model is None or not model.enabled or model.capabilities.get('verified') is not True: return False
        needs=('embedding',) if task=='embedding' else ('text','json')
        if not all(model.capabilities.get(k) is True for k in needs): return False
        try:
            endpoint=EndpointPolicy().require(model.provider_type,model.base_url,model.model_name)
            if endpoint.family=='ollama':
                if not model.model_digest: return False
            elif self.cipher is None or not model.secret_ciphertext or not self.cipher.decrypt(model.secret_ciphertext).strip(): return False
        except DomainError: return False
        if task=='embedding': return type(model.embedding_dimension) is int and 1<=model.embedding_dimension<=8192
        prompt=(dependencies.prompts.get(workflow.prompt_version_id) if dependencies is not None else session.get(PromptVersion,workflow.prompt_version_id)) if workflow.prompt_version_id else None
        return prompt is not None and prompt.status=='published' and prompt.task_type==task

    def _mail_ready(self,session,dependencies=None):
        """在锁定的当前配置中筛选激活项，避免SQL条件回到旧快照。"""
        rows=[row for row in dependencies.mail_configs if row.state=='active'] if dependencies is not None else list(session.scalars(select(MailConfig).where(MailConfig.state=='active')))
        if len(rows)!=1 or self.settings is None: return False
        row=rows[0]
        try:
            MailPolicy(self.settings).require(row.smtp_host,row.smtp_port,row.tls_mode,row.public_base_url)
            if row.username and (self.cipher is None or not row.secret_ciphertext or not self.cipher.decrypt(row.secret_ciphertext).strip()): return False
            if bool(row.username)!=bool(row.secret_ciphertext): return False
            return True
        except DomainError: return False

    def check(self,session,job,dependencies=None):
        """返回安全阻塞代码；开启使用当前读，预览结果不保证后续仍就绪。"""
        reasons=[]
        locking=dependencies is not None
        if job.status!='open': reasons.append('JOB_NOT_OPEN')
        version=session.get(JobVersion,job.current_version_id,with_for_update=locking,populate_existing=locking) if job.current_version_id else None
        if version is None or version.status!='published': reasons.append('JOB_VERSION_NOT_PUBLISHED')
        elif version.job_id!=job.id: reasons.append('CURRENT_VERSION_MISMATCH')
        paper_version=session.get(PaperVersion,version.paper_version_id) if version and version.job_id==job.id and version.paper_version_id else None
        paper=None
        if paper_version:
            # Parent then version follows PaperService's locking order.
            paper=session.get(Paper,paper_version.paper_id,with_for_update=locking,populate_existing=locking)
            if locking: paper_version=session.get(PaperVersion,paper_version.id,with_for_update=True,populate_existing=True)
        items_query=select(PaperItem).where(PaperItem.paper_version_id==paper_version.id).order_by(PaperItem.id) if paper_version else None
        if locking and items_query is not None: items_query=items_query.with_for_update().execution_options(populate_existing=True)
        items=list(session.scalars(items_query)) if items_query is not None else []
        valid_paper=(paper_version is not None and paper_version.status=='published' and paper is not None and paper.status=='active'
            and paper.department_id==job.department_id and paper_version.duration_minutes>0 and items
            and sum((item.max_score for item in items),Decimal(0))==paper_version.total_score and paper_version.total_score>0)
        if not valid_paper: reasons.append('PAPER_NOT_PUBLISHED')
        tasks=['extract','profile','match','embedding']
        if any(item.question_type=='short_answer' for item in items): tasks.append('grade')
        if not all(self._model_ready(session,task,dependencies) for task in tasks): reasons.append('MODEL_UNAVAILABLE')
        if not self._mail_ready(session,dependencies): reasons.append('MAIL_NOT_VERIFIED')
        return Readiness(ready=not reasons,blocking_reasons=reasons)
