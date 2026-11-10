"""共享画像类型：事实引用与部门动态视图在类型层面分离。"""
from typing import Any
from pydantic import BaseModel,ConfigDict,Field,model_validator
from app.ai_runtime.generation_types import Evidence
from app.talents.schemas import Command

MAX_SUMMARY_BYTES=65535  # Existing MySQL TEXT capacity; count bytes, not characters.


class GroundedClaim(BaseModel):
    """一个完整事实及其简历字段来源，不接受模型自报能力分。"""
    model_config=ConfigDict(extra='forbid',strict=True)
    text: str=Field(min_length=1,max_length=20000)
    source: Evidence


class ProfileOutput(BaseModel):
    """发布给profile工作流的固定schema，只允许摘录事实。"""
    model_config=ConfigDict(extra='forbid',strict=True,title='ProfileOutput')
    summary_claims: list[GroundedClaim]=Field(max_length=30)
    skills: list[GroundedClaim]=Field(max_length=100)
    experiences: list[GroundedClaim]=Field(max_length=100)
    citations: list[Evidence]=Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def cited_claims(self):
        """全部内容必须有根引文；完整事实匹配由绑定本简历的验证器校验。"""
        if len('\n'.join(c.text for c in self.summary_claims).encode('utf8'))>MAX_SUMMARY_BYTES:raise ValueError('Profile summary exceeds storage budget')
        if not self.summary_claims and not self.skills and not self.experiences:raise ValueError('No profile facts')
        for claim in [*self.summary_claims,*self.skills,*self.experiences]:
            if claim.source not in self.citations or claim.text!=claim.source.quote:raise ValueError('Uncited claim')
        return self


class ProfileDraft(BaseModel):
    """可信构建产物；运行ID和原始校验输出由网关注入，不是模型字段。"""
    model_config=ConfigDict(extra='forbid')
    summary: str
    skills: list[str]
    experiences: list[str]
    evidence: list[dict]
    ai_run_id: int|None=None
    validated_output: dict|None=None


class ProfileRevision(Command):
    """人工重选/编排现有简历事实，新事实须先走简历修订。"""
    base_profile_id: int=Field(gt=0)
    changes: dict[str,list[str]]=Field(min_length=1,max_length=3)


class AuthorizedApplicationView(BaseModel):
    """按当前岗位权限动态返回，永不写入共享画像或向量。"""
    application_id: str
    job_id: str
    department_id: int
    stage: str
    relationship_state: str
    canonical_application_id: str|None
    exam_results: list[dict]
    interview_events: list[dict]
    radar: dict|None=None


class ProfileView(BaseModel):
    """共享事实与授权附加视图分开，历史版本保持其原始归属。"""
    id: str
    candidate_id: str
    resume_version_id: str
    version_no: int
    summary: str
    skills: list[str]
    experiences: list[str]
    evidence: list[dict]
    source_record_refs: list[dict]
    ai_run_id: str|None
    confirmed_by: str|None
    version: int
    authorized_application_views: list[AuthorizedApplicationView]
