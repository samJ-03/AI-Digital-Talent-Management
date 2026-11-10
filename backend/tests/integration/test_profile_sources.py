"""T17隔离MySQL画像验收，模型仅使用MockTransport合成响应。"""
import json
from copy import deepcopy
import pytest
from sqlalchemy import select,delete,update
from tests.integration.test_candidate_merge import merges,candidates,imports,identity
from tests.integration.test_identity import login
from app.identity.models import Role
from app.talents.models import Candidate,CandidateProfile
from app.recruitment.models import RecruitmentEvent
from app.ai_runtime.models import AiRun,ModelConfig,PromptVersion,WorkflowConfig


@pytest.fixture
def profiles(merges):
    """把既有合成档案补成可核实的事实画像，保留独立私有面试记录。"""
    imports,factory,i=merges
    with factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role']);role.permission_codes=sorted(set(role.permission_codes)|{'profile.read','profile.write','recruitment.read'})
        for cid,rid,pid in [(i['a'],i['ar'],i['profiles'][0]),(i['b'],i['br'],i['profiles'][1])]:
            row=uow.session.get(CandidateProfile,pid);row.summary='张三';row.skills=['Python'];row.experiences=[];row.confirmed_by=imports[0][4]['hr']
            row.source_record_refs=[{'source_type':'resume_version','source_id':str(rid)}]
            row.evidence=[{'field':path,'text':value,'source':{'source_type':'resume_version','source_id':str(rid),'locator':loc,'quote':value}} for path,value,loc in [('summary_claims.0','张三','identity.name'),('skills.0','Python','skills.0')]]
        event=RecruitmentEvent(application_id=i['apps'][0],event_type='interview.note',content={'note':'PRIVATE_EVALUATION_SENTINEL'},actor_id=imports[0][4]['hr']);uow.session.add(event);uow.session.flush();eid=event.id;uow.commit()
    yield imports,factory,i
    with factory() as uow:
        from app.assessment.models.exams import ExamAttempt
        from app.assessment.models.grading import ScoreReport
        uow.session.execute(update(ExamAttempt).where(ExamAttempt.id.in_(i['attempts'])).values(current_score_report_id=None))
        uow.session.execute(delete(ScoreReport).where(ScoreReport.attempt_id.in_(i['attempts'])))
        uow.session.execute(delete(RecruitmentEvent).where(RecruitmentEvent.id==eid))
        uow.session.execute(update(Candidate).where(Candidate.id.in_([i['a'],i['b']])).values(current_profile_id=None))
        uow.session.execute(delete(CandidateProfile).where(CandidateProfile.candidate_id.in_([i['a'],i['b']]),CandidateProfile.id.not_in(i['profiles'])))
        uow.commit()


def test_no_private_interview_in_shared_summary(profiles):
    imports,_,i=profiles;client=imports[0][0];login(imports[0],'other')
    response=client.get(f"/api/v1/talents/{i['a']}/profile")
    assert response.status_code==200,response.text
    data=response.json()['data'];assert 'PRIVATE_EVALUATION_SENTINEL' not in data['summary']
    assert data['authorized_application_views']==[] and 'PRIVATE_EVALUATION_SENTINEL' not in response.text


def test_no_exam_no_radar(profiles):
    imports,_,i=profiles;client=imports[0][0];login(imports[0],'hr')
    response=client.get(f"/api/v1/talents/{i['a']}/profile")
    assert response.status_code==200,response.text
    views=response.json()['data']['authorized_application_views'];assert views
    assert all(v['radar'] is None and v['exam_results']==[] for v in views)


def test_manual_revision_preserves_ai_version(profiles):
    imports,factory,i=profiles;client=imports[0][0]
    response=client.post(f"/api/v1/talents/{i['a']}/profile-revisions",json={'base_profile_id':i['profiles'][0],'changes':{'summary_claims':['Python']},'reason':'调整摘要重点'},headers={**login(imports[0],'hr'),'Idempotency-Key':'profile-revision-test'})
    assert response.status_code==200,response.text
    with factory() as uow:
        assert uow.session.get(CandidateProfile,i['profiles'][0]).summary=='张三'
        row=uow.session.get(CandidateProfile,int(response.json()['data']['id']));assert row.summary=='Python' and row.version_no==2 and row.confirmed_by==imports[0][4]['hr']


@pytest.fixture
def generation(profiles):
    """真实网关/持久化记录与受控HTTP；绝不访问真实供应商。"""
    import httpx
    from cryptography.fernet import Fernet
    from app.core.secrets import SecretCipher
    from app.ai_runtime.gateway import ModelGateway
    from app.talents.profile_builder import ProfileBuilder
    from app.talents.profile_schemas import ProfileOutput
    from app.talents.profile_service import ProfileService
    from tests.integration.test_candidate_merge import resolve
    imports,factory,i=profiles;assert resolve(profiles,'different_person').status_code==200
    cipher=SecretCipher(Fernet.generate_key().decode());calls=[];mutations=[]
    with factory() as uow:
        row=uow.session.get(Candidate,i['a']);row.current_profile_id=None
        from app.talents.models import ResumeVersion
        run=uow.session.get(AiRun,uow.session.get(ResumeVersion,i['ar']).field_sources['ai_run_id'])
        mid=run.model_config_id
        model=uow.session.get(ModelConfig,mid);model.enabled=True;model.capabilities={'verified':True,'text':True,'json':True};model.secret_ciphertext=cipher.encrypt('synthetic-only')
        prompt=PromptVersion(task_type='profile',revision_no=(uow.session.scalar(select(__import__('sqlalchemy').func.max(PromptVersion.revision_no)).where(PromptVersion.task_type=='profile')) or 0)+1,content='Select complete factual leaves only',output_schema=ProfileOutput.model_json_schema(),status='published')
        uow.session.add(prompt);uow.session.flush();pid=prompt.id
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='profile'));keys=['enabled','model_config_id','prompt_version_id','timeout_seconds','max_retries','config_revision'];old={k:getattr(flow,k) for k in keys}
        flow.enabled=True;flow.model_config_id=mid;flow.prompt_version_id=pid;flow.timeout_seconds=30;flow.max_retries=0;flow.config_revision+=1;uow.commit()
    def transport(request):
        body=json.loads(request.content);calls.append(body)
        sources=json.loads(body['messages'][1]['content'])['untrusted_evidence'];by={s['locator']:s for s in sources}
        selected=[by['identity.name'],by['skills.0']]
        reply={'summary_claims':[{'text':selected[0]['quote'],'source':selected[0]}],'skills':[{'text':selected[1]['quote'],'source':selected[1]}],'experiences':[],'citations':selected}
        for mutate in mutations:mutate(reply)
        return httpx.Response(200,json={'model':'deepseek-flash','choices':[{'finish_reason':'stop','message':{'content':json.dumps(reply,ensure_ascii=False)}}]})
    service=ProfileService(factory,ProfileBuilder(ModelGateway(factory,cipher,httpx.MockTransport(transport))))
    yield imports,factory,i,service,calls,mutations
    with factory() as uow:
        uow.session.execute(update(Candidate).where(Candidate.id.in_([i['a'],i['b']])).values(current_profile_id=None))
        uow.session.execute(delete(CandidateProfile).where(CandidateProfile.candidate_id.in_([i['a'],i['b']]),CandidateProfile.id.not_in(i['profiles'])))
        uow.session.execute(delete(AiRun).where(AiRun.model_config_id==mid,AiRun.task_type=='profile'))
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='profile'))
        for k,v in old.items():setattr(flow,k,v)
        uow.session.flush();uow.session.execute(delete(PromptVersion).where(PromptVersion.id==pid));uow.commit()


def test_all_claims_have_sources(generation):
    _,factory,i,service,calls,_=generation
    result=service.generate(i['a'],i['ar'])
    assert result.summary=='张三' and result.skills==['Python'] and result.ai_run_id
    assert all(e['source']['source_type']=='resume_version' and e['source']['source_id']==str(i['ar']) for e in result.evidence)
    assert 'PRIVATE_EVALUATION_SENTINEL' not in json.dumps(calls,ensure_ascii=False) and 'same@example.com' not in json.dumps(calls)
    with factory() as uow:assert uow.session.get(AiRun,int(result.ai_run_id)).state=='succeeded'


def test_foreign_source_never_success(generation):
    from app.core.errors import DomainError
    _,factory,i,service,_,mutations=generation
    def foreign(reply):
        for c in reply['citations']:c['source_id']=str(i['br'])
    mutations.append(foreign)
    with pytest.raises(DomainError,match='MODEL_OUTPUT_INVALID'):service.generate(i['a'],i['ar'])
    with factory() as uow:
        assert uow.session.get(Candidate,i['a']).current_profile_id is None
        assert uow.session.scalar(select(AiRun).where(AiRun.task_type=='profile')).state=='invalid'


def test_repeated_generation_does_not_call_model(generation):
    _,_,i,service,calls,_=generation
    a=service.generate(i['a'],i['ar']);b=service.generate(i['a'],i['ar'])
    assert a.id==b.id and len(calls)==1


def test_worker_registered_and_finalizes(generation):
    from app.talents.profile_worker import ProfileBuildHandler
    from app.runtime.job_service import JobRunner,BackgroundJobService
    from app.runtime.models import BackgroundJob
    _,factory,i,service,calls,_=generation
    with factory() as uow:tid=uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build'))
    JobRunner(BackgroundJobService(factory),{'profile.build':ProfileBuildHandler(service)}).execute(tid)
    with factory() as uow:
        assert uow.session.get(BackgroundJob,tid).state=='succeeded'
        assert uow.session.get(Candidate,i['a']).current_profile_id is not None
    assert len(calls)==1


def test_truncated_claim_rejected_before_success(generation):
    from app.core.errors import DomainError
    _,_,i,service,_,mutations=generation
    def truncate(reply):
        reply['skills'][0]['text']='Py';reply['skills'][0]['source']['quote']='Py'
    mutations.append(truncate)
    with pytest.raises(DomainError,match='MODEL_OUTPUT_INVALID'):service.generate(i['a'],i['ar'])


def test_late_result_never_overwrites_new_pointer(generation):
    from app.core.errors import DomainError
    _,factory,i,service,_,mutations=generation
    def changed(reply):
        with factory() as uow:uow.session.get(Candidate,i['a']).current_profile_id=i['profiles'][0];uow.commit()
    mutations.append(changed)
    with pytest.raises(DomainError,match='PROFILE_SOURCE_STALE'):service.generate(i['a'],i['ar'])
    with factory() as uow:assert uow.session.get(Candidate,i['a']).current_profile_id==i['profiles'][0]


def test_manual_revision_rejects_private_note(profiles):
    imports,factory,i=profiles
    response=imports[0][0].post(f"/api/v1/talents/{i['a']}/profile-revisions",json={'base_profile_id':i['profiles'][0],'changes':{'summary_claims':['PRIVATE_EVALUATION_SENTINEL']},'reason':'尝试混入面试评价'},headers={**login(imports[0],'hr'),'Idempotency-Key':'invalid-profile-revision'})
    assert response.status_code==422,response.text
    with factory() as uow:assert uow.session.get(Candidate,i['a']).current_profile_id==i['profiles'][0]


def test_official_report_is_whitelisted(profiles):
    from app.assessment.models.grading import ScoreReport
    from app.assessment.models.exams import ExamAttempt
    imports,factory,i=profiles
    with factory() as uow:
        report=ScoreReport(attempt_id=i['attempts'][0],version_no=1,objective_score=60,subjective_score=28,total_score=88,item_score_snapshot={'answer':'ANSWER_SENTINEL'},confirmed_by=imports[0][4]['hr'],reason='正式确认')
        uow.session.add(report);uow.session.flush();uow.session.get(ExamAttempt,i['attempts'][0]).current_score_report_id=report.id;uow.commit()
    login(imports[0],'hr');response=imports[0][0].get(f"/api/v1/talents/{i['a']}/profile")
    assert response.status_code==200,response.text
    view=response.json()['data']['authorized_application_views'][0]
    assert view['exam_results'][0]['total_score']=='88.00' and view['radar'] is None
    assert 'ANSWER_SENTINEL' not in response.text


def test_private_permissions_revoked_immediately(profiles):
    imports,factory,i=profiles;client=imports[0][0];login(imports[0],'hr');url=f"/api/v1/talents/{i['a']}/profile"
    first=client.get(url);assert 'PRIVATE_EVALUATION_SENTINEL' in first.text
    with factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role']);role.permission_codes=[p for p in role.permission_codes if p!='recruitment.read'];uow.commit()
    response=client.get(url);assert response.status_code==200 and 'PRIVATE_EVALUATION_SENTINEL' not in response.text


def test_pipeline_resume_recovers_legacy_once(generation):
    from app.talents.pipeline_resume import PipelineResume
    from app.runtime.models import BackgroundJob
    _,factory,i,_,calls,_=generation
    with factory() as uow:
        old=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build'));old.state='failed';old.error_code='HANDLER_NOT_REGISTERED';uow.commit()
    recovery=PipelineResume(factory)
    assert recovery.recover_legacy()==1 and recovery.recover_legacy()==0
    recovery.consume_due();recovery.consume_due()
    with factory() as uow:
        jobs=list(uow.session.scalars(select(BackgroundJob).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build',BackgroundJob.state=='queued')))
        assert len(jobs)==1 and 'profile_revision' in jobs[0].input_refs
        jobs[0].state='failed';jobs[0].error_code='PROFILE_CONFIG_UNAVAILABLE';uow.commit()
    assert recovery.recover_legacy()==0
    assert calls==[]


def test_pipeline_disabled_or_blocked_never_queues(generation):
    from app.talents.pipeline_resume import PipelineResume
    from app.runtime.models import BackgroundJob,OutboxEvent
    _,factory,i,_,calls,_=generation
    with factory() as uow:
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='profile'));flow.enabled=False
        old=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build'));old.state='failed';old.error_code='HANDLER_NOT_REGISTERED';uow.commit()
    recovery=PipelineResume(factory);assert recovery.recover_legacy()==0;assert recovery.consume_due()==0
    with factory() as uow:
        events=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='pipeline.resume',OutboxEvent.aggregate_id==i['a'])))
        assert events and all(e.state=='pending' for e in events)
    assert calls==[]


def test_manual_revision_preserves_real_ai_version(generation):
    imports,factory,i,service,calls,_=generation;original=service.generate(i['a'],i['ar'])
    headers={**login(imports[0],'hr'),'Idempotency-Key':'manual-real-ai-version'}
    body={'base_profile_id':int(original.id),'changes':{'summary_claims':['Python']},'reason':'HR调整事实重点'}
    url=f"/api/v1/talents/{i['a']}/profile-revisions"
    response=imports[0][0].post(url,json=body,headers=headers);assert response.status_code==200,response.text
    assert imports[0][0].post(url,json=body,headers=headers).json()['data']['id']==response.json()['data']['id']
    with factory() as uow:
        old=uow.session.get(CandidateProfile,int(original.id));new=uow.session.get(CandidateProfile,int(response.json()['data']['id']))
        assert old.ai_run_id and old.summary=='张三' and new.ai_run_id is None and new.summary=='Python'
        assert new.version_no==old.version_no+1
        from app.audit.models import AuditLog
        audit=uow.session.scalar(select(AuditLog).where(AuditLog.action=='profile.revise',AuditLog.entity_id==i['a']).order_by(AuditLog.id.desc()))
        assert audit.change_summary['reason']=='HR调整事实重点' and audit.change_summary['previous_version']==old.version_no
    assert len(calls)==1


def test_blocked_resume_event_does_not_starve_ready_event(generation):
    from app.talents.pipeline_resume import PipelineResume
    from app.runtime.models import OutboxEvent
    _,factory,i,_,_,_=generation
    with factory() as uow:uow.session.get(Candidate,i['a']).status='duplicate_review';uow.commit()
    consumer=PipelineResume(factory);consumer.consume_due(1);consumer.consume_due(1)
    with factory() as uow:
        event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_type=='pipeline.resume',OutboxEvent.aggregate_id==i['b']))
        assert event.state=='sent'


def test_contact_update_resumes_failed_profile_job(generation):
    from app.talents.pipeline_resume import PipelineResume
    from app.runtime.models import BackgroundJob
    imports,factory,i,_,calls,_=generation;consumer=PipelineResume(factory);consumer.consume_due()
    with factory() as uow:
        old=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build'));old.state='failed';old.error_code='DEPENDENCY_UNAVAILABLE'
        version=uow.session.get(Candidate,i['a']).row_version;uow.commit()
    response=imports[0][0].patch(f"/api/v1/talents/{i['a']}/contacts",json={'email':'updated@example.com','reason':'补齐邮箱'},headers={**login(imports[0],'hr'),'If-Match':str(version)})
    assert response.status_code==200,response.text
    consumer.consume_due()
    with factory() as uow:
        active=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build',BackgroundJob.state=='queued')))
        assert len(active)==1
    assert calls==[]


def test_expired_worker_lease_does_not_publish(generation):
    from datetime import timedelta
    from app.talents.profile_worker import ProfileBuildHandler
    from app.runtime.job_service import BackgroundJobService
    from app.runtime.models import BackgroundJob
    from app.core.errors import DomainError
    _,factory,i,service,_,_=generation
    with factory() as uow:tid=uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['a'],BackgroundJob.job_type=='profile.build'))
    tasks=BackgroundJobService(factory);lease=tasks.claim(tid,'test');handler=ProfileBuildHandler(service);callback=handler.prepare(lease)
    with factory() as uow:uow.session.get(BackgroundJob,tid).lease_until-=timedelta(days=1);uow.commit()
    with pytest.raises(DomainError,match='STALE_JOB_LEASE'),handler.finalization_context():tasks.run_atomic(lease,callback)
    with factory() as uow:assert uow.session.get(Candidate,i['a']).current_profile_id is None


def test_foreign_profile_version_hidden(profiles):
    imports,_,i=profiles;login(imports[0],'hr')
    response=imports[0][0].get(f"/api/v1/talents/{i['a']}/profile?version_id={i['profiles'][1]}")
    assert response.status_code==404


def test_review_resume_then_contact_has_one_active_job(generation):
    from app.talents.pipeline_resume import PipelineResume
    from app.runtime.models import BackgroundJob
    imports,factory,i,_,calls,_=generation
    with factory() as uow:uow.session.get(Candidate,i['b']).current_profile_id=None;uow.commit()
    PipelineResume(factory).consume_due()
    with factory() as uow:
        before=list(uow.session.scalars(select(BackgroundJob).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['b'],BackgroundJob.job_type=='profile.build',BackgroundJob.state=='queued')))
        assert len(before)==1 and ':resume:' in before[0].idempotency_key
        version=uow.session.get(Candidate,i['b']).row_version
    response=imports[0][0].patch(f"/api/v1/talents/{i['b']}/contacts",json={'phone':'13800000000','reason':'补充联系方式'},headers={**login(imports[0],'hr'),'If-Match':str(version)})
    assert response.status_code==200,response.text
    with factory() as uow:
        active=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==i['b'],BackgroundJob.job_type=='profile.build',BackgroundJob.state.in_(['queued','running','retry']))))
        assert len(active)==1
    assert calls==[]


@pytest.mark.parametrize('kind',['ascii','multibyte'])
def test_review_summary_storage_limit_invalidates_ai_run(generation,kind):
    from app.talents.models import ResumeVersion
    from app.core.errors import DomainError
    imports,factory,i,service,_,mutations=generation
    texts=[str(n)+('x'*18000 if kind=='ascii' else '文'*6000) for n in range(4)]
    with factory() as uow:
        old=uow.session.get(ResumeVersion,i['ar']);facts=deepcopy(old.structured_data)
        facts['projects']=[{'name':None,'role':None,'description':text} for text in texts]
        for n,text in enumerate(texts):
            path=f'projects.{n}.description';source={'source_type':'manual_correction','source_id':str(imports[0][4]['hr']),'locator':path,'quote':text}
            facts['field_sources'][path]=[source];facts['citations'].append(source)
        # New synthetic immutable resume snapshot; no historical row is edited.
        new=ResumeVersion(candidate_id=i['a'],file_id=old.file_id,version_no=2,parent_version_id=old.id,structured_data=facts,field_sources={'kind':'synthetic_fixture'},parser_revision=old.parser_revision,state='confirmed',change_reason='合成长项目资料')
        uow.session.add(new);uow.session.flush();rid=new.id;uow.session.get(Candidate,i['a']).current_resume_version_id=rid;uow.commit()
    def long_summary(reply):
        sources=[{'source_type':'resume_version','source_id':str(rid),'locator':f'projects.{n}.description','quote':text} for n,text in enumerate(texts)]
        reply['summary_claims']=[{'text':s['quote'],'source':s} for s in sources];reply['citations']+=sources
        assert len(json.dumps(reply,ensure_ascii=False).encode())<256*1024
    mutations.append(long_summary)
    with pytest.raises(DomainError,match='MODEL_OUTPUT_INVALID'):service.generate(i['a'],rid)
    with factory() as uow:
        run=uow.session.scalar(select(AiRun).where(AiRun.task_type=='profile').order_by(AiRun.id.desc()))
        assert run.state=='invalid' and uow.session.get(Candidate,i['a']).current_profile_id is None
        source={'source_type':'resume_version','source_id':str(rid),'locator':'projects.0.description','quote':texts[0]}
        manual=CandidateProfile(candidate_id=i['a'],resume_version_id=rid,version_no=2,summary=texts[0],skills=[],experiences=[],evidence=[{'field':'summary_claims.0','text':texts[0],'source':source}],source_record_refs=[{'source_type':'resume_version','source_id':str(rid)}],confirmed_by=imports[0][4]['hr'])
        uow.session.add(manual);uow.session.flush();manual_id=manual.id;uow.session.get(Candidate,i['a']).current_profile_id=manual.id;uow.commit()
    response=imports[0][0].post(f"/api/v1/talents/{i['a']}/profile-revisions",json={'base_profile_id':manual_id,'changes':{'summary_claims':texts},'reason':'检查人工长摘要预算'},headers={**login(imports[0],'hr'),'Idempotency-Key':'long-manual-'+kind})
    assert response.status_code==422 and response.json()['code']=='INVALID_PROFILE_REVISION',response.text
    with factory() as uow:assert uow.session.get(Candidate,i['a']).current_profile_id==manual_id
