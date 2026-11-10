"""一期受控单次执行器：保留历史调用名，任务白名单/校验交给可信网关。"""
from app.ai_runtime.generation_types import GenerationRequest,ValidatedAiResult
from app.ai_runtime.schemas import TASK_TYPES
from app.core.errors import DomainError

class FixedGraphRunner:
    """兼容既有调用方的薄执行入口，不创建图或维护第二套恢复状态。"""
    def __init__(self,gateway,output_types):
        if set(output_types)-set(TASK_TYPES) or 'embedding' in output_types:
            raise ValueError('Unsupported generation task')
        self.gateway=gateway;self.output_types=dict(output_types)

    def run(self,task_type,input_data,config) -> ValidatedAiResult:
        """只执行代码注册的生成任务；来源/schema/配置仍由网关严格核验。"""
        if task_type not in self.output_types:
            raise DomainError('AI_TASK_NOT_REGISTERED',409,'该业务流程尚未注册')
        request=GenerationRequest(task_type=task_type,model_config_id=config.model_config_id,prompt_version_id=config.prompt_version_id,**input_data)
        result=self.gateway.generate(request,self.output_types[task_type],snapshot=config)
        return ValidatedAiResult(result.value.model_dump(mode='json'),result.ai_run_id)
