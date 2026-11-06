"""平台开发工具：验证model transport的正常与失败场景；测试数据仅用于隔离环境。"""
import httpx
import pytest
from app.ai_runtime.capability_probe import CapabilityProbe,ProbeFailure
from app.ai_runtime.generation_types import ProviderConnection,GenerationRequest
from app.ai_runtime.ollama_adapter import OllamaAdapter
from app.ai_runtime.validation import OutputInvalid

@pytest.mark.parametrize('body',[b'not-json',b'[]',b'{'])
def test_provider_envelope_malformed_is_invalid(body):
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=body))) as client:
        with pytest.raises(ProbeFailure) as exc: CapabilityProbe()._request(client,'POST','https://api.deepseek.com/v1/chat/completions')
    assert exc.value.code=='MODEL_OUTPUT_INVALID'

def test_response_size_capped():
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*(512*1024+1)))) as client:
        with pytest.raises(ProbeFailure) as exc: CapabilityProbe()._request(client,'POST','https://api.deepseek.com/v1/chat/completions')
    assert exc.value.code=='MODEL_RESPONSE_TOO_LARGE'

def test_local_digest_changed_no_generation():
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'models':[{'name':'local-model','digest':'changed'}]})
    connection=ProviderConnection('ollama','http://host.docker.internal:11434','local-model',None,'approved',10)
    req=GenerationRequest(task_type='match',model_config_id=1,prompt_version_id=1,input_refs=[{'source_type':'resume','source_id':'1'}],evidence=[{'source_type':'resume','source_id':'1','locator':'page1','quote':'Python'}],output_schema={'type':'object'})
    with pytest.raises(ProbeFailure) as exc: OllamaAdapter(connection,'prompt',httpx.MockTransport(handler)).generate(req)
    assert exc.value.code=='MODEL_DIGEST_CHANGED' and len(calls)==1
