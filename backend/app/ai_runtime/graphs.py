"""模型配置与受控AI执行：用代码注册固定LangGraph流程，不向模型开放业务写工具。"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.ai_runtime.generation_types import GenerationRequest, ValidatedAiResult
from app.ai_runtime.schemas import TASK_TYPES
from app.core.errors import DomainError

class _State(TypedDict,total=False):
    """_State：模型配置与受控AI执行中的输入输出数据契约。"""
    request: GenerationRequest
    result: object

class FixedGraphRunner:
    """Code-registered output contracts only; no user graphs or side-effect tools."""
    def __init__(self,gateway,output_types):
        if set(output_types)-set(TASK_TYPES) or 'embedding' in output_types:
            raise ValueError('Unsupported generation task')
        self.gateway=gateway;self.output_types=dict(output_types)

    def run(self,task_type,input_data,config) -> ValidatedAiResult:
        """运行本模块定义的受控探测或固定流程。"""
        if task_type not in self.output_types:
            raise DomainError('AI_TASK_NOT_REGISTERED',409,'该业务流程尚未注册')
        request=GenerationRequest(task_type=task_type,model_config_id=config.model_config_id,
            prompt_version_id=config.prompt_version_id,**input_data)
        def invoke(state):
            return {'result':self.gateway.generate(state['request'],self.output_types[task_type],snapshot=config)}
        graph=StateGraph(_State)
        graph.add_node('invoke_and_validate',invoke)
        graph.add_edge(START,'invoke_and_validate');graph.add_edge('invoke_and_validate',END)
        result=graph.compile().invoke({'request':request},config={'recursion_limit':3})['result']
        return ValidatedAiResult(result.value.model_dump(mode='json'),result.ai_run_id)
