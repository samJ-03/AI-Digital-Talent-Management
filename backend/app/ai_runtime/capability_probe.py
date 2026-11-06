"""模型配置与受控AI执行：使用合成输入探测供应商协议和实际模型能力。"""
import json
import math
import re
import httpx
from app.ai_runtime.endpoint_policy import EndpointPolicy
from app.ai_runtime.schemas import CapabilityTest

class ProbeFailure(Exception):
    """ProbeFailure：模型配置与受控AI执行中的协作类型。"""
    def __init__(self,code): self.code=code

class CapabilityProbe:
    """Synthetic protocol/capability checks; not a recruitment quality evaluation."""
    def __init__(self,transport=None): self.transport=transport

    def _request(self,client,method,url,body=None,secret=None):
        headers={'Authorization':'Bearer '+secret} if secret else {}
        with client.stream(method,url,json=body,headers=headers) as response:
            if response.status_code in {401,403}: raise ProbeFailure('MODEL_AUTH_FAILED')
            if response.status_code==429: raise ProbeFailure('MODEL_RATE_LIMITED')
            if 300<=response.status_code<400: raise ProbeFailure('MODEL_REDIRECT_DENIED')
            if response.status_code!=200: raise ProbeFailure('MODEL_PROVIDER_ERROR')
            data=bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data)>512*1024: raise ProbeFailure('MODEL_RESPONSE_TOO_LARGE')
            try: result=json.loads(data)
            except (ValueError,RecursionError): raise ProbeFailure('MODEL_OUTPUT_INVALID') from None
            if not isinstance(result,dict): raise ProbeFailure('MODEL_OUTPUT_INVALID')
            return result

    def _vectors(self,vectors,dimension):
        if not isinstance(vectors,list) or len(vectors)!=2: raise ProbeFailure('MODEL_OUTPUT_INVALID')
        actual=len(vectors[0]) if isinstance(vectors[0],list) else 0
        if not 1<=actual<=8192 or dimension is not None and actual!=dimension: raise ProbeFailure('EMBEDDING_DIMENSION_MISMATCH')
        for vector in vectors:
            if not isinstance(vector,list) or len(vector)!=actual: raise ProbeFailure('EMBEDDING_DIMENSION_MISMATCH')
            if any(type(n) not in (int,float) or not math.isfinite(n) for n in vector) or not any(n!=0 for n in vector):
                raise ProbeFailure('MODEL_OUTPUT_INVALID')
        return actual

    def run(self,config,secret=None) -> CapabilityTest:
        """运行本模块定义的受控探测或固定流程。"""
        endpoint=EndpointPolicy().require(config.provider_type,config.base_url,config.model_name)
        if endpoint.family!='ollama' and not secret:
            return CapabilityTest(verified=False,capabilities={},error_code='MODEL_SECRET_MISSING')
        try:
            with httpx.Client(transport=self.transport,timeout=httpx.Timeout(20,connect=5),follow_redirects=False,trust_env=False) as client:
                capabilities={};dimension=None;digest=None
                if endpoint.family=='deepseek':
                    result=self._request(client,'POST',endpoint.base_url+'/chat/completions',{'model':config.model_name,
                        'messages':[{'role':'user','content':'Return exactly this JSON object: {"ok":true}'}],
                        'response_format':{'type':'json_object'},'max_tokens':64,'thinking':{'type':'disabled'}},secret)
                    choice=result['choices'][0]
                    value=json.loads(choice['message']['content'])
                    if choice.get('finish_reason')!='stop' or not isinstance(value,dict) or value.get('ok') is not True:
                        raise ProbeFailure('MODEL_OUTPUT_INVALID')
                    capabilities={'text':True,'json':True,'provider':'deepseek'}
                    returned=result.get('model','')
                    if isinstance(returned,str) and re.fullmatch(r'deepseek-[a-zA-Z0-9_.-]{1,120}',returned): capabilities['returned_model']=returned
                elif endpoint.capability=='embedding':
                    expected=config.embedding_dimension or 1024
                    result=self._request(client,'POST',endpoint.base_url+'/embeddings',{'model':config.model_name,
                        'input':['Python数据分析','酒店前台接待'],'dimensions':expected,'encoding_format':'float'},secret)
                    rows=result['data']
                    if not isinstance(rows,list) or len(rows)!=2 or {r['index'] for r in rows}!={0,1}: raise ProbeFailure('MODEL_OUTPUT_INVALID')
                    dimension=self._vectors([r['embedding'] for r in sorted(rows,key=lambda r:r['index'])],expected)
                    capabilities={'embedding':True,'provider':'dashscope'}
                elif endpoint.capability=='rerank':
                    result=self._request(client,'POST',endpoint.base_url+'/services/rerank/text-rerank/text-rerank',{'model':config.model_name,
                        'input':{'query':'Python数据分析岗位','documents':['Python数据分析工作经验','酒店前台接待工作经验']},'parameters':{'top_n':2,'return_documents':False}},secret)
                    rows=result['output']['results']
                    if not isinstance(rows,list) or len(rows)!=2 or {r['index'] for r in rows}!={0,1}: raise ProbeFailure('MODEL_OUTPUT_INVALID')
                    scores=[r['relevance_score'] for r in rows]
                    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in scores) or scores!=sorted(scores,reverse=True) or rows[0]['index']!=0:
                        raise ProbeFailure('MODEL_OUTPUT_INVALID')
                    capabilities={'rerank':True,'provider':'dashscope'}
                else:
                    tags=self._request(client,'GET',endpoint.base_url+'/api/tags')
                    matched=next((m for m in tags.get('models',[]) if m.get('name') in {config.model_name,config.model_name+':latest'}),None)
                    if matched is None or not re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}',matched.get('digest','')):
                        raise ProbeFailure('MODEL_NOT_AVAILABLE')
                    digest=matched['digest']
                    shown=self._request(client,'POST',endpoint.base_url+'/api/show',{'model':config.model_name})
                    if 'embedding' in shown.get('capabilities',[]):
                        result=self._request(client,'POST',endpoint.base_url+'/api/embed',{'model':config.model_name,'input':['Python数据分析','酒店前台接待'],'truncate':False})
                        dimension=self._vectors(result['embeddings'],config.embedding_dimension)
                        capabilities={'embedding':True,'provider':'ollama'}
                    else:
                        result=self._request(client,'POST',endpoint.base_url+'/api/generate',{'model':config.model_name,'prompt':'Return JSON {"ok":true}','format':'json','stream':False,'options':{'num_predict':64}})
                        if result.get('done') is not True or json.loads(result['response']).get('ok') is not True: raise ProbeFailure('MODEL_OUTPUT_INVALID')
                        capabilities={'text':True,'json':True,'provider':'ollama'}
                capabilities['verified']=True
                return CapabilityTest(verified=True,capabilities=capabilities,model_digest=digest,embedding_dimension=dimension)
        except ProbeFailure as error:
            return CapabilityTest(verified=False,capabilities={},error_code=error.code)
        except httpx.TimeoutException:
            return CapabilityTest(verified=False,capabilities={},error_code='MODEL_TIMEOUT')
        except httpx.HTTPError:
            return CapabilityTest(verified=False,capabilities={},error_code='MODEL_UNAVAILABLE')
        except (ValueError,KeyError,TypeError,IndexError,AttributeError):
            return CapabilityTest(verified=False,capabilities={},error_code='MODEL_OUTPUT_INVALID')
