"""模型配置与受控AI执行：构造对外视图，控制内部字段暴露。"""
from app.ai_runtime.schemas import MaskedModelConfig,PromptView,WorkflowView

def model_view(row):
    """构造model的允许字段视图。"""
    return MaskedModelConfig(id=str(row.id),logical_key=row.logical_key,revision_no=row.revision_no,provider_type=row.provider_type,
        base_url=row.base_url,model_name=row.model_name,model_digest=row.model_digest,capabilities=row.capabilities,
        embedding_dimension=row.embedding_dimension,secret_configured=bool(row.secret_ciphertext),enabled=row.enabled,version=row.row_version)

def prompt_view(row):
    """构造prompt的允许字段视图。"""
    return PromptView(id=str(row.id),task_type=row.task_type,revision_no=row.revision_no,content=row.content,output_schema=row.output_schema,
        status=row.status,published_by=str(row.published_by) if row.published_by else None,version=row.row_version)

def workflow_view(row):
    """构造workflow的允许字段视图。"""
    return WorkflowView(id=str(row.id),task_type=row.task_type,model_config_id=str(row.model_config_id) if row.model_config_id else None,
        prompt_version_id=str(row.prompt_version_id) if row.prompt_version_id else None,enabled=row.enabled,timeout_seconds=row.timeout_seconds,
        max_retries=row.max_retries,config_revision=row.config_revision,version=row.row_version)
