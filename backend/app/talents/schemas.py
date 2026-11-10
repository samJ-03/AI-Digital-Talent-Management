"""人才写入契约：禁止额外字段，保留未知值并要求人工修改理由。"""
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Command(BaseModel):
    """所有人才命令禁止客户端注入状态和版本指针。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason: str=Field(min_length=1,max_length=500)


class ContactsPatch(Command):
    """省略联系方式表示保持原值，显式null表示清空。"""
    email: str|None=Field(default=None,max_length=254)
    phone: str|None=Field(default=None,max_length=64)

    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        """只做格式验证，不查询DNS或验证邮箱控制权。"""
        if value is not None:
            from email_validator import validate_email
            validate_email(value,check_deliverability=False)
        return value

    @model_validator(mode='after')
    def nonempty_patch(self):
        """拒绝没有任何联系方式的空修改。"""
        if not self.model_fields_set & {'email','phone'}: raise ValueError('Contacts patch is empty')
        return self


class ResumeCorrection(Command):
    """changes为白名单事实的点分路径映射，例如identity.name。"""
    base_resume_version_id: int=Field(gt=0)
    changes: dict[str,Any]=Field(min_length=1,max_length=50)


class TalentView(BaseModel):
    """共享人才摘要，不包含部门私有评价，联系信息默认遮罩。"""
    id: str
    canonical_candidate_id: str
    name: str
    email_masked: str|None
    education: list[dict]
    major: list[str]
    years_experience: float|None=None
    skills: list[str]
    status: str
    current_profile_id: str|None
    version: int


class ResumeVersionView(BaseModel):
    """仅HR授权后返回的简历快照；人工来源与原文来源分开保存。"""
    id: str
    candidate_id: str
    file_id: str
    version_no: int
    parent_version_id: str|None
    raw_text: str|None
    structured_data: dict
    field_sources: dict
    parser_revision: str
    state: str
    change_reason: str|None
    version: int


@dataclass(frozen=True)
class MaterializationResult:
    """内部建档结果；任务ID只引用持久化任务，不代表已生成画像。"""
    candidate_id: int
    resume_version_id: int
    application_id: int|None
    state: str
    next_task: int|None
