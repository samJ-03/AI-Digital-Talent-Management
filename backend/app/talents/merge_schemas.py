"""去重裁决白名单与共享响应；不承载部门考试答案或评分。"""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from app.core.types import PageQuery
from app.talents.schemas import Command


class DuplicateQuery(PageQuery):
    """稳定分页与裁决状态过滤。"""
    status: Literal['pending','same_person','different_person']|None=None


class ApplicationResolution(BaseModel):
    """同岗位所有有效次关系必须明确列出，不能跨岗位注入映射。"""
    model_config=ConfigDict(extra='forbid',strict=True)
    job_id: int=Field(gt=0)
    primary_application_id: int=Field(gt=0)
    secondary_application_ids: list[int]=Field(min_length=1,max_length=100)


class MergeDecision(Command):
    """客户端仅指定裁决，来源人才由服务端case推导。"""
    decision: Literal['same_person','different_person']
    target_candidate_id: int|None=Field(default=None,gt=0)
    application_resolutions: list[ApplicationResolution]=Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def decision_shape(self):
        """不同人裁决不得夹带合并目标或招聘关系映射。"""
        if self.decision=='same_person' and self.target_candidate_id is None:raise ValueError('Target required')
        if self.decision=='different_person' and (self.target_candidate_id is not None or self.application_resolutions):raise ValueError('Unexpected merge input')
        jobs=[r.job_id for r in self.application_resolutions]
        if len(set(jobs))!=len(jobs):raise ValueError('Duplicate job resolution')
        for r in self.application_resolutions:
            if len(set(r.secondary_application_ids))!=len(r.secondary_application_ids) or r.primary_application_id in r.secondary_application_ids or any(type(v) is not int or v<=0 for v in r.secondary_application_ids):raise ValueError('Invalid application IDs')
        return self


class DuplicateCaseView(BaseModel):
    """仅共享身份线索和裁决元数据，列表不展开任何岗位历史。"""
    id: str
    candidate_a_id: str
    candidate_b_id: str
    status: str
    evidence: list[dict]
    resolved_by: str|None
    version: int


class ApplicationMapping(BaseModel):
    """已授权的次关系到主关系映射；不移动考试归属。"""
    job_id: str
    application_id: str
    canonical_application_id: str


class MergeResult(BaseModel):
    """不同身份没有统一根，canonical_candidate_id为null。"""
    canonical_candidate_id: str|None
    application_mappings: list[ApplicationMapping]


@dataclass(frozen=True)
class MergePlan:
    """仅限同事务planner生成/应用的不可变身份及关系变更计划。"""
    case_id: int
    case_version: int
    canonical_root: int|None
    aliases: tuple[int,...]
    application_mappings: tuple[tuple[int,int,int],...]
    conflicts: tuple[dict,...]
