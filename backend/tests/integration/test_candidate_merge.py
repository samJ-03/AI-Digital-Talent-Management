"""T16真实隔离MySQL测试；使用合成人才/考试，不调用模型或邮件。"""
from datetime import datetime,timedelta
import pytest
from sqlalchemy import select,delete,update
from tests.integration.test_candidate_materialization import candidates,imports,identity
from tests.integration.test_identity import login
from app.identity.models import Role
from app.talents.models import Candidate,ResumeVersion,CandidateProfile,DuplicateCase
from app.talents.candidate_service import CandidateService
from app.recruitment.models import Application
from app.evaluation.models import EvaluationRun
from app.jobs.models import Job,JobVersion
from app.assessment.models.papers import Paper,PaperVersion
from app.assessment.models.exams import ExamAttempt
from app.runtime.models import OutboxEvent


@pytest.fixture
def merges(candidates):
    """两份真实简历、同岗位两条关系及独立历史考试，按外键顺序清理。"""
    imports,factory,seed,_=candidates;ids=imports[0][4];service=CandidateService(factory)
    a=service.materialize(*seed('same@example.com'));b=service.materialize(*seed('same@example.com'))
    with factory() as uow:
        role=uow.session.get(Role,ids['hr_role']);role.permission_codes=sorted(set(role.permission_codes)|{'recruitment.write','evaluation.read'})
        job=Job(title=imports[0][2]+'-merge',department_id=ids['d1'],owner_hr_id=ids['hr'],headcount=1,status='open',auto_invite_enabled=False)
        paper=Paper(name=imports[0][2]+'-paper',department_id=ids['d1'],created_by=ids['hr']);uow.session.add_all([job,paper]);uow.session.flush()
        jv=JobVersion(job_id=job.id,version_no=1,description='Synthetic',conditions=[],match_weights={},invite_threshold=70,invite_valid_hours=24,mail_template={},status='published')
        pv=PaperVersion(paper_id=paper.id,version_no=1,duration_minutes=60,total_score=100,status='published');uow.session.add_all([jv,pv]);uow.session.flush()
        apps=[];profiles=[];attempts=[];evaluations=[]
        for result in [a,b]:
            profile=CandidateProfile(candidate_id=result.candidate_id,resume_version_id=result.resume_version_id,version_no=1,summary='Synthetic shared resume',skills=['Python'],experiences=[],evidence=[],source_record_refs=[])
            app=Application(candidate_id=result.candidate_id,job_id=job.id,source='import',stage='hr_review',relationship_state='active',current_round=1)
            uow.session.add_all([profile,app]);uow.session.flush();uow.session.get(Candidate,result.candidate_id).current_profile_id=profile.id
            evaluation=EvaluationRun(application_id=app.id,resume_version_id=result.resume_version_id,profile_id=profile.id,job_version_id=jv.id,state='matched',screening_result='pass',invitation_mode='manual_only')
            uow.session.add(evaluation);uow.session.flush()
            attempt=ExamAttempt(application_id=app.id,evaluation_run_id=evaluation.id,paper_version_id=pv.id,round_no=1,email_snapshot='same@example.com',invite_status='sent',valid_until=datetime.utcnow()+timedelta(days=1),state='finalized',final_score=88)
            uow.session.add(attempt);uow.session.flush();apps.append(app.id);profiles.append(profile.id);attempts.append(attempt.id);evaluations.append(evaluation.id)
        case=uow.session.scalar(select(DuplicateCase).where(DuplicateCase.candidate_a_id==a.candidate_id,DuplicateCase.candidate_b_id==b.candidate_id))
        info={'a':a.candidate_id,'b':b.candidate_id,'ar':a.resume_version_id,'br':b.resume_version_id,'case':case.id,'case_version':case.row_version,'job':job.id,'jv':jv.id,'paper':paper.id,'pv':pv.id,'apps':apps,'profiles':profiles,'attempts':attempts,'evaluations':evaluations};uow.commit()
    yield imports,factory,info
    with factory() as uow:
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.event_type=='pipeline.resume',OutboxEvent.aggregate_id.in_([info['a'],info['b']])))
        uow.session.execute(delete(ExamAttempt).where(ExamAttempt.id.in_(attempts)))
        uow.session.execute(update(Application).where(Application.id.in_(apps)).values(current_evaluation_id=None,canonical_application_id=None))
        uow.session.execute(delete(EvaluationRun).where(EvaluationRun.id.in_(evaluations)))
        uow.session.execute(delete(Application).where(Application.id.in_(apps)))
        uow.session.execute(update(Candidate).where(Candidate.id.in_([info['a'],info['b']])).values(current_profile_id=None))
        uow.session.execute(delete(CandidateProfile).where(CandidateProfile.id.in_(profiles)))
        uow.session.execute(delete(JobVersion).where(JobVersion.id==info['jv']));uow.session.execute(delete(Job).where(Job.id==info['job']))
        uow.session.execute(delete(PaperVersion).where(PaperVersion.id==info['pv']));uow.session.execute(delete(Paper).where(Paper.id==info['paper']));uow.commit()


def resolve(merges,decision='same_person',who='hr',overrides=None,version=None):
    """通过真实HTTP提交人工裁决，既有会话和CSRF均参与验证。"""
    imports,_,i=merges
    body={'decision':decision,'reason':'HR核实身份','application_resolutions':[]}
    if decision=='same_person':body.update(target_candidate_id=i['b'],application_resolutions=[{'job_id':i['job'],'primary_application_id':i['apps'][1],'secondary_application_ids':[i['apps'][0]]}])
    if overrides:body.update(overrides)
    return imports[0][0].post(f"/api/v1/duplicates/{i['case']}/resolve",json=body,headers={**login(imports[0],who),'If-Match':str(version or i['case_version'])})


def test_merge_two_historical_applications(merges):
    _,factory,i=merges;response=resolve(merges)
    assert response.status_code==200,response.text
    assert response.json()['data']['canonical_candidate_id']==str(i['b'])
    with factory() as uow:
        assert uow.session.get(Candidate,i['a']).merged_into_id==i['b']
        target=uow.session.get(Candidate,i['b']);assert target.current_resume_version_id==i['br'] and target.current_profile_id==i['profiles'][1]
        assert uow.session.get(ResumeVersion,i['ar']).candidate_id==i['a']
        assert uow.session.get(Application,i['apps'][0]).candidate_id==i['a']
        assert uow.session.get(Application,i['apps'][0]).canonical_application_id==i['apps'][1]
        assert [uow.session.get(ExamAttempt,aid).application_id for aid in i['attempts']]==i['apps']
        assert [uow.session.get(ExamAttempt,aid).final_score for aid in i['attempts']]==[88,88]


def test_active_attempt_conflict_no_partial_commit(merges):
    _,factory,i=merges
    with factory() as uow:
        uow.session.get(ExamAttempt,i['attempts'][0]).state='in_progress';uow.commit()
    response=resolve(merges);assert response.status_code==409,response.text
    assert response.json()['code']=='MERGE_CONFLICT'
    with factory() as uow:
        assert uow.session.get(DuplicateCase,i['case']).status=='pending'
        assert uow.session.get(Candidate,i['a']).merged_into_id is None
        assert uow.session.get(Application,i['apps'][0]).relationship_state=='active'


def test_unknown_other_department_denied(merges):
    response=resolve(merges,who='other');assert response.status_code==404,response.text
    assert 'attempt' not in response.text and 'score' not in response.text


def test_different_person_resumes_once(merges):
    _,factory,i=merges;response=resolve(merges,'different_person');assert response.status_code==200,response.text
    repeated=resolve(merges,'different_person');assert repeated.status_code==409
    with factory() as uow:
        assert all(uow.session.get(Candidate,cid).status=='ready' for cid in [i['a'],i['b']])
        events=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='pipeline.resume',OutboxEvent.aggregate_id.in_([i['a'],i['b']]))))
        assert len(events)==2 and all('email' not in str(e.payload_refs) for e in events)


def test_missing_resolution_rejected(merges):
    response=resolve(merges,overrides={'application_resolutions':[]})
    assert response.status_code==409 and response.json()['code']=='MERGE_CONFLICT'


def test_list_cases_contains_no_private_results(merges):
    imports,_,i=merges;client=imports[0][0];login(imports[0],'other')
    response=client.get('/api/v1/duplicates?status=pending&page=1&page_size=10')
    assert response.status_code==200,response.text
    assert str(i['case']) in [v['id'] for v in response.json()['data']['items']]
    assert 'final_score' not in response.text and 'applications' not in response.text


def test_merge_lock_order(merges):
    from app.talents.merge_service import DuplicateService,MergePlanner
    from app.talents.merge_schemas import MergeDecision
    from app.identity.models import User
    from app.identity.views import resolve_user
    imports,factory,i=merges
    with factory() as uow:
        actor=resolve_user(uow.session,uow.session.get(User,imports[0][4]['hr']))
    service=DuplicateService(factory)
    cmd=MergeDecision(decision='same_person',target_candidate_id=i['b'],reason='检查锁顺序',application_resolutions=[{'job_id':i['job'],'primary_application_id':i['apps'][1],'secondary_application_ids':[i['apps'][0]]}])
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    locks=[]
    def capture(connection,cursor,statement,parameters,context,many):
        if 'FROM candidates' in statement and 'FOR UPDATE' in statement:locks.append((statement,parameters))
    event.listen(Engine,'before_cursor_execute',capture)
    try:
        with service.candidates.identity_write(),factory() as uow:
            planner=MergePlanner(actor,i['case'],service);plan=planner.plan(uow,cmd)
            assert plan.conflicts==()
            uow.rollback()
    finally:event.remove(Engine,'before_cursor_execute',capture)
    assert locks and 'ORDER BY candidates.id' in locks[0][0]
    assert list(locks[0][1].values())==sorted([i['a'],i['b']])


def test_concurrent_opposite_merge_has_one_winner(merges):
    from concurrent.futures import ThreadPoolExecutor
    from app.talents.merge_service import DuplicateService
    from app.talents.merge_schemas import MergeDecision
    from app.identity.models import User
    from app.identity.views import resolve_user
    from app.core.errors import DomainError
    imports,factory,i=merges
    with factory() as uow:actor=resolve_user(uow.session,uow.session.get(User,imports[0][4]['hr']))
    def run(target):
        cmd=MergeDecision(decision='same_person',target_candidate_id=target,reason='并发核实',application_resolutions=[{'job_id':i['job'],'primary_application_id':i['apps'][1],'secondary_application_ids':[i['apps'][0]]}])
        try:return DuplicateService(factory).resolve(actor,i['case'],cmd,i['case_version'])
        except DomainError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[i['a'],i['b']]))
    assert sum(not isinstance(r,str) for r in results)==1 and 'VERSION_CONFLICT' in results
    with factory() as uow:
        roots=[uow.session.get(Candidate,cid) for cid in [i['a'],i['b']]]
        assert sum(r.merged_into_id is None for r in roots)==1


def test_alias_pending_case_still_blocks_contacts(merges,candidates):
    imports,factory,i=merges
    with factory() as uow:
        third=Candidate(display_name='第三人',status='duplicate_review');uow.session.add(third);uow.session.flush();candidates[3].append(third.id)
        a,b=sorted([i['a'],third.id]);uow.session.add(DuplicateCase(candidate_a_id=a,candidate_b_id=b,status='pending',evidence=[]));uow.commit()
    response=resolve(merges);assert response.status_code==200,response.text
    with factory() as uow:
        target=uow.session.get(Candidate,i['b']);assert target.status=='duplicate_review';version=target.row_version
    patch=imports[0][0].patch(f"/api/v1/talents/{i['b']}/contacts",json={'phone':'138 0000 0000','reason':'补充电话'},headers={**login(imports[0],'hr'),'If-Match':str(version)})
    assert patch.status_code==200,patch.text
    assert patch.json()['data']['status']=='duplicate_review'


def test_sole_primary_live_attempt_can_continue(merges):
    _,factory,i=merges
    with factory() as uow:
        uow.session.get(ExamAttempt,i['attempts'][1]).state='in_progress';uow.commit()
    response=resolve(merges);assert response.status_code==200,response.text
    with factory() as uow:assert uow.session.get(ExamAttempt,i['attempts'][1]).state=='in_progress'


def test_audit_failure_rolls_back_everything(merges,monkeypatch):
    from app.talents.merge_service import DuplicateService
    from app.core.errors import DomainError
    _,factory,i=merges
    def fail(*args,**kwargs):raise DomainError('SYNTHETIC_ABORT',409,'测试回滚')
    monkeypatch.setattr(DuplicateService,'audit',fail)
    response=resolve(merges);assert response.status_code==409
    with factory() as uow:
        assert uow.session.get(Candidate,i['a']).merged_into_id is None
        assert uow.session.get(DuplicateCase,i['case']).status=='pending'
        assert uow.session.get(Application,i['apps'][0]).relationship_state=='active'


def test_target_without_email_stays_pending(merges):
    _,factory,i=merges
    with factory() as uow:
        target=uow.session.get(Candidate,i['b']);target.email=None;target.email_normalized=None;target.email_valid=False;uow.commit()
    response=resolve(merges);assert response.status_code==200,response.text
    with factory() as uow:
        target=uow.session.get(Candidate,i['b']);assert target.status=='pending_email' and target.email is None
        assert list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='pipeline.resume',OutboxEvent.aggregate_id==i['b'])))==[]


def test_invalid_cross_job_mapping_rejected(merges):
    _,factory,i=merges
    response=resolve(merges,overrides={'application_resolutions':[{'job_id':i['job']+1000,'primary_application_id':i['apps'][1],'secondary_application_ids':[i['apps'][0]]}]})
    assert response.status_code==422,response.text
    with factory() as uow:assert uow.session.get(DuplicateCase,i['case']).status=='pending'


def test_archive_target_not_reactivated(merges):
    _,factory,i=merges
    with factory() as uow:uow.session.get(Candidate,i['b']).status='archived';uow.commit()
    response=resolve(merges);assert response.status_code==200,response.text
    with factory() as uow:assert uow.session.get(Candidate,i['b']).status=='archived'
