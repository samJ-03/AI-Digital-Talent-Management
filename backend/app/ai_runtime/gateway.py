import hashlib
import json
import time
import httpx
from sqlalchemy import select
from app.ai_runtime.capability_probe import CapabilityProbe, ProbeFailure
from app.ai_runtime.endpoint_policy import EndpointPolicy
from app.ai_runtime.generation_types import GenerationResult, EmbeddingBatch, ProviderConnection
from app.ai_runtime.models import AiRun, ModelConfig, PromptVersion, WorkflowConfig
from app.ai_runtime.ollama_adapter import OllamaAdapter
from app.ai_runtime.validation import OutputInvalid, validate_output, validate_vectors
from app.core.errors import DomainError

class ModelGateway:
    """Internal capability: callers must authorize persisted source references first."""
    def __init__(self,uow_factory,cipher,transport=None):
        self.uow_factory=uow_factory;self.cipher=cipher;self.transport=transport

    def _load(self,uow,task_type,model_id,prompt_id=None,snapshot=None):
        workflow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type==task_type))
        model=uow.session.get(ModelConfig,model_id)
        if (workflow is None or not workflow.enabled or workflow.model_config_id!=model_id
            or model is None or not model.enabled or model.capabilities.get('verified') is not True):
            raise DomainError('AI_WORKFLOW_UNAVAILABLE',409,'模型流程未就绪')
        if snapshot is not None and (snapshot.model_config_id!=model_id or snapshot.prompt_version_id!=prompt_id
            or snapshot.config_revision!=workflow.config_revision or snapshot.timeout!=workflow.timeout_seconds
            or snapshot.max_retries!=workflow.max_retries):
            raise DomainError('AI_CONFIG_STALE',409,'模型流程配置已变更')
        if not 5<=workflow.timeout_seconds<=180 or not 0<=workflow.max_retries<=2:
            raise DomainError('AI_CONFIG_INVALID',409,'模型流程配置无效')
        required=('embedding',) if task_type=='embedding' else ('text','json')
        if not all(model.capabilities.get(k) is True for k in required):
            raise DomainError('AI_CAPABILITY_MISMATCH',409,'模型能力不匹配')
        EndpointPolicy().require(model.provider_type,model.base_url,model.model_name)
        secret=None
        if model.secret_ciphertext:
            if self.cipher is None: raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用')
            secret=self.cipher.decrypt(model.secret_ciphertext)
        connection=ProviderConnection(model.provider_type,model.base_url,model.model_name,secret,
            model.model_digest,max(1,workflow.timeout_seconds//(workflow.max_retries+1)))
        prompt=None
        if task_type!='embedding':
            prompt=uow.session.get(PromptVersion,prompt_id)
            if workflow.prompt_version_id!=prompt_id or prompt is None or prompt.status!='published' or prompt.task_type!=task_type:
                raise DomainError('AI_PROMPT_MISMATCH',409,'提示词版本不匹配')
        return workflow,model,prompt,connection

    def _finish(self,run_id,state,started,output=None,code=None):
        with self.uow_factory() as uow:
            row=uow.session.get(AiRun,run_id)
            row.state=state;row.validated_output=output;row.error_code=code
            row.duration_ms=min(int((time.monotonic()-started)*1000),4294967295)
            uow.commit()

    def generate(self,request,output_type,*,snapshot=None):
        payload=request.model_dump(mode='json')
        encoded=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        if len(encoded)>256*1024: raise DomainError('AI_INPUT_TOO_LARGE',422,'模型输入超出限制')
        evidence=[e.model_dump() for e in request.evidence]
        # No cross-reference may be smuggled into evidence beyond the caller's authorized refs.
        if any(set(ref)!={'source_type','source_id'} or not all(v.strip() for v in ref.values()) for ref in request.input_refs):
            raise DomainError('AI_SOURCE_MISMATCH',422,'模型输入来源不匹配')
        if any(not any(ref.get('source_type')==e['source_type'] and ref.get('source_id')==e['source_id'] for ref in request.input_refs) for e in evidence):
            raise DomainError('AI_SOURCE_MISMATCH',422,'模型输入来源不匹配')
        with self.uow_factory() as uow:
            workflow,model,prompt,connection=self._load(uow,request.task_type,request.model_config_id,request.prompt_version_id,snapshot)
            if request.output_schema!=prompt.output_schema:
                raise DomainError('AI_SCHEMA_MISMATCH',422,'输出契约与发布版本不一致')
            system=prompt.content;schema=prompt.output_schema;retries=workflow.max_retries
            row=AiRun(task_type=request.task_type,model_config_id=model.id,prompt_version_id=prompt.id,
                input_hash=hashlib.sha256(encoded).hexdigest(),source_refs=request.input_refs,state='running')
            uow.session.add(row);uow.session.flush();run_id=row.id;uow.commit()
        started=time.monotonic()
        try:
            for attempt in range(retries+1):
                try:
                    raw=OllamaAdapter(connection,system,self.transport).generate(request)
                    break
                except (httpx.TimeoutException,httpx.NetworkError,ProbeFailure) as exc:
                    code=exc.code if isinstance(exc,ProbeFailure) else 'MODEL_TRANSPORT_FAILED'
                    if attempt==retries or code not in {'MODEL_TRANSPORT_FAILED','MODEL_RATE_LIMITED','MODEL_PROVIDER_ERROR'}: raise
            value=validate_output(raw.content,output_type,schema,evidence)
            output=value.model_dump(mode='json')
        except OutputInvalid:
            self._finish(run_id,'invalid',started,code='MODEL_OUTPUT_INVALID')
            raise DomainError('MODEL_OUTPUT_INVALID',422,'模型输出未通过验证') from None
        except Exception as exc:
            code=exc.code if isinstance(exc,ProbeFailure) else 'MODEL_TRANSPORT_FAILED'
            state='invalid' if code=='MODEL_OUTPUT_INVALID' else 'failed'
            self._finish(run_id,state,started,code=code)
            raise DomainError(code,502,'模型调用未成功') from None
        self._finish(run_id,'succeeded',started,output=output)
        return GenerationResult(value,run_id)

    def embed(self,texts: list[str],model_config_id: int) -> EmbeddingBatch:
        if (not isinstance(texts,list) or not 1<=len(texts)<=10
            or any(not isinstance(t,str) or not t.strip() or len(t.encode('utf8'))>20000 for t in texts)):
            raise DomainError('AI_INPUT_INVALID',422,'向量输入无效')
        with self.uow_factory() as uow:
            workflow,model,_,connection=self._load(uow,'embedding',model_config_id)
            dimension=model.embedding_dimension;revision=model.revision_no
        endpoint=EndpointPolicy().require(connection.provider_type,connection.base_url,connection.model_name)
        try:
            with httpx.Client(transport=self.transport,timeout=httpx.Timeout(connection.timeout,connect=5),follow_redirects=False,trust_env=False) as client:
                probe=CapabilityProbe()
                if endpoint.family=='ollama':
                    adapter=OllamaAdapter(connection,'',self.transport);adapter._digest(client,endpoint)
                    result=probe._request(client,'POST',endpoint.base_url+'/api/embed',{'model':connection.model_name,'input':texts,'truncate':False})
                    vectors=result.get('embeddings');adapter._digest(client,endpoint)
                elif endpoint.capability=='embedding':
                    if not connection.secret: raise ProbeFailure('MODEL_SECRET_MISSING')
                    result=probe._request(client,'POST',endpoint.base_url+'/embeddings',{'model':connection.model_name,
                        'input':texts,'dimensions':dimension,'encoding_format':'float'},connection.secret)
                    rows=result.get('data')
                    if (not isinstance(rows,list) or len(rows)!=len(texts) or any(not isinstance(r,dict) or type(r.get('index')) is not int for r in rows)
                        or {r['index'] for r in rows}!=set(range(len(texts)))): raise OutputInvalid()
                    vectors=[r.get('embedding') for r in sorted(rows,key=lambda r:r['index'])]
                else: raise ProbeFailure('MODEL_CAPABILITY_MISMATCH')
                actual=validate_vectors(vectors,len(texts),dimension)
        except Exception as exc:
            code=exc.code if isinstance(exc,ProbeFailure) else 'MODEL_OUTPUT_INVALID' if isinstance(exc,OutputInvalid) else 'MODEL_TRANSPORT_FAILED'
            raise DomainError(code,502,'向量调用未成功') from None
        return EmbeddingBatch(vectors,actual,connection.model_digest,model_config_id,revision,connection.model_name)
