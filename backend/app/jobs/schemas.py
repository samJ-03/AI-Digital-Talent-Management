"""岗位输入输出契约：规则类型、权重、模板及CAS字段的边界校验。"""
import math
from datetime import datetime
from decimal import Decimal
from string import Formatter
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,StrictBool,AliasChoices,JsonValue,field_validator,model_validator,field_serializer

class InputModel(BaseModel):
    """拒绝未知字段，防止客户端修改当前版本指针或领域状态。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class JobCreate(InputModel):
    """创建岗位元数据；状态和自动邀请开关由服务端初始化。"""
    title: str=Field(min_length=1,max_length=200)
    department_id: int=Field(gt=0)
    headcount: int=Field(gt=0,le=100000,strict=True)

class JobPatch(InputModel):
    """仅允许修改非版本化元数据；显式NULL不覆盖非空字段。"""
    title: str|None=Field(default=None,min_length=1,max_length=200)
    headcount: int|None=Field(default=None,gt=0,le=100000,strict=True)
    owner_hr_id: int|None=Field(default=None,gt=0)
    @model_validator(mode='after')
    def nonempty(self):
        """拒绝空更新和显式NULL，保留缺省字段的原值。"""
        if not self.model_fields_set or any(getattr(self,k) is None for k in self.model_fields_set):
            raise ValueError('At least one non-null metadata field is required')
        return self

class Condition(InputModel):
    """确定性筛选条件，仅表达白名单规则，不执行正则或脚本。"""
    key: str=Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    field: Literal['education','major','relevant_years','skill','certificate']
    operator: Literal['eq','in','gte','lte','between','contains_any','contains_all']
    expected: JsonValue
    required: StrictBool
    @model_validator(mode='after')
    def compatible_value(self):
        """按字段和操作符校验期望值，未知信息留给后续三态引擎。"""
        value=self.expected
        def strings(v):
            return isinstance(v,list) and 1<=len(v)<=30 and all(isinstance(s,str) and 0<len(s.strip())<=200 for s in v) and len({s.strip().casefold() for s in v})==len(v)
        levels={'high_school','secondary','associate','bachelor','master','doctor'}
        valid=False
        if self.field=='education':
            valid=self.operator in {'eq','gte'} and isinstance(value,str) and value in levels
            valid=valid or self.operator=='in' and strings(value) and set(value)<=levels
        elif self.field=='major':
            valid=self.operator=='eq' and isinstance(value,str) and 0<len(value.strip())<=200 or self.operator=='in' and strings(value)
        elif self.field in {'skill','certificate'}:
            valid=self.operator in {'contains_any','contains_all'} and strings(value)
        else:
            def numeric(v): return type(v) in (int,float) and 0<=v<=100 and math.isfinite(v)
            valid=self.operator in {'gte','lte'} and numeric(value)
            valid=valid or self.operator=='between' and isinstance(value,list) and len(value)==2 and all(numeric(v) for v in value) and value[0]<=value[1]
        if not valid: raise ValueError('Condition field/operator/value are incompatible')
        if isinstance(value,list) and all(isinstance(v,str) for v in value): self.expected=[v.strip() for v in value]
        return self

class MatchWeights(InputModel):
    """三维权重精确合计100；计算用Decimal，JSON保持数值。"""
    skills: Decimal=Field(ge=0,le=100,max_digits=5,decimal_places=2)
    experience: Decimal=Field(ge=0,le=100,max_digits=5,decimal_places=2)
    responsibilities: Decimal=Field(ge=0,le=100,max_digits=5,decimal_places=2)
    @model_validator(mode='after')
    def total_100(self):
        """拒绝非100总和，不自动归一化HR输入的业务权重。"""
        if self.skills+self.experience+self.responsibilities!=Decimal(100): raise ValueError('Match weights must total 100')
        return self
    @field_serializer('skills','experience','responsibilities')
    def numeric(self,value):
        """将已校验权重输出为JSON数值。"""
        return float(value)

class MailTemplate(InputModel):
    """纯文本邮件模板；占位符只允许直接字段名。"""
    subject: str=Field(min_length=1,max_length=200)
    body: str=Field(min_length=1,max_length=16000)
    @model_validator(mode='after')
    def safe_fields(self):
        """拒绝邮件头换行及对象属性、索引和任意格式执行。"""
        if '\n' in self.subject or '\r' in self.subject: raise ValueError('Subject must be a single line')
        for value in (self.subject,self.body):
            try:
                for _,name,spec,conversion in Formatter().parse(value):
                    if name is not None and (name not in {'candidate_name','job_title','exam_url','valid_until'} or spec or conversion):
                        raise ValueError('Unsupported template placeholder')
            except ValueError: raise ValueError('Invalid plain-text template placeholder') from None
        return self

class JobVersionDraft(InputModel):
    """岗位发布标准的完整草稿，修改须生成或编辑draft版本。"""
    description: str=Field(min_length=1,max_length=30000)
    conditions: list[Condition]=Field(default_factory=list,max_length=50)
    match_weights: MatchWeights
    invite_threshold: Decimal=Field(ge=0,le=100,max_digits=5,decimal_places=2)
    paper_version_id: int|None=Field(default=None,gt=0)
    invite_valid_hours: int=Field(gt=0,le=8760,strict=True)
    mail_template: MailTemplate
    @model_validator(mode='after')
    def unique_conditions(self):
        """条件键是证据结果的稳定标识，不允许重复。"""
        if len({c.key for c in self.conditions})!=len(self.conditions): raise ValueError('Duplicate condition keys')
        return self

class ReasonCommand(InputModel):
    """发布及状态变化必须留人工理由。"""
    reason: str=Field(min_length=1,max_length=500)

class StateCommand(InputModel):
    """支持契约reopen_reason并兼容统一reason；内部归一化。"""
    action: Literal['open','pause','close']
    reason: str=Field(min_length=1,max_length=500,validation_alias=AliasChoices('reopen_reason','reason'))

class AutomationCommand(InputModel):
    """显式布尔开关；不接受字符串或数字冒充布尔。"""
    enabled: StrictBool

class JobView(BaseModel):
    """岗位安全元数据视图；ID以字符串传给JavaScript。"""
    id: str
    title: str
    department_id: str
    owner_hr_id: str
    headcount: int
    status: str
    current_version_id: str|None
    auto_invite_enabled: bool
    version: int

class JobVersionView(BaseModel):
    """岗位标准快照，不包含模型/SMTP连接秘密。"""
    id: str
    job_id: str
    version_no: int
    description: str
    conditions: list[Condition]
    match_weights: MatchWeights
    invite_threshold: Decimal
    paper_version_id: str|None
    invite_valid_hours: int
    mail_template: MailTemplate
    status: str
    published_by: str|None
    published_at: datetime|None
    version: int
    @field_serializer('invite_threshold')
    def score(self,value):
        """阈值以两位小数字符串序列化，避免展示精度丢失。"""
        return format(value,'.2f')

class Readiness(BaseModel):
    """仅向HR提供安全原因代码，不返回内部连接信息。"""
    ready: bool
    blocking_reasons: list[str]

class AutomationView(BaseModel):
    """开关结果以及当前时刻的就绪预览。"""
    job: JobView
    readiness: Readiness
