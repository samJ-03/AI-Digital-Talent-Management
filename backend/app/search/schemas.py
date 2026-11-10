"""语义检索边界类型；相关度不是岗位匹配分。"""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

@dataclass(frozen=True)
class VectorRecord:
    """向量仅携带授权引用与摘要，不存简历或私有评价正文。"""
    key: str
    entity_id: int
    entity_type: str
    scope: str
    department_id: int|None
    content_hash: str
    vector: list[float]

@dataclass(frozen=True)
class SearchScope:
    """由服务端创建的范围，禁止接收自由Milvus过滤表达式。"""
    entity_type: str='profile'
    shared: bool=True
    department_ids: tuple[int,...]=()

@dataclass(frozen=True)
class VectorHit:
    """检索命中仍须MySQL复验。"""
    entity_id: int
    relevance: float
    key: str
    content_hash: str

@dataclass(frozen=True)
class IndexEntityRef:
    """内部可信引用，人才索引仅支持共享profile。"""
    type: str
    id: int

@dataclass(frozen=True)
class IndexSyncResult:
    """可重建索引的持久化同步结果。"""
    state: str
    record_id: int
    collection_name: str

class TalentFilter(BaseModel):
    """共享人才筛选只允许公开履历条件，不提供部门私有评价过滤。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    skills: list[str]=Field(default_factory=list,max_length=30)
    education: str|None=Field(default=None,max_length=100)
    major: str|None=Field(default=None,max_length=200)
    page_size: int=Field(default=20,ge=1,le=100)

class TalentSearchQuery(BaseModel):
    """搜索是无写副作用的POST，仍要求HR会话与CSRF。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    query: str=Field(min_length=1,max_length=2000)
    filters: TalentFilter=Field(default_factory=TalentFilter)
    page_size: int=Field(default=20,ge=1,le=100)

class Recommendation(BaseModel):
    """只推荐，不加入关系或生成邀请。"""
    candidate_id: str
    profile_id: str
    semantic_relevance: float
    matched_evidence: list[dict]

class SemanticSearchResult(BaseModel):
    """故障抛503，不返回degraded空列表伪装成功。"""
    items: list[Recommendation]
    degraded: Literal[False]=False
    query: str
