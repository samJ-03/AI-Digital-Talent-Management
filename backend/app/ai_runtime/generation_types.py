from dataclasses import dataclass
from typing import Generic, TypeVar, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue

T=TypeVar('T',bound=BaseModel)

class Evidence(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    source_type: str=Field(min_length=1,max_length=50)
    source_id: str=Field(min_length=1,max_length=64)
    locator: str=Field(min_length=1,max_length=200)
    quote: str=Field(min_length=1,max_length=20000)

class GenerationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    task_type: Literal['extract','profile','match','question_generation','grade','knowledge_ask']
    model_config_id: int=Field(gt=0)
    prompt_version_id: int=Field(gt=0)
    input_refs: list[dict[str,str]]=Field(min_length=1,max_length=100)
    evidence: list[Evidence]=Field(min_length=1,max_length=100)
    output_schema: dict[str,JsonValue]

@dataclass(frozen=True)
class GenerationResult(Generic[T]):
    value: T
    ai_run_id: int

@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    dimension: int
    model_digest: str|None
    model_config_id: int
    revision_no: int
    model_name: str

@dataclass(frozen=True)
class AiConfigSnapshot:
    model_config_id: int
    prompt_version_id: int
    timeout: int
    max_retries: int
    config_revision: int

@dataclass(frozen=True)
class ValidatedAiResult:
    output: dict[str,JsonValue]
    ai_run_id: int

@dataclass(frozen=True,repr=False)
class ProviderConnection:
    provider_type: str
    base_url: str
    model_name: str
    secret: str|None
    model_digest: str|None
    timeout: int

@dataclass(frozen=True,repr=False)
class RawModelResponse:
    content: str
