import json
from typing import Literal,Any
from pydantic import BaseModel,ConfigDict,Field,SecretStr,field_validator
from jsonschema import Draft202012Validator,SchemaError

TASK_TYPES=('extract','profile','match','question_generation','grade','knowledge_ask','embedding')
TaskType=Literal['extract','profile','match','question_generation','grade','knowledge_ask','embedding']

class InputModel(BaseModel):
    model_config=ConfigDict(extra='forbid')

class ModelConfigCreate(InputModel):
    logical_key: str=Field(min_length=1,max_length=100,pattern=r'^[a-zA-Z0-9_.-]+$')
    provider_type: Literal['ollama','compatible_http']
    base_url: str=Field(min_length=1,max_length=500)
    model_name: str=Field(min_length=1,max_length=150,pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.:/-]*$')
    secret: SecretStr|None=Field(default=None,min_length=1,max_length=8192)
    embedding_dimension: Literal[64,128,256,512,768,1024]|None=None

class MaskedModelConfig(BaseModel):
    id: str
    logical_key: str
    revision_no: int
    provider_type: str
    base_url: str
    model_name: str
    model_digest: str|None
    capabilities: dict[str,Any]
    embedding_dimension: int|None
    secret_configured: bool
    enabled: bool
    version: int

class CapabilityTest(BaseModel):
    verified: bool
    capabilities: dict[str,Any]
    model_digest: str|None=None
    embedding_dimension: int|None=None
    error_code: str|None=None

class PromptCreate(InputModel):
    task_type: TaskType
    content: str=Field(min_length=1,max_length=32000)
    output_schema: dict[str,Any]
    @field_validator('output_schema')
    @classmethod
    def offline_schema(cls,value):
        if len(json.dumps(value))>65536: raise ValueError('Schema is too large')
        def walk(node,depth=0):
            if depth>16: raise ValueError('Schema is too deep')
            if isinstance(node,dict):
                for key,item in node.items():
                    if key in {'$ref','$dynamicRef'} and (not isinstance(item,str) or not item.startswith('#')):
                        raise ValueError('Remote schema references are not allowed')
                    if key=='$id': raise ValueError('Custom schema resource identifiers are not allowed')
                    walk(item,depth+1)
            elif isinstance(node,list):
                for item in node: walk(item,depth+1)
        walk(value)
        try: Draft202012Validator.check_schema(value)
        except SchemaError: raise ValueError('Invalid JSON Schema') from None
        if value.get('type')!='object': raise ValueError('Output root must be an object')
        return value

class PublishCommand(InputModel):
    reason: str=Field(min_length=1,max_length=500)

class PromptView(BaseModel):
    id: str
    task_type: str
    revision_no: int
    content: str
    output_schema: dict[str,Any]
    status: str
    published_by: str|None
    version: int

class WorkflowWrite(InputModel):
    model_config_id: int|None=Field(default=None,gt=0)
    prompt_version_id: int|None=Field(default=None,gt=0)
    enabled: bool
    timeout_seconds: int=Field(default=60,ge=5,le=180)
    max_retries: int=Field(default=1,ge=0,le=2)

class WorkflowView(BaseModel):
    id: str
    task_type: str
    model_config_id: str|None
    prompt_version_id: str|None
    enabled: bool
    timeout_seconds: int
    max_retries: int
    config_revision: int
    version: int
