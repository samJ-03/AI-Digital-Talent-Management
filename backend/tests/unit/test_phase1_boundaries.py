"""一期轻量执行与公开边界：不需要数据库或真实模型。"""
from pathlib import Path
import builtins,runpy
from unittest.mock import patch
from pydantic import BaseModel
from app.ai_runtime.generation_types import AiConfigSnapshot,GenerationResult


def test_fixed_execution_does_not_require_graph_runtime():
    """一个受控生成不应强制安装或加载图编排运行时。"""
    original=builtins.__import__
    def blocked(name,*args,**kwargs):
        if name=='langgraph' or name.startswith('langgraph.'):raise ImportError('Graph runtime is optional in phase one')
        return original(name,*args,**kwargs)
    path=Path(__file__).resolve().parents[2]/'app/ai_runtime/graphs.py'
    with patch('builtins.__import__',blocked):module=runpy.run_path(str(path))
    class Reply(BaseModel):value: str
    calls=[]
    class Gateway:
        def generate(self,request,output_type,*,snapshot):
            calls.append((request,snapshot));return GenerationResult(Reply(value='validated'),7)
    snapshot=AiConfigSnapshot(1,2,30,0,1)
    result=module['FixedGraphRunner'](Gateway(),{'match':Reply}).run('match',{'input_refs':[{'source_type':'resume_version','source_id':'1'}],'evidence':[{'source_type':'resume_version','source_id':'1','locator':'skills.0','quote':'Python'}],'output_schema':Reply.model_json_schema()},snapshot)
    assert result.output=={'value':'validated'} and result.ai_run_id==7 and len(calls)==1
    assert calls[0][0].model_config_id==1 and calls[0][1]==snapshot


def test_public_cross_domain_boundaries_are_explicit():
    """跨领域消费者不应依赖另一个服务的私有API。"""
    from app.evaluation.service import EvaluationService
    from app.talents.candidate_service import CandidateService
    assert callable(getattr(EvaluationService,'is_current',None))
    assert callable(getattr(EvaluationService,'resource_scope',None))
    assert callable(getattr(CandidateService,'resume_view',None))


def test_semantic_services_are_opt_in_without_deleting_definitions():
    import yaml
    root=Path(__file__).resolve().parents[3]
    services=yaml.safe_load((root/'infra/compose.yaml').read_text())['services']
    assert services['milvus']['profiles']==['semantic']
    assert services['etcd']['profiles']==['semantic']
    for name in ['mysql','redis','minio','api','worker','scheduler','mailpit']:
        assert not services[name].get('profiles')
