import hashlib
import json
from sqlalchemy import select,func
from app.ai_runtime.admin_base import AiAdminBase
from app.ai_runtime.models import PromptVersion,WorkflowConfig
from app.ai_runtime.views import prompt_view
from app.ai_runtime.schemas import PromptCreate
from app.core.errors import DomainError
from app.core.idempotency import IdempotencyService,ResultRef

class PromptService(AiAdminBase):
    def __init__(self,uow_factory,idempotency_key=None):
        super().__init__(uow_factory);self.idempotency_key=idempotency_key

    def create(self,actor,cmd: PromptCreate):
        with self.transaction(actor,'prompt.manage') as (uow,fresh):
            lock=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type==cmd.task_type).with_for_update())
            if lock is None: raise DomainError('WORKFLOW_NOT_INITIALIZED',503,'固定流程尚未初始化')
            revision=(uow.session.scalar(select(func.max(PromptVersion.revision_no)).where(PromptVersion.task_type==cmd.task_type)) or 0)+1
            row=PromptVersion(task_type=cmd.task_type,revision_no=revision,content=cmd.content,output_schema=cmd.output_schema,status='draft')
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'prompt.create','prompt',row.id,{'revision':revision})
            return prompt_view(row)

    def publish(self,actor,prompt_id: int,reason: str):
        if not reason.strip(): raise DomainError('REASON_REQUIRED',422,'发布原因不可为空')
        if not self.idempotency_key: raise DomainError('IDEMPOTENCY_KEY_REQUIRED',422,'发布需要幂等键')
        with self.uow_factory() as uow: self.authorize(uow,actor,'prompt.manage')
        def command(uow):
            fresh=self.authorize(uow,actor,'prompt.manage')
            row=uow.session.scalar(select(PromptVersion).where(PromptVersion.id==prompt_id).with_for_update())
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'提示词不存在')
            if row.status!='published':
                row.status='published';row.published_by=actor.user_id
                self.audit(uow,fresh,'prompt.publish','prompt',row.id,{'reason':reason,'revision':row.revision_no})
            return ResultRef('prompt_version',row.id,200)
        payload_hash=hashlib.sha256(json.dumps({'prompt_id':prompt_id,'reason':reason},sort_keys=True).encode()).hexdigest()
        result=IdempotencyService(self.uow_factory).execute(actor,'prompt.publish',self.idempotency_key,payload_hash,command)
        with self.uow_factory() as uow:
            return prompt_view(uow.session.get(PromptVersion,result.entity_id))
