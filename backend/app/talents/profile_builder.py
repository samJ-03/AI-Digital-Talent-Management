"""画像构建只读取简历事实，不接收岗位、考试、面试或联系人数据。"""
import json
from pydantic import model_validator,ValidationError
from app.ai_runtime.generation_types import Evidence
from app.ai_runtime.graphs import FixedGraphRunner
from app.core.errors import DomainError
from app.ingestion.extraction_types import ResumeFacts
from app.talents.profile_schemas import ProfileOutput,ProfileDraft,GroundedClaim


def fact_catalog(resume):
    """将已校验结构化事实转为完整叶子引文，排除邮箱/电话/出生日期。"""
    try:facts=ResumeFacts.model_validate(resume.structured_data).model_dump(mode='json')
    except (ValueError,TypeError):raise DomainError('PROFILE_SOURCE_INVALID',409,'简历事实未通过校验') from None
    catalog={}
    def walk(value,path):
        if isinstance(value,dict):
            for key,item in value.items():walk(item,path+'.'+key if path else key)
        elif isinstance(value,list):
            for index,item in enumerate(value):walk(item,path+'.'+str(index))
        elif value is not None:
            catalog[path]=Evidence(source_type='resume_version',source_id=resume.id,locator=path,quote=value)
    for key in ['education','employment','projects','skills','certificates']:walk(facts[key],key)
    if facts['identity']['name']:walk(facts['identity']['name'],'identity.name')
    if not catalog or len(catalog)>100:raise DomainError('PROFILE_SOURCE_BUDGET',422,'简历事实为空或超出当前画像预算')
    return catalog


def bound_output(catalog):
    """来源约束在网关校验阶段执行，错误输出不会被记为成功AiRun。"""
    class BoundProfileOutput(ProfileOutput):
        @model_validator(mode='after')
        def exact_facts(self):
            for source in self.citations:
                if catalog.get(source.locator)!=source:raise ValueError('Citation is not a full authorized fact')
            for group in ['summary_claims','skills','experiences']:
                for claim in getattr(self,group):
                    if catalog.get(claim.source.locator)!=claim.source:raise ValueError('Foreign fact')
                    if group=='skills' and not claim.source.locator.startswith('skills.'):raise ValueError('Not a skill fact')
                    if group=='experiences' and not claim.source.locator.startswith(('education.','employment.','projects.')):raise ValueError('Not an experience fact')
            return self
    return BoundProfileOutput


def draft_from_output(output,ai_run_id=None):
    """确定性拼接摘要并记录每个显示字段的来源，禁止二次自由改写。"""
    evidence=[]
    for group in ['summary_claims','skills','experiences']:
        for index,claim in enumerate(getattr(output,group)):
            evidence.append({'field':f'{group}.{index}','text':claim.text,'source':claim.source.model_dump(mode='json')})
    return ProfileDraft(summary='\n'.join(c.text for c in output.summary_claims),skills=[c.text for c in output.skills],experiences=[c.text for c in output.experiences],evidence=evidence,ai_run_id=ai_run_id,validated_output=output.model_dump(mode='json') if ai_run_id else None)


def output_from_evidence(evidence,catalog):
    """读取持久化画像时再次验证字段顺序、来源和完整事实。"""
    groups={k:{} for k in ['summary_claims','skills','experiences']};citations=[]
    try:
        for entry in evidence:
            if set(entry)!={'field','text','source'}:raise ValueError()
            group,index=entry['field'].split('.')
            if group not in groups or not index.isascii() or not index.isdigit() or int(index) in groups[group]:raise ValueError()
            claim=GroundedClaim.model_validate({'text':entry['text'],'source':entry['source']})
            groups[group][int(index)]=claim
            if claim.source not in citations:citations.append(claim.source)
        for values in groups.values():
            if set(values)!=set(range(len(values))):raise ValueError()
        return bound_output(catalog).model_validate({**{k:[c.model_dump(mode='json') for _,c in sorted(v.items())] for k,v in groups.items()},'citations':[c.model_dump(mode='json') for c in citations]})
    except (ValueError,TypeError,KeyError,AttributeError):raise DomainError('PROFILE_SOURCE_INVALID',409,'画像事实来源未通过校验') from None


class ProfileBuilder:
    """只依赖受控网关；配置快照沿用T09，不另选模型或读取凭据。"""
    def __init__(self,gateway):self.gateway=gateway

    def build(self,resume,config) -> ProfileDraft:
        """所有事实完整传入，超预算拒绝而不静默截断。"""
        catalog=fact_catalog(resume)
        payload={'input_refs':[{'source_type':'resume_version','source_id':resume.id}],'evidence':[e.model_dump(mode='json') for e in catalog.values()],'output_schema':ProfileOutput.model_json_schema()}
        if len(json.dumps(payload,ensure_ascii=False).encode())>250*1024:raise DomainError('PROFILE_SOURCE_BUDGET',422,'简历事实超过画像输入预算')
        result=FixedGraphRunner(self.gateway,{'profile':bound_output(catalog)}).run('profile',payload,config)
        output=bound_output(catalog).model_validate(result.output)
        return draft_from_output(output,result.ai_run_id)
