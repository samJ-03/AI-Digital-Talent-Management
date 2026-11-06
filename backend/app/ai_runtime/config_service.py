"""模型配置与受控AI执行：管理不可变连接修订与启停校验。"""
from dataclasses import dataclass
from sqlalchemy import select,func
from app.ai_runtime.admin_base import AiAdminBase
from app.ai_runtime.endpoint_policy import EndpointPolicy
from app.ai_runtime.models import ModelConfig,WorkflowConfig,PromptVersion
from app.ai_runtime.schemas import TASK_TYPES,ModelConfigCreate,WorkflowWrite
from app.ai_runtime.views import model_view,workflow_view
from app.core.errors import DomainError

@dataclass(frozen=True,slots=True)
class ProbeConfig:
    """ProbeConfig：模型配置与受控AI执行中的协作类型。"""
    provider_type: str
    base_url: str
    model_name: str
    embedding_dimension: int|None

class ModelConfigService(AiAdminBase):
    """ModelConfigService：模型配置与受控AI执行中的协作类型。"""
    def __init__(self,uow_factory,cipher,probe):
        super().__init__(uow_factory);self.cipher=cipher;self.probe=probe

    def create_revision(self,actor,cmd: ModelConfigCreate):
        """创建不可变连接修订，秘密仅以密文持久化。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        with self.transaction(actor,'model.manage') as (uow,fresh):
            endpoint=EndpointPolicy().require(cmd.provider_type,cmd.base_url,cmd.model_name)
            list(uow.session.scalars(select(WorkflowConfig).order_by(WorkflowConfig.id).with_for_update()))
            revision=(uow.session.scalar(select(func.max(ModelConfig.revision_no)).where(ModelConfig.logical_key==cmd.logical_key)) or 0)+1
            secret=None
            if cmd.secret is not None:
                if self.cipher is None: raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用')
                secret=self.cipher.encrypt(cmd.secret.get_secret_value())
            row=ModelConfig(logical_key=cmd.logical_key,revision_no=revision,provider_type=cmd.provider_type,
                base_url=endpoint.base_url,model_name=cmd.model_name,embedding_dimension=cmd.embedding_dimension,
                secret_ciphertext=secret,enabled=False,capabilities={})
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'model.create','model_config',row.id,{'revision':revision,'changed_fields':['connection','model']})
            return model_view(row)

    def test(self,actor,config_id: int):
        """验证连接能力或提交异步配置测试；以返回状态为准。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'model.manage')
            row=uow.session.get(ModelConfig,config_id)
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'模型配置不存在')
            EndpointPolicy().require(row.provider_type,row.base_url,row.model_name)
            version=row.row_version
            config=ProbeConfig(row.provider_type,row.base_url,row.model_name,row.embedding_dimension)
            ciphertext=row.secret_ciphertext
        secret=None
        if ciphertext:
            if self.cipher is None: raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用')
            secret=self.cipher.decrypt(ciphertext)
        result=self.probe.run(config,secret)
        with self.transaction(actor,'model.manage') as (uow,fresh):
            row=uow.session.scalar(select(ModelConfig).where(ModelConfig.id==config_id).with_for_update())
            if row is None or row.row_version!=version: raise DomainError('VERSION_CONFLICT',409,'模型配置已更新，请重新验证')
            row.capabilities=dict(result.capabilities)
            row.enabled=result.verified
            row.model_digest=result.model_digest
            if result.embedding_dimension is not None: row.embedding_dimension=result.embedding_dimension
            uow.session.flush()
            self.audit(uow,fresh,'model.test','model_config',row.id,{'enabled':row.enabled,'error_code':result.error_code})
        return result

class WorkflowConfigService(AiAdminBase):
    """WorkflowConfigService：模型配置与受控AI执行中的协作类型。"""
    def configure(self,actor,task_type: str,cmd: WorkflowWrite,expected_version: int):
        """以乐观锁更新固定流程配置并校验关联修订。 actor为服务端解析的操作者，资源范围仍由服务层验证。expected_version必须匹配当前row_version，否则拒绝覆盖。"""
        if task_type not in TASK_TYPES: raise DomainError('INVALID_TASK_TYPE',422,'不支持的固定流程')
        with self.transaction(actor,'workflow.manage') as (uow,fresh):
            row=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type==task_type).with_for_update())
            if row is None: raise DomainError('WORKFLOW_NOT_INITIALIZED',503,'固定流程尚未初始化')
            if row.row_version!=expected_version: raise DomainError('VERSION_CONFLICT',409,'流程配置已更新')
            model=uow.session.get(ModelConfig,cmd.model_config_id) if cmd.model_config_id else None
            prompt=uow.session.get(PromptVersion,cmd.prompt_version_id) if cmd.prompt_version_id else None
            if cmd.model_config_id and model is None or cmd.prompt_version_id and prompt is None:
                raise DomainError('RESOURCE_NOT_FOUND',404,'关联配置不存在')
            if prompt and prompt.task_type!=task_type:
                raise DomainError('PROMPT_TASK_MISMATCH',422,'提示词与流程类型不一致')
            if cmd.enabled:
                needed='embedding' if task_type=='embedding' else 'text'
                if model is None or not model.enabled or model.capabilities.get('verified') is not True or model.capabilities.get(needed) is not True:
                    raise DomainError('MODEL_NOT_VERIFIED',409,'需要通过能力检查的模型')
                if task_type!='embedding' and (prompt is None or prompt.status!='published' or model.capabilities.get('json') is not True):
                    raise DomainError('PROMPT_NOT_PUBLISHED',409,'需要已发布的匹配提示词和结构化输出能力')
            row.model_config_id=cmd.model_config_id;row.prompt_version_id=cmd.prompt_version_id;row.enabled=cmd.enabled
            row.timeout_seconds=cmd.timeout_seconds;row.max_retries=cmd.max_retries;row.config_revision+=1
            uow.session.flush()
            self.audit(uow,fresh,'workflow.configure','workflow',row.id,{'enabled':row.enabled,'revision':row.config_revision})
            return workflow_view(row)

    def list(self,actor):
        """读取当前服务允许展示的对象集合。 actor为服务端解析的操作者，资源范围仍由服务层验证。"""
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'workflow.manage')
            return [workflow_view(row) for row in uow.session.scalars(select(WorkflowConfig).where(WorkflowConfig.task_type.in_(TASK_TYPES)).order_by(WorkflowConfig.id))]
