"""T15使用隔离MySQL、私有MinIO与合成资料，不调用外部模型。"""
from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import select, delete, update, func
from tests.integration.test_import_batches import imports, identity, post, actor_and_service
from tests.integration.test_identity import login
from app.identity.models import Role
from app.talents.models import Candidate, ResumeVersion, DuplicateCase
from app.ingestion.models import ImportItem
from app.runtime.models import BackgroundJob, OutboxEvent
from app.ai_runtime.models import ModelConfig, PromptVersion, AiRun
from app.recruitment.models import Application
from app.ingestion.extraction_types import ExtractedResume


@pytest.fixture
def candidates(imports):
    """追踪本夹具创建的数据，按外键顺序回收；不触碰开发库。"""
    client=imports[0][0]; factory=client.app.state.identity.uow_factory
    owned=[]; runs=[]
    with factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role'])
        role.permission_codes=sorted(set(role.permission_codes)|{'talent.write'})
        model=ModelConfig(logical_key=uuid4().hex,revision_no=1,provider_type='compatible_http',base_url='https://api.deepseek.com/v1',model_name='deepseek-flash',enabled=False)
        prompt=PromptVersion(task_type='extract',revision_no=(uow.session.scalar(select(func.max(PromptVersion.revision_no)).where(PromptVersion.task_type=='extract')) or 0)+1,content='synthetic fixture',output_schema={},status='published')
        uow.session.add_all([model,prompt]);uow.session.flush();mid=model.id;pid=prompt.id;uow.commit()
    def seed(email=None,name='张三',files=None):
        response=post(imports,files=files);assert response.status_code==202,response.text
        detail=client.get('/api/v1/imports/'+response.json()['data']['id']).json()['data'];item=detail['items'][0]
        quote=name+' Python'+(' '+email if email else '')
        evidence={'source_type':'stored_file','source_id':item['file_id'],'locator':'p1','quote':quote}
        data={'identity':{'name':name,'birth_date':None},'contacts':{'email':email,'phone':None},'education':[],'employment':[],'projects':[],'skills':['Python'],'certificates':[],
              'field_sources':{'identity.name':[evidence],'skills.0':[evidence]},'citations':[evidence]}
        if email:data['field_sources']['contacts.email']=[evidence]
        with factory() as uow:
            run=AiRun(task_type='extract',model_config_id=mid,prompt_version_id=pid,input_hash='a'*64,source_refs=[{'source_type':'stored_file','source_id':item['file_id']}],validated_output=data,state='succeeded')
            uow.session.add(run);uow.session.flush();rid=run.id;runs.append(rid);uow.commit()
        return int(item['id']),ExtractedResume.model_validate({**data,'ai_run_id':rid})
    yield imports,factory,seed,owned
    with factory() as uow:
        file_ids=list(uow.session.scalars(select(__import__('app.files.models',fromlist=['StoredFile']).StoredFile.id).where(__import__('app.files.models',fromlist=['StoredFile']).StoredFile.bucket==imports[1].bucket)))
        resume_ids=list(uow.session.scalars(select(ResumeVersion.id).where(ResumeVersion.file_id.in_(file_ids))))
        cids=set(owned)|set(uow.session.scalars(select(ResumeVersion.candidate_id).where(ResumeVersion.id.in_(resume_ids))))
        tasks=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id.in_(cids))))
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_id.in_(tasks),OutboxEvent.aggregate_type=='background_job'))
        uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(tasks)))
        uow.session.execute(delete(Application).where(Application.candidate_id.in_(cids)))
        uow.session.execute(delete(DuplicateCase).where((DuplicateCase.candidate_a_id.in_(cids))|(DuplicateCase.candidate_b_id.in_(cids))))
        uow.session.execute(update(ImportItem).where(ImportItem.resume_version_id.in_(resume_ids)).values(resume_version_id=None))
        uow.session.execute(update(Candidate).where(Candidate.id.in_(cids)).values(current_resume_version_id=None,merged_into_id=None))
        uow.session.execute(update(ResumeVersion).where(ResumeVersion.id.in_(resume_ids)).values(parent_version_id=None))
        uow.session.execute(delete(ResumeVersion).where(ResumeVersion.id.in_(resume_ids)))
        uow.session.execute(delete(Candidate).where(Candidate.id.in_(cids)))
        uow.session.execute(delete(AiRun).where(AiRun.id.in_(runs)))
        uow.session.execute(delete(PromptVersion).where(PromptVersion.id==pid));uow.session.execute(delete(ModelConfig).where(ModelConfig.id==mid));uow.commit()


def test_email_completion_resumes_pipeline(candidates):
    imports,factory,_,owned=candidates;client=imports[0][0]
    with factory() as uow:
        row=Candidate(display_name='合成人才',status='pending_email');uow.session.add(row);uow.session.flush();cid=row.id;owned.append(cid);uow.commit()
    headers=login(imports[0],'hr')
    response=client.patch(f'/api/v1/talents/{cid}/contacts',json={'email':'person@example.com','reason':'补充联系方式'},headers={**headers,'If-Match':'1'})
    assert response.status_code==200,response.text
    assert response.json()['data']['status']=='ready'


def test_parsed_without_email_stays_pending(candidates):
    from app.talents.candidate_service import CandidateService
    _,factory,seed,_=candidates;item,extracted=seed()
    service=CandidateService(factory);result=service.materialize(item,extracted)
    assert result.state=='pending_email' and result.next_task is None
    assert service.materialize(item,extracted).candidate_id==result.candidate_id
    with factory() as uow:
        assert uow.session.get(ImportItem,item).status=='parsed'
        assert uow.session.get(ResumeVersion,result.resume_version_id).structured_data['contacts']['email'] is None


def test_same_name_not_merge(candidates):
    from app.talents.candidate_service import CandidateService
    _,factory,seed,_=candidates;service=CandidateService(factory)
    a=service.materialize(*seed());b=service.materialize(*seed())
    assert a.candidate_id!=b.candidate_id
    # Identical imported bytes are only a duplicate clue, never identity proof.
    with factory() as uow: assert uow.session.get(Candidate,b.candidate_id).merged_into_id is None


def test_correction_new_version(candidates):
    from app.talents.candidate_service import CandidateService
    imports,factory,seed,_=candidates;result=CandidateService(factory).materialize(*seed())
    headers={**login(imports[0],'hr'),'Idempotency-Key':uuid4().hex}
    payload={'base_resume_version_id':result.resume_version_id,'changes':{'identity.name':'李四'},'reason':'HR核实姓名'}
    url=f'/api/v1/talents/{result.candidate_id}/resume-corrections'
    response=imports[0][0].post(url,json=payload,headers=headers)
    assert response.status_code==202,response.text
    assert imports[0][0].post(url,json=payload,headers=headers).json()['data']['id']==response.json()['data']['id']
    with factory() as uow:
        old=uow.session.get(ResumeVersion,result.resume_version_id);new=uow.session.get(ResumeVersion,int(response.json()['data']['id']))
        assert old.structured_data['identity']['name']=='张三' and new.structured_data['identity']['name']=='李四'
        assert new.parent_version_id==old.id and new.version_no==old.version_no+1


def test_canonical_cycle_rejected(candidates):
    from app.talents.identity_resolver import CanonicalResolver
    from app.core.errors import DomainError
    _,factory,_,owned=candidates
    with factory() as uow:
        a=Candidate(display_name='a');b=Candidate(display_name='b');uow.session.add_all([a,b]);uow.session.flush();owned.extend([a.id,b.id]);a.merged_into_id=b.id;b.merged_into_id=a.id;uow.commit()
    with factory() as uow,pytest.raises(DomainError,match='IDENTITY_CYCLE'):
        CanonicalResolver().resolve(uow,a.id)


def test_worker_unsupported_format_finishes_without_candidate(candidates):
    from app.ingestion.worker import ResumeParseHandler
    from app.runtime.job_service import JobRunner, BackgroundJobService
    imports,factory,seed,_=candidates;item,_=seed()
    with factory() as uow:
        task=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id==item));tid=task.id
    handler=ResumeParseHandler(imports[0][0].app.state.file_service,None,factory)
    JobRunner(BackgroundJobService(factory),{'resume.parse':handler}).execute(tid)
    with factory() as uow:
        assert uow.session.get(BackgroundJob,tid).state=='failed'
        row=uow.session.get(ImportItem,item)
        assert row.status=='failed' and row.error_code=='DOCUMENT_FORMAT_UNAVAILABLE'
        assert row.resume_version_id is None


def test_provenance_forgery_rolls_back(candidates):
    from app.talents.candidate_service import CandidateService
    from app.core.errors import DomainError
    _,factory,seed,_=candidates;item,extracted=seed()
    with factory() as uow:
        run=uow.session.get(AiRun,extracted.ai_run_id);run.source_refs=[{'source_type':'stored_file','source_id':'999999'}];uow.commit()
    with pytest.raises(DomainError) as error:CandidateService(factory).materialize(item,extracted)
    assert error.value.code=='EXTRACTION_SOURCE_MISMATCH'
    with factory() as uow:assert uow.session.get(ImportItem,item).resume_version_id is None


def test_email_completion_enqueues_once_and_cas(candidates):
    from app.talents.candidate_service import CandidateService
    imports,factory,seed,_=candidates;service=CandidateService(factory);result=service.materialize(*seed())
    headers=login(imports[0],'hr');url=f'/api/v1/talents/{result.candidate_id}/contacts'
    response=imports[0][0].patch(url,json={'email':'User+cv@example.com','reason':'本人提供'},headers={**headers,'If-Match':'2'})
    # Obtain persisted row version; creating the resume pointer already bumped it.
    if response.status_code==409:
        with factory() as uow:version=uow.session.get(Candidate,result.candidate_id).row_version
        response=imports[0][0].patch(url,json={'email':'User+cv@example.com','reason':'本人提供'},headers={**headers,'If-Match':str(version)})
    assert response.status_code==200,response.text
    version=response.json()['data']['version']
    again=imports[0][0].patch(url,json={'email':'User+cv@example.com','reason':'再次核实'},headers={**headers,'If-Match':str(version)})
    assert again.status_code==200,again.text
    stale=imports[0][0].patch(url,json={'phone':'123','reason':'旧版本'},headers={**headers,'If-Match':'1'})
    assert stale.status_code==409
    with factory() as uow:
        assert uow.session.get(Candidate,result.candidate_id).email_normalized=='User+cv@example.com'
        assert len(list(uow.session.scalars(select(BackgroundJob).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==result.candidate_id))))==1


def test_collision_blocks_both_candidates(candidates):
    from app.talents.candidate_service import CandidateService
    _,factory,seed,_=candidates;service=CandidateService(factory)
    a=service.materialize(*seed('same@example.com'));b=service.materialize(*seed('same@example.com'))
    assert b.state=='duplicate_review' and b.next_task is None
    with factory() as uow:
        assert uow.session.get(Candidate,a.candidate_id).status=='duplicate_review'
        case=uow.session.scalar(select(DuplicateCase).where(DuplicateCase.candidate_a_id==a.candidate_id,DuplicateCase.candidate_b_id==b.candidate_id))
        assert case and case.status=='pending'


def test_concurrent_materialization_one_identity(candidates):
    from app.talents.candidate_service import CandidateService
    from concurrent.futures import ThreadPoolExecutor
    _,factory,seed,_=candidates;service=CandidateService(factory);args=seed()
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:service.materialize(*args),range(2)))
    assert values[0].candidate_id==values[1].candidate_id


def test_archive_prevents_contact_resumption(candidates):
    from app.talents.candidate_service import CandidateService
    imports,factory,seed,_=candidates;result=CandidateService(factory).materialize(*seed())
    with factory() as uow:version=uow.session.get(Candidate,result.candidate_id).row_version
    headers=login(imports[0],'hr');url=f'/api/v1/talents/{result.candidate_id}'
    archived=imports[0][0].post(url+'/archive',json={'reason':'停止招聘'},headers={**headers,'If-Match':str(version)})
    assert archived.status_code==200,archived.text
    patch=imports[0][0].patch(url+'/contacts',json={'email':'new@example.com','reason':'修改'},headers={**headers,'If-Match':str(archived.json()['data']['version'])})
    assert patch.status_code==409 and patch.json()['code']=='CANDIDATE_ARCHIVED'


def test_admin_and_missing_read_denied(candidates):
    imports,factory,_,owned=candidates;client=imports[0][0]
    with factory() as uow:
        row=Candidate(display_name='s');uow.session.add(row);uow.session.flush();cid=row.id;owned.append(cid);uow.commit()
    url=f'/api/v1/talents/{cid}/contacts';payload={'email':'s@example.com','reason':'核实'}
    assert client.patch(url,json=payload,headers={**login(imports[0],'admin'),'If-Match':'1'}).status_code==403
    with factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role']);role.permission_codes=[p for p in role.permission_codes if p!='talent.read'];uow.commit()
    assert client.patch(url,json=payload,headers={**login(imports[0],'hr'),'If-Match':'1'}).status_code==403
    with factory() as uow:assert uow.session.get(Candidate,cid).email is None


@pytest.fixture
def parse_case(candidates):
    """真实DOCX解析和模型网关，HTTP传输替身只生成合成事实。"""
    import httpx,json
    from app.ai_runtime.models import WorkflowConfig
    from app.ai_runtime.gateway import ModelGateway
    from app.core.secrets import SecretCipher
    from cryptography.fernet import Fernet
    from app.ingestion.extraction_types import ResumeFacts
    from tests.integration.test_core_document_parsers import docx_bytes
    imports,factory,seed,_=candidates
    data=docx_bytes(lambda doc:doc.add_paragraph('张三 Python'))
    item,extracted=seed(files=[('files',('resume.docx',data,'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))])
    reply=extracted.model_dump(mode='json',exclude={'ai_run_id'})
    for evidence in reply['citations']:evidence['locator']='docx:body:b1'
    for sources in reply['field_sources'].values():
        for evidence in sources:evidence['locator']='docx:body:b1'
    cipher=SecretCipher(Fernet.generate_key().decode())
    with factory() as uow:
        run=uow.session.get(AiRun,extracted.ai_run_id);mid=run.model_config_id;pid=run.prompt_version_id
        prompt=uow.session.get(PromptVersion,pid);prompt.output_schema=ResumeFacts.model_json_schema()
        model=uow.session.get(ModelConfig,mid);model.enabled=True;model.capabilities={'verified':True,'text':True,'json':True}
        model.secret_ciphertext=cipher.encrypt('synthetic-test-secret')
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='extract'))
        keys=['model_config_id','prompt_version_id','enabled','timeout_seconds','max_retries','config_revision'];old={k:getattr(flow,k) for k in keys}
        flow.model_config_id=mid;flow.prompt_version_id=pid;flow.enabled=True;flow.timeout_seconds=30;flow.max_retries=0;flow.config_revision+=1
        task=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.entity_type=='import_item',BackgroundJob.entity_id==item));tid=task.id;uow.commit()
    calls=[]
    def transport(request):
        calls.append(request)
        return httpx.Response(200,json={'model':'deepseek-flash','choices':[{'finish_reason':'stop','message':{'content':json.dumps(reply,ensure_ascii=False)}}]})
    gateway=ModelGateway(factory,cipher,httpx.MockTransport(transport))
    yield imports,factory,item,tid,gateway,calls
    with factory() as uow:
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='extract'))
        for key,value in old.items():setattr(flow,key,value)
        uow.session.execute(delete(AiRun).where(AiRun.model_config_id==mid,AiRun.id!=extracted.ai_run_id));uow.commit()


def test_worker_docx_to_immutable_resume(parse_case):
    from app.ingestion.worker import ResumeParseHandler
    from app.runtime.job_service import JobRunner,BackgroundJobService
    imports,factory,item,tid,gateway,calls=parse_case
    handler=ResumeParseHandler(imports[0][0].app.state.file_service,gateway,factory)
    tasks=BackgroundJobService(factory);lease=tasks.claim(tid,'test')
    callback=handler.prepare(lease)
    with handler.finalization_context():tasks.run_atomic(lease,callback)
    with factory() as uow:
        task=uow.session.get(BackgroundJob,tid);assert task.state=='succeeded',task.error_code
        row=uow.session.get(ImportItem,item);resume=uow.session.get(ResumeVersion,row.resume_version_id)
        assert resume.raw_text=='张三 Python' and 'python-docx' in resume.parser_revision
        assert uow.session.get(Candidate,resume.candidate_id).status=='pending_email'
    assert len(calls)==1


def test_worker_hash_mismatch_never_calls_model(parse_case):
    from app.ingestion.worker import ResumeParseHandler
    from app.runtime.job_service import JobRunner,BackgroundJobService
    from app.files.models import StoredFile
    imports,factory,item,tid,gateway,calls=parse_case
    with factory() as uow:
        row=uow.session.get(ImportItem,item);uow.session.get(StoredFile,row.file_id).sha256='0'*64;uow.commit()
    JobRunner(BackgroundJobService(factory),{'resume.parse':ResumeParseHandler(imports[0][0].app.state.file_service,gateway,factory)}).execute(tid)
    with factory() as uow:
        row=uow.session.get(ImportItem,item);assert row.status=='failed' and row.error_code=='FILE_INTEGRITY_MISMATCH'
    assert calls==[]


def test_worker_revoked_permission_before_finalize(parse_case):
    from app.ingestion.worker import ResumeParseHandler
    from app.runtime.job_service import BackgroundJobService
    from app.core.errors import DomainError
    imports,factory,item,tid,gateway,calls=parse_case
    tasks=BackgroundJobService(factory);lease=tasks.claim(tid,'test')
    handler=ResumeParseHandler(imports[0][0].app.state.file_service,gateway,factory)
    callback=handler.prepare(lease)
    with factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role']);role.permission_codes=[p for p in role.permission_codes if p!='import.write'];uow.commit()
    with pytest.raises(DomainError),handler.finalization_context():tasks.run_atomic(lease,callback)
    with factory() as uow:
        assert uow.session.get(ImportItem,item).resume_version_id is None
        assert uow.session.get(BackgroundJob,tid).state=='running'
    assert len(calls)==1


def test_stale_lease_rolls_back_materialization(parse_case):
    from datetime import timedelta
    from app.ingestion.worker import ResumeParseHandler
    from app.runtime.job_service import BackgroundJobService
    from app.core.errors import DomainError
    imports,factory,item,tid,gateway,_=parse_case
    tasks=BackgroundJobService(factory);lease=tasks.claim(tid,'test')
    handler=ResumeParseHandler(imports[0][0].app.state.file_service,gateway,factory);callback=handler.prepare(lease)
    with factory() as uow:
        row=uow.session.get(BackgroundJob,tid);row.lease_until-=timedelta(days=1);uow.commit()
    with pytest.raises(DomainError,match='STALE_JOB_LEASE'),handler.finalization_context():tasks.run_atomic(lease,callback)
    with factory() as uow:assert uow.session.get(ImportItem,item).resume_version_id is None


def test_correction_rejects_provenance_injection(candidates):
    from app.talents.candidate_service import CandidateService
    imports,factory,seed,_=candidates;result=CandidateService(factory).materialize(*seed())
    response=imports[0][0].post(f'/api/v1/talents/{result.candidate_id}/resume-corrections',json={'base_resume_version_id':result.resume_version_id,'changes':{'field_sources':{}},'reason':'synthetic'},headers={**login(imports[0],'hr'),'Idempotency-Key':uuid4().hex})
    assert response.status_code==422 and response.json()['code']=='INVALID_CORRECTION'


def test_disabled_workflow_explains_failure(parse_case):
    from app.ingestion.worker import ResumeParseHandler
    from app.ai_runtime.models import WorkflowConfig
    from app.runtime.job_service import JobRunner,BackgroundJobService
    imports,factory,item,tid,gateway,calls=parse_case
    with factory() as uow:
        uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='extract')).enabled=False;uow.commit()
    JobRunner(BackgroundJobService(factory),{'resume.parse':ResumeParseHandler(imports[0][0].app.state.file_service,gateway,factory)}).execute(tid)
    with factory() as uow:
        row=uow.session.get(ImportItem,item);assert row.status=='failed' and row.error_code=='AI_WORKFLOW_UNAVAILABLE'
    assert calls==[]


@pytest.mark.parametrize('change',['file','owner'])
def test_source_changed_before_model_does_not_transmit(parse_case,candidates,monkeypatch,change):
    from app.ingestion.worker import ResumeParseHandler
    from app.ingestion.parsers import DocxParser
    from app.runtime.job_service import BackgroundJobService
    from app.core.errors import DomainError
    imports,factory,item,tid,gateway,calls=parse_case
    other_item,_=candidates[2]()
    with factory() as uow:replacement=uow.session.get(ImportItem,other_item).file_id
    original=DocxParser.parse
    def parse_then_replace(parser,content):
        document=original(parser,content)
        with factory() as uow:
            row=uow.session.get(ImportItem,item)
            if change=='file':row.file_id=replacement
            else:
                from app.ingestion.models import ImportBatch
                uow.session.get(ImportBatch,row.batch_id).created_by=imports[0][4]['other']
            uow.commit()
        return document
    monkeypatch.setattr(DocxParser,'parse',parse_then_replace)
    tasks=BackgroundJobService(factory);lease=tasks.claim(tid,'test')
    handler=ResumeParseHandler(imports[0][0].app.state.file_service,gateway,factory)
    with pytest.raises(DomainError,match='IMPORT_SOURCE_CHANGED'):handler.prepare(lease)
    assert calls==[]
