from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')

class ApiEnvelope(BaseModel, Generic[T]):
    code: str = 'OK'
    message: str = '成功'
    data: T
    request_id: str

class HealthView(BaseModel):
    alive: bool

class ReadinessView(BaseModel):
    ready: bool
    dependencies: dict[str, bool]

class MonitorContext(BaseModel):
    authenticated: bool = True

class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

from typing import TypedDict

class SchemaManifest(TypedDict):
    tables: list[str]
    indexes: dict[str, list[dict[str, Any]]]
    foreign_keys: dict[str, list[dict[str, Any]]]

class TaskAccepted(BaseModel):
    task_id: str
    state: str
    poll_url: str
