"""简历原文事实契约；共享资料不混入岗位评分或私有评价。"""
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.ai_runtime.generation_types import Evidence

class FactModel(BaseModel):
    """只接受白名单字段，原文未知字段保持null。"""
    model_config=ConfigDict(extra='forbid',strict=True)
class ResumeIdentity(FactModel):
    """身份原文，不推算年龄或敏感属性。"""
    name: str|None=Field(default=None,max_length=120)
    birth_date: str|None=Field(default=None,max_length=100)
class ResumeContacts(FactModel):
    """联系方式仅来自原文，邮箱格式校验不发网络请求。"""
    email: str|None=Field(default=None,max_length=254)
    phone: str|None=Field(default=None,max_length=64)
    @field_validator('email')
    @classmethod
    def valid_email(cls,value):
        """保留原始写法；不查询DNS、不推断缺失邮箱。"""
        if value is not None:
            from email_validator import validate_email
            validate_email(value,check_deliverability=False)
        return value
class EducationFact(FactModel):
    """学历经历原文，规范化和硬规则留后续服务。"""
    school: str|None=None
    degree: str|None=None
    major: str|None=None
    start_date: str|None=None
    end_date: str|None=None
class EmploymentFact(FactModel):
    """工作经历不据日期推算资历。"""
    company: str|None=None
    title: str|None=None
    start_date: str|None=None
    end_date: str|None=None
    responsibilities: str|None=None
class ProjectFact(FactModel):
    """项目事实不转化为能力结论。"""
    name: str|None=None
    role: str|None=None
    description: str|None=None
class ResumeFacts(FactModel):
    """模型输出固定结构；不接受模型自报运行ID。"""
    identity: ResumeIdentity
    contacts: ResumeContacts
    education: list[EducationFact]=Field(max_length=50)
    employment: list[EmploymentFact]=Field(max_length=100)
    projects: list[ProjectFact]=Field(max_length=100)
    skills: list[str]=Field(max_length=200)
    certificates: list[str]=Field(max_length=100)
    field_sources: dict[str,list[Evidence]]
    citations: list[Evidence]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def grounded_fields(self):
        """全部非空事实需精确覆盖来源；根引文由网关再验证真实输入。"""
        leaves={}
        def walk(value,path):
            if isinstance(value,dict):
                for key,item in value.items(): walk(item,path+'.'+key if path else key)
            elif isinstance(value,list):
                for index,item in enumerate(value): walk(item,path+'.'+str(index))
            elif value is not None:
                if not isinstance(value,str) or not value.strip(): raise ValueError('Empty or unsupported fact')
                leaves[path]=value
        data=self.model_dump(exclude={'citations','field_sources'})
        # ai_run_id belongs to the trusted wrapper, not model-authored facts.
        data.pop('ai_run_id',None)
        walk(data,'')
        if set(self.field_sources)!=set(leaves): raise ValueError('Field evidence must exactly cover known facts')
        for path,value in leaves.items():
            sources=self.field_sources[path]
            if not sources or len(sources)>100: raise ValueError('Missing or excessive field evidence')
            if any(source not in self.citations for source in sources): raise ValueError('Field evidence is not cited')
            if not any(value in source.quote for source in sources): raise ValueError('Fact is absent from original quote')
        for group in (self.education,self.employment,self.projects):
            if any(not any(v is not None for v in entry.model_dump().values()) for entry in group):
                raise ValueError('Empty fact record')
        return self

class ExtractedResume(ResumeFacts):
    """校验后的提取产物；ai_run_id只由可信网关注入。"""
    ai_run_id: int=Field(gt=0,strict=True)
