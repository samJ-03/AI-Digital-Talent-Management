"""岗位匹配类型、证据复验与Decimal权重计算；不使用向量相似度。"""
from dataclasses import dataclass
from decimal import Decimal,ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from app.ai_runtime.generation_types import Evidence
from app.core.errors import DomainError

NAMES={'skills','experience','responsibilities'}

class DimensionScore(BaseModel):
    """缺证据维度使用None，不能以零分代替未知。"""
    model_config=ConfigDict(extra='forbid')
    name: Literal['skills','experience','responsibilities']
    score: float|None=Field(ge=0,le=100,default=None)
    evidence: list[Evidence]=Field(default_factory=list,max_length=100)

class MatchClaim(BaseModel):
    """优势或差距必须携带可复验的事实引文。"""
    model_config=ConfigDict(extra='forbid')
    text: str=Field(min_length=1,max_length=2000)
    evidence: list[Evidence]=Field(min_length=1,max_length=20)

class MatchDraft(BaseModel):
    """模型只能提出维度，不接收或信任模型生成的总分。"""
    model_config=ConfigDict(extra='forbid')
    dimensions: list[DimensionScore]=Field(min_length=3,max_length=3)
    strengths: list[MatchClaim]=Field(max_length=20)
    gaps: list[MatchClaim]=Field(max_length=20)
    citations: list[Evidence]=Field(min_length=1,max_length=100)

@dataclass(frozen=True)
class MatchValidation:
    """业务证据校验结果；不能将无证据的高分用于自动邀请。"""
    valid: bool
    unknown_dimensions: tuple[str,...]
    reasons: tuple[str,...]

class MatchEvidenceValidator:
    """完整原文引用和授权来源双校验，不接受仅岗位证据支撑人才得分。"""
    def validate(self,draft,evidence):
        allowed={e.model_dump_json() for e in evidence};unknown=[];reasons=[]
        if len(draft.dimensions)!=3 or {d.name for d in draft.dimensions}!=NAMES:reasons.append('INVALID_DIMENSIONS')
        citations={e.model_dump_json() for e in draft.citations}
        if not citations<=allowed:reasons.append('FOREIGN_CITATION')
        for dimension in draft.dimensions:
            refs=dimension.evidence
            if dimension.score is None or not refs or not any(e.source_type=='resume_version' for e in refs) or any(e.model_dump_json() not in allowed or e.model_dump_json() not in citations for e in refs):unknown.append(dimension.name)
        for claim in [*draft.strengths,*draft.gaps]:
            if any(e.model_dump_json() not in allowed or e.model_dump_json() not in citations for e in claim.evidence):reasons.append('FOREIGN_CLAIM')
        if unknown:reasons.append('UNKNOWN_DIMENSIONS')
        return MatchValidation(not reasons,tuple(unknown),tuple(reasons))

class MatchScorer:
    """只计算明确且完整的三维分数；权重由已发布岗位提供。"""
    def aggregate(self,dimensions,weights):
        if len(dimensions)!=3 or {d.name for d in dimensions}!=NAMES:raise DomainError('MATCH_DIMENSIONS_INVALID',422,'匹配维度不完整或重复')
        if any(d.score is None for d in dimensions):raise DomainError('MATCH_DIMENSION_UNKNOWN',409,'仍有未知匹配维度')
        from app.jobs.schemas import MatchWeights
        weights=MatchWeights.model_validate(weights.model_dump() if hasattr(weights,'model_dump') else weights)
        return sum((Decimal(str(d.score))*getattr(weights,d.name)/Decimal(100) for d in dimensions),Decimal(0)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
