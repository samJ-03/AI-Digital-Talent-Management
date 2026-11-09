"""简历事实/字段证据校验；只使用合成文本。"""
import json
from copy import deepcopy
import pytest
from app.ai_runtime.validation import validate_output,OutputInvalid
from app.ingestion.extraction_types import ResumeFacts

def citation():
    return {'source_type':'stored_file','source_id':'7','locator':'pdf:p1:l1','quote':'张三 Python 本科'}
def facts():
    c=citation()
    return {'identity':{'name':'张三','birth_date':None},'contacts':{'email':None,'phone':None},'education':[{'school':None,'degree':'本科','major':None,'start_date':None,'end_date':None}],
        'employment':[],'projects':[],'skills':['Python'],'certificates':[],
        'field_sources':{'identity.name':[c],'education.0.degree':[c],'skills.0':[c]},'citations':[c]}
def validate(value):
    return validate_output(json.dumps(value,ensure_ascii=False),ResumeFacts,ResumeFacts.model_json_schema(),[citation()])
def test_missing_email_remains_unknown():
    assert validate(facts()).contacts.email is None
@pytest.mark.parametrize('mutation',['invented_email','invented_name','missing_source','extra_source','wrong_source','wrong_quote','private_score','empty_fact'])
def test_unsupported_fact_is_not_validated(mutation):
    value=deepcopy(facts())
    if mutation=='invented_email': value['contacts']['email']='madeup@example.com';value['field_sources']['contacts.email']=[citation()]
    if mutation=='invented_name': value['identity']['name']='李四'
    if mutation=='missing_source': del value['field_sources']['skills.0']
    if mutation=='extra_source': value['field_sources']['contacts.email']=[citation()]
    if mutation=='wrong_source': value['field_sources']['identity.name'][0]['source_id']='999'
    if mutation=='wrong_quote': value['field_sources']['identity.name'][0]['quote']='李四'
    if mutation=='private_score': value['exam_score']=99
    if mutation=='empty_fact': value['skills']=['']
    with pytest.raises(OutputInvalid): validate(value)

def test_too_many_paragraphs_block_before_gateway():
    from app.ingestion.extraction import ResumeExtractor
    from app.ingestion.document_types import ParsedDocument
    from app.ai_runtime.generation_types import AiConfigSnapshot
    from app.core.errors import DomainError
    class NeverCalled:
        def generate(self,*args,**kwargs): raise AssertionError('No model call allowed')
    document=ParsedDocument.model_validate({'pages':[{'number':1,'paragraphs':[{'id':str(i),'text':'Python'} for i in range(101)]}],'pagination':'logical','parser_revision':'synthetic'})
    with pytest.raises(DomainError) as error: ResumeExtractor(NeverCalled(),7).extract(document,AiConfigSnapshot(1,1,30,0,1))
    assert error.value.code=='AI_INPUT_TOO_LARGE'

@pytest.mark.parametrize('source',[True,0,-1,'7'])
def test_source_id_must_be_trusted_persisted_identifier(source):
    from app.ingestion.extraction import ResumeExtractor
    with pytest.raises(ValueError): ResumeExtractor(None,source)
