from types import SimpleNamespace
import httpx
import pytest
from cryptography.fernet import Fernet
from app.ai_runtime.capability_probe import CapabilityProbe
from app.ai_runtime.endpoint_policy import EndpointPolicy
from app.core.errors import DomainError
from app.core.secrets import SecretCipher

def config(model='text-embedding-v3'):
    return SimpleNamespace(provider_type='compatible_http',base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',model_name=model,embedding_dimension=64)

def test_embedding_capability_checks_full_batch_dimensions_and_values():
    def valid(request): return httpx.Response(200,json={'data':[{'index':1,'embedding':[0.5]*64},{'index':0,'embedding':[0.25]*64}]})
    result=CapabilityProbe(httpx.MockTransport(valid)).run(config(),'synthetic-key')
    assert result.verified and result.embedding_dimension==64 and result.model_digest is None
    def mismatch(request): return httpx.Response(200,json={'data':[{'index':0,'embedding':[0.5]*64},{'index':1,'embedding':[0.25]*63}]})
    result=CapabilityProbe(httpx.MockTransport(mismatch)).run(config(),'synthetic-key')
    assert not result.verified and result.error_code=='EMBEDDING_DIMENSION_MISMATCH'

def test_redirect_is_never_followed_with_a_credential():
    requests=[]
    def redirect(request):
        requests.append(request)
        return httpx.Response(302,headers={'Location':'https://evil.example/collect'})
    result=CapabilityProbe(httpx.MockTransport(redirect)).run(config(),'synthetic-key')
    assert not result.verified and result.error_code=='MODEL_REDIRECT_DENIED'
    assert len(requests)==1 and requests[0].url.host=='dashscope.aliyuncs.com'

@pytest.mark.parametrize('url',['https://user:password@api.deepseek.com/v1','https://api.deepseek.com:8443/v1','https://api.deepseek.com/v1?token=x','https://api.deepseek.com.evil.example/v1','https://api.openai-proxy.org/v1','http://127.0.0.1:8000'])
def test_unapproved_endpoints_denied(url):
    with pytest.raises(DomainError): EndpointPolicy().require('compatible_http',url,'deepseek-flash')

def test_encryption_tamper_and_wrong_master_key_fail_closed():
    cipher=SecretCipher(Fernet.generate_key().decode())
    value=cipher.encrypt('synthetic-secret')
    assert cipher.decrypt(value)=='synthetic-secret'
    other=SecretCipher(Fernet.generate_key().decode())
    for altered in (value,'v1.'+value[3:-2]+'XX'):
        with pytest.raises(DomainError) as error: other.decrypt(altered)
        assert error.value.code=='SECRET_DECRYPT_FAILED'

def test_provider_error_does_not_echo_raw_error_or_credentials():
    def error(request): return httpx.Response(401,json={'error':'raw upstream details synthetic-key'})
    result=CapabilityProbe(httpx.MockTransport(error)).run(config(),'synthetic-key')
    assert result.error_code=='MODEL_AUTH_FAILED'
    assert 'synthetic-key' not in result.model_dump_json()
