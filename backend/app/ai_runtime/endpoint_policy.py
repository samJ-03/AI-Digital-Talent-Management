"""模型配置与受控AI执行：校验供应商地址与模型白名单，拒绝重定向目的地及未授权代理。"""
from dataclasses import dataclass
from urllib.parse import urlsplit
from app.core.errors import DomainError

@dataclass(frozen=True,slots=True)
class ProviderEndpoint:
    """ProviderEndpoint：模型配置与受控AI执行中的协作类型。"""
    family: str
    base_url: str
    capability: str

class EndpointPolicy:
    """EndpointPolicy：模型配置与受控AI执行中的协作类型。"""
    def require(self,provider_type: str,base_url: str,model_name: str) -> ProviderEndpoint:
        """验证权限或地址策略，不满足时失败关闭。"""
        try: url=urlsplit(base_url)
        except ValueError: raise DomainError('MODEL_URL_DENIED',422,'模型地址不在允许范围内') from None
        if (url.username or url.password or url.query or url.fragment or '%' in base_url or '\\' in base_url
            or any(ord(ch)<33 for ch in base_url)):
            raise DomainError('MODEL_URL_DENIED',422,'模型地址不在允许范围内')
        origin=url.scheme+'://'+url.netloc
        path=url.path.rstrip('/')
        if provider_type=='compatible_http':
            if origin=='https://api.deepseek.com' and path in {'','/v1'} and model_name=='deepseek-flash':
                return ProviderEndpoint('deepseek','https://api.deepseek.com/v1','text')
            if origin=='https://dashscope.aliyuncs.com' and path in {'/compatible-mode/v1','/api/v1'}:
                if model_name=='text-embedding-v3': return ProviderEndpoint('dashscope','https://dashscope.aliyuncs.com/compatible-mode/v1','embedding')
                if model_name=='qwen3-rerank': return ProviderEndpoint('dashscope','https://dashscope.aliyuncs.com/api/v1','rerank')
        elif provider_type=='ollama' and origin=='http://host.docker.internal:11434' and path=='':
            return ProviderEndpoint('ollama',origin,'local')
        raise DomainError('MODEL_URL_DENIED',422,'模型地址或模型不在允许范围内')
