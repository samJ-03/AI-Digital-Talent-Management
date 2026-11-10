"""评估HTTP契约：客户端只能选择当前简历并提供人工理由。"""
from typing import Literal,Any
from pydantic import BaseModel,ConfigDict,Field
from app.core.types import TaskAccepted

class EvaluationRequest(BaseModel):
    """显式重评始终使用人工邀请模式。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    resume_version_id: int|None=Field(default=None,gt=0)
    reason: str=Field(min_length=1,max_length=500)

class OverrideRequest(BaseModel):
    """不允许改写原始结果或客户端注入状态。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason: str=Field(min_length=1,max_length=500)
    decision: Literal['continue']

class EvaluationAccepted(TaskAccepted):
    """异步受理结果同时提供冻结评估ID。"""
    evaluation_id: str

class EvaluationView(BaseModel):
    """当前性独立于历史结果，旧运行仍可读取。"""
    id: str
    application_id: str
    resume_version_id: str
    profile_id: str
    job_version_id: str
    state: str
    screening_result: str|None
    invitation_mode: str
    is_current: bool
    error_code: str|None

class EvaluationDetail(EvaluationView):
    """白名单投影不包含部门面试、考试答卷或供应商原始响应。"""
    screening_context: dict[str,Any]
    conditions: list[dict[str,Any]]
    match: dict[str,Any]|None
    override_events: list[dict[str,Any]]
