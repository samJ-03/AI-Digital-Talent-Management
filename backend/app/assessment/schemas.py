"""题库、试卷与考试：定义输入输出类型、字段约束及序列化边界。"""
from datetime import datetime
from decimal import Decimal
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator,field_serializer

QuestionType=Literal['single_choice','multiple_choice','short_answer']

class InputModel(BaseModel):
    """InputModel：题库、试卷与考试中的输入输出数据契约。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class Option(InputModel):
    """Option：题库、试卷与考试中的输入输出数据契约。"""
    key: str=Field(min_length=1,max_length=20,pattern=r'^[A-Za-z0-9_-]+$')
    text: str=Field(min_length=1,max_length=2000)

class Criterion(InputModel):
    """Criterion：题库、试卷与考试中的输入输出数据契约。"""
    key: str=Field(min_length=1,max_length=50,pattern=r'^[A-Za-z0-9_-]+$')
    description: str=Field(min_length=1,max_length=2000)
    weight: float=Field(gt=0,le=100,allow_inf_nan=False)

class ShortRubric(InputModel):
    """ShortRubric：题库、试卷与考试中的输入输出数据契约。"""
    reference_answer: str=Field(min_length=1,max_length=8000)
    criteria: list[Criterion]=Field(min_length=1,max_length=20)
    policy: Literal['weighted_rubric']='weighted_rubric'
    policy_version: Literal[1]=1
    @model_validator(mode='after')
    def unique_criteria(self):
        """校验评分维度键唯一，防止重复计分。"""
        if len({c.key for c in self.criteria})!=len(self.criteria): raise ValueError('Duplicate criterion keys')
        return self

class ReferenceSource(InputModel):
    """ReferenceSource：题库、试卷与考试中的输入输出数据契约。"""
    source_type: Literal['knowledge_document','knowledge_chunk']
    source_id: int=Field(gt=0)
    locator: dict[str,Any]=Field(default_factory=dict)
    quote: str=Field(default='',max_length=1000)

class QuestionDraft(InputModel):
    """QuestionDraft：题库、试卷与考试中的输入输出数据契约。"""
    bank_id: int=Field(gt=0)
    type: QuestionType
    stem: str=Field(min_length=1,max_length=16000)
    options: list[Option]|None=Field(default=None,max_length=20)
    answer_key: dict[str,list[str]]|None=None
    rubric: dict[str,Any]=Field(default_factory=dict)
    reference_sources: list[ReferenceSource]=Field(default_factory=list,max_length=30)
    @model_validator(mode='after')
    def complete_standard(self):
        """校验客观题或量表标准是否足以发布。"""
        if self.type=='short_answer':
            if self.options or self.answer_key not in (None,{}): raise ValueError('Short answer cannot have choice options/keys')
            self.options=None;self.answer_key=None
            self.rubric=ShortRubric.model_validate(self.rubric).model_dump(mode='json')
        else:
            if not self.options or len(self.options)<2: raise ValueError('At least two options required')
            keys={o.key for o in self.options}
            if len(keys)!=len(self.options): raise ValueError('Option keys must be unique')
            if not self.answer_key or set(self.answer_key)!={'selected_keys'}: raise ValueError('Answer key required')
            selected=self.answer_key['selected_keys']
            if not selected or len(selected)!=len(set(selected)) or not set(selected)<=keys: raise ValueError('Invalid answer choices')
            if self.type=='single_choice' and len(selected)!=1: raise ValueError('Single choice needs one answer')
            if self.rubric and (set(self.rubric)-{'policy','policy_version'} or self.rubric.get('policy')!='exact_set_all_or_nothing' or self.rubric.get('policy_version',1)!=1):
                raise ValueError('Unsupported choice grading policy')
            self.answer_key={'selected_keys':sorted(selected)}
            self.rubric={'policy':'exact_set_all_or_nothing','policy_version':1}
        return self

class ReviseQuestion(QuestionDraft):
    """ReviseQuestion：题库、试卷与考试中的协作类型。"""
    reason: str=Field(min_length=1,max_length=500)

class ReasonCommand(InputModel):
    """ReasonCommand：题库、试卷与考试中的输入输出数据契约。"""
    reason: str=Field(min_length=1,max_length=500)

class QuestionBankCreate(InputModel):
    """QuestionBankCreate：题库、试卷与考试中的输入输出数据契约。"""
    name: str=Field(min_length=1,max_length=200)
    department_id: int=Field(gt=0)

class PaperCreate(QuestionBankCreate):
    """PaperCreate：题库、试卷与考试中的协作类型。"""
    pass

class PaperItemDraft(InputModel):
    """PaperItemDraft：题库、试卷与考试中的输入输出数据契约。"""
    source_question_id: int=Field(gt=0)
    max_score: Decimal=Field(gt=0,le=Decimal('9999.99'),max_digits=6,decimal_places=2)
    position_no: int=Field(ge=1,le=200)

class PaperVersionDraft(InputModel):
    """PaperVersionDraft：题库、试卷与考试中的输入输出数据契约。"""
    duration_minutes: int=Field(ge=1,le=1440)
    reference_pass_score: Decimal|None=Field(default=None,ge=0,max_digits=6,decimal_places=2)
    items: list[PaperItemDraft]=Field(min_length=1,max_length=200)
    @model_validator(mode='after')
    def valid_items(self):
        """校验试卷条目、题型、分值与引用。"""
        if sorted(i.position_no for i in self.items)!=list(range(1,len(self.items)+1)) or len({i.source_question_id for i in self.items})!=len(self.items):
            raise ValueError('Unique questions and continuous positions required')
        total=sum((i.max_score for i in self.items),Decimal('0'))
        if total>Decimal('9999.99') or self.reference_pass_score is not None and self.reference_pass_score>total:
            raise ValueError('Invalid total or reference score')
        return self

class QuestionBankView(BaseModel):
    """QuestionBankView：题库、试卷与考试中的输入输出数据契约。"""
    id: str
    name: str
    department_id: str
    status: str
    version: int

class PaperView(QuestionBankView):
    """PaperView：题库、试卷与考试中的协作类型。"""
    pass

class QuestionView(BaseModel):
    """QuestionView：题库、试卷与考试中的输入输出数据契约。"""
    id: str
    bank_id: str
    logical_key: str
    revision_no: int
    type: QuestionType
    stem: str
    options: list[Option]|None
    answer_key: dict[str,list[str]]|None
    rubric: dict[str,Any]
    reference_sources: list[dict[str,Any]]
    state: str
    version: int

class PaperItemView(BaseModel):
    """PaperItemView：题库、试卷与考试中的输入输出数据契约。"""
    id: str
    source_question_id: str|None
    position_no: int
    type: QuestionType
    stem: str
    options: list[Option]|None
    max_score: Decimal
    answer_key: dict[str,list[str]]|None
    rubric: dict[str,Any]
    reference_sources: list[dict[str,Any]]
    @field_serializer('max_score')
    def score(self,value):
        """按冻结标准计算客观题或评分量表结果。"""
        return format(value,'.2f')

class PaperVersionView(BaseModel):
    """PaperVersionView：题库、试卷与考试中的输入输出数据契约。"""
    id: str
    paper_id: str
    version_no: int
    duration_minutes: int
    total_score: Decimal
    reference_pass_score: Decimal|None
    status: str
    published_at: datetime|None
    items: list[PaperItemView]
    version: int
    @field_serializer('total_score','reference_pass_score')
    def score(self,value):
        """按冻结标准计算客观题或评分量表结果。"""
        return format(value,'.2f') if value is not None else None

class CandidatePaperItem(BaseModel):
    """CandidatePaperItem：题库、试卷与考试中的输入输出数据契约。"""
    id: str
    type: QuestionType
    stem: str
    options: list[Option]|None
    max_score: Decimal
    @field_serializer('max_score')
    def score(self,value):
        """按冻结标准计算客观题或评分量表结果。"""
        return format(value,'.2f')
