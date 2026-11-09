"""真实隔离MySQL与受控HTTP验证提取，不调用真实模型。"""
from copy import deepcopy
from sqlalchemy import select
import pytest
from tests.integration.test_model_gateway import gateway_case,ai,identity
from tests.unit.test_resume_extraction import facts
from app.ai_runtime.models import AiRun,PromptVersion,WorkflowConfig
from app.ai_runtime.generation_types import AiConfigSnapshot
from app.ingestion.document_types import ParsedDocument
from app.ingestion.extraction import ResumeExtractor
from app.ingestion.extraction_types import ResumeFacts
from app.core.errors import DomainError

@pytest.fixture
def extraction_case(gateway_case):
    gateway,request,reply,calls,runtime,_,_=gateway_case
    with runtime.uow_factory() as uow:
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='extract'))
        keys=['model_config_id','prompt_version_id','enabled','timeout_seconds','max_retries','config_revision']
        old={k:getattr(flow,k) for k in keys}
        prompt=uow.session.get(PromptVersion,request.prompt_version_id);prompt.task_type='extract';prompt.output_schema=ResumeFacts.model_json_schema()
        flow.model_config_id=request.model_config_id;flow.prompt_version_id=prompt.id;flow.enabled=True;flow.timeout_seconds=30;flow.max_retries=0;flow.config_revision+=1
        config=AiConfigSnapshot(request.model_config_id,prompt.id,30,0,flow.config_revision);uow.commit()
    reply.clear();reply.update(deepcopy(facts()))
    document=ParsedDocument.model_validate({'pages':[{'number':1,'paragraphs':[{'id':'pdf:p1:l1','text':'张三 Python 本科'}]}],'pagination':'physical','parser_revision':'synthetic-test'})
    yield ResumeExtractor(gateway,7),document,config,reply,runtime,calls
    with runtime.uow_factory() as uow:
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='extract'))
        for k,v in old.items(): setattr(flow,k,v)
        uow.commit()

def test_valid_extract_persists_with_unknown_email(extraction_case):
    extractor,document,config,_,runtime,calls=extraction_case
    output=extractor.extract(document,config)
    assert output.contacts.email is None and output.identity.name=='张三' and len(calls)==1
    with runtime.uow_factory() as uow:
        run=uow.session.get(AiRun,output.ai_run_id)
        assert run.state=='succeeded' and run.task_type=='extract'
        assert run.source_refs==[{'source_type':'stored_file','source_id':'7'}]
        assert run.validated_output['contacts']['email'] is None

@pytest.mark.parametrize('mutation',['invented_name','invented_source','invented_email'])
def test_bad_extract_never_persisted_as_success(extraction_case,mutation):
    extractor,document,config,reply,runtime,_=extraction_case
    if mutation=='invented_name': reply['identity']['name']='李四'
    if mutation=='invented_source': reply['citations'][0]['source_id']='99'
    if mutation=='invented_email': reply['contacts']['email']='fake@example.com';reply['field_sources']['contacts.email']=[deepcopy(reply['citations'][0])]
    with pytest.raises(DomainError) as error: extractor.extract(document,config)
    assert error.value.code=='MODEL_OUTPUT_INVALID'
    with runtime.uow_factory() as uow:
        run=uow.session.scalar(select(AiRun).where(AiRun.model_config_id==config.model_config_id))
        assert run.state=='invalid' and run.validated_output is None
