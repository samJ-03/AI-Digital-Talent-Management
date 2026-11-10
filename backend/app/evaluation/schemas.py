"""纯筛选类型：复用已发布的岗位条件语言，结果保留证据及版本口径。"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel,ConfigDict,JsonValue
from app.jobs.schemas import Condition
from app.ingestion.extraction_types import EmploymentFact
from app.ai_runtime.generation_types import Evidence

ScreeningCondition=Condition
Employment=EmploymentFact


@dataclass(frozen=True)
class EducationValue:
    """规范层次；高中与中专同层次，但eq仍区分不同类型。"""
    code: str
    rank: int


@dataclass(frozen=True)
class MajorResolution:
    """只有版本化词典精确别名返回确定结果，不做模糊概率猜测。"""
    canonical: str|None
    confidence: Decimal
    needs_review: bool


@dataclass(frozen=True)
class ExperienceBounds:
    """完整月覆盖的保守上下界；任何缺失/损坏日期整体返回None。"""
    min_years: Decimal
    max_years: Decimal


class ScreeningDetail(BaseModel):
    """一项冻结条件的观察、结论、原文证据和固定安全原因。"""
    model_config=ConfigDict(extra='forbid')
    condition_key: str
    required: bool
    expected: JsonValue
    actual: JsonValue|None
    result: Literal['met','unmet','unknown']
    evidence: list[Evidence]
    reason_code: str


class ScreeningReport(BaseModel):
    """三态总结果不改变人才、应聘或邀请状态。"""
    model_config=ConfigDict(extra='forbid')
    result: Literal['pass','fail','unknown']
    details: list[ScreeningDetail]
    as_of: date
    dictionary_revision: str
    normalization_revision: str
