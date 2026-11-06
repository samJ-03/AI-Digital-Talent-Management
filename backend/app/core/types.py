"""公共基础设施：声明公共响应和跨模块类型契约。"""
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')

class ApiEnvelope(BaseModel, Generic[T]):
    """ApiEnvelope：公共基础设施中的输入输出数据契约。"""
    code: str = 'OK'
    message: str = '成功'
    data: T
    request_id: str

class HealthView(BaseModel):
    """HealthView：公共基础设施中的输入输出数据契约。"""
    alive: bool

class ReadinessView(BaseModel):
    """ReadinessView：公共基础设施中的输入输出数据契约。"""
    ready: bool
    dependencies: dict[str, bool]

class MonitorContext(BaseModel):
    """MonitorContext：公共基础设施中的输入输出数据契约。"""
    authenticated: bool = True

class PageQuery(BaseModel):
    """PageQuery：公共基础设施中的输入输出数据契约。"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class Page(BaseModel, Generic[T]):
    """Page：公共基础设施中的输入输出数据契约。"""
    items: list[T]
    total: int
    page: int
    page_size: int

from typing import TypedDict

class SchemaManifest(TypedDict):
    """SchemaManifest：公共基础设施中的输入输出数据契约。"""
    tables: list[str]
    indexes: dict[str, list[dict[str, Any]]]
    foreign_keys: dict[str, list[dict[str, Any]]]

class TaskAccepted(BaseModel):
    """TaskAccepted：公共基础设施中的输入输出数据契约。"""
    task_id: str
    state: str
    poll_url: str
