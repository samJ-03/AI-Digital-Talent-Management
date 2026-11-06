"""模型配置与受控AI执行：定义网关输入、证据、配置快照和结果类型。"""
from dataclasses import dataclass
from typing import Generic, TypeVar, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue

T=TypeVar('T',bound=BaseModel)

class Evidence(BaseModel):
    """Evidence：模型配置与受控AI执行中的输入输出数据契约。"""
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    source_type: str=Field(min_length=1,max_length=50)
    source_id: str=Field(min_length=1,max_length=64)
    locator: str=Field(min_length=1,max_length=200)
    quote: str=Field(min_length=1,max_length=20000)

class GenerationRequest(BaseModel):
    """GenerationRequest：模型配置与受控AI执行中的输入输出数据契约。"""
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    task_type: Literal['extract','profile','match','question_generation','grade','knowledge_ask']
    model_config_id: int=Field(gt=0)
    prompt_version_id: int=Field(gt=0)
    input_refs: list[dict[str,str]]=Field(min_length=1,max_length=100)
    evidence: list[Evidence]=Field(min_length=1,max_length=100)
    output_schema: dict[str,JsonValue]

@dataclass(frozen=True)
class GenerationResult(Generic[T]):
    """GenerationResult：模型配置与受控AI执行中的协作类型。"""
    value: T
    ai_run_id: int

@dataclass(frozen=True)
class EmbeddingBatch:
    """EmbeddingBatch：模型配置与受控AI执行中的协作类型。"""
    vectors: list[list[float]]
    dimension: int
    model_digest: str|None
    model_config_id: int
    revision_no: int
    model_name: str

@dataclass(frozen=True)
class AiConfigSnapshot:
    """AiConfigSnapshot：模型配置与受控AI执行中的协作类型。"""
    model_config_id: int
    prompt_version_id: int
    timeout: int
    max_retries: int
    config_revision: int

@dataclass(frozen=True)
class ValidatedAiResult:
    """ValidatedAiResult：模型配置与受控AI执行中的协作类型。"""
    output: dict[str,JsonValue]
    ai_run_id: int

@dataclass(frozen=True,repr=False)
class ProviderConnection:
    """ProviderConnection：模型配置与受控AI执行中的协作类型。"""
    provider_type: str
    base_url: str
    model_name: str
    secret: str|None
    model_digest: str|None
    timeout: int

@dataclass(frozen=True,repr=False)
class RawModelResponse:
    """RawModelResponse：模型配置与受控AI执行中的协作类型。"""
    content: str
