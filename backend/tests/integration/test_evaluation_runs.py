"""T19真实隔离MySQL验收；画像供应商仅Mock，无邮件副作用。"""
import pytest
from sqlalchemy import select,delete,update
from tests.integration.test_profile_sources import generation,profiles,merges,candidates,imports,identity
from tests.integration.test_identity import login
from app.identity.models import Role
from app.talents.models import Candidate
from app.jobs.models import Job,JobVersion
from app.recruitment.models import Application,RecruitmentEvent
from app.evaluation.models import EvaluationRun,ScreeningDetail,MatchResult
from app.runtime.models import BackgroundJob,OutboxEvent

@pytest.fixture
def evaluations(generation):
    """冻结来源均来自合成且有效的共享画像；清理仅本fixture数据。"""
    imports,factory,i,profiles_service,_,_=generation
    profiles_service.generate(i['a'],i['ar'])
    with factory() as uow:
        role=uow.session.get(Role,imports[0][4]['hr_role']);role.permission_codes=sorted(set(role.permission_codes)|{'evaluation.write','evaluation.read','recruitment.write','recruitment.read','job.read'})
        job=uow.session.get(Job,i['job']);job.current_version_id=i['jv']
        jv=uow.session.get(JobVersion,i['jv']);jv.conditions=[]
        uow.commit()
    yield imports,factory,i
    with factory() as uow:
        appids=list(uow.session.scalars(select(Application.id).where(Application.job_id==i['job'])))
        runs=list(uow.session.scalars(select(EvaluationRun.id).where(EvaluationRun.application_id.in_(appids),EvaluationRun.id.not_in(i['evaluations']))))
        tids=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='application',BackgroundJob.entity_id.in_(appids))))
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.event_type=='job.dispatch',OutboxEvent.aggregate_id.in_(tids)))
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.event_type.in_(['evaluation.match.requested','application.evaluate.requested']),OutboxEvent.aggregate_id.in_(appids+runs)))
        uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(tids)))
        uow.session.execute(update(Application).where(Application.id.in_(appids)).values(current_evaluation_id=None))
        uow.session.execute(delete(ScreeningDetail).where(ScreeningDetail.evaluation_run_id.in_(runs)))
        uow.session.execute(delete(MatchResult).where(MatchResult.evaluation_run_id.in_(runs)))
        uow.session.execute(delete(RecruitmentEvent).where(RecruitmentEvent.application_id.in_(appids),RecruitmentEvent.event_type.in_(['evaluation.override','application.created'])))
        uow.session.execute(delete(EvaluationRun).where(EvaluationRun.id.in_(runs)))
        uow.session.execute(delete(Application).where(Application.id.in_(appids),Application.id.not_in(i['apps'])))
        uow.session.get(Job,i['job']).current_version_id=None;uow.commit()

def start(evaluations,key='evaluation-start',who='hr',**body):
    """请求通过真实会话、CSRF和幂等命令。"""
    imports,_,i=evaluations
    return imports[0][0].post(f"/api/v1/applications/{i['apps'][0]}/evaluations",json={'reason':'HR主动重评',**body},headers={**login(imports[0],who),'Idempotency-Key':key})

def screen(evaluations,run_id):
    """内部确定性筛选不调用供应商。"""
    from app.evaluation.service import EvaluationService
    return EvaluationService(evaluations[1]).screen(int(run_id))

def test_reevaluate_manual_only_and_snapshot(evaluations):
    imports,factory,i=evaluations;response=start(evaluations)
    assert response.status_code==202,response.text
    data=response.json()['data'];rid=int(data['evaluation_id'])
    assert start(evaluations).json()['data']==data
    with factory() as uow:
        run=uow.session.get(EvaluationRun,rid)
        assert run.invitation_mode=='manual_only' and run.resume_version_id==i['ar'] and run.job_version_id==i['jv']
        assert run.screening_context['as_of'] and run.screening_context['normalization_revision']=='screening-core-v1'
        assert uow.session.get(Application,i['apps'][0]).stage=='hr_review'
    assert screen(evaluations,rid).screening_result=='pass'
    login(imports[0],'hr');view=imports[0][0].get(f'/api/v1/evaluations/{rid}')
    assert view.status_code==200 and view.json()['data']['is_current']
    assert 'PRIVATE_EVALUATION_SENTINEL' not in view.text

def test_missing_email_no_start(evaluations):
    _,factory,i=evaluations
    with factory() as uow:
        row=uow.session.get(Candidate,i['a']);row.email_valid=False;row.email=None;row.email_normalized=None;row.status='pending_email';uow.commit()
    response=start(evaluations);assert response.status_code==409,response.text
    with factory() as uow:assert uow.session.scalar(select(EvaluationRun.id).where(EvaluationRun.application_id==i['apps'][0],EvaluationRun.id.not_in(i['evaluations']))) is None

def test_stale_run_not_current(evaluations):
    _,factory,i=evaluations
    first=start(evaluations,'first');assert first.status_code==202,first.text
    second=start(evaluations,'second');assert second.status_code==202,second.text
    rid=int(first.json()['data']['evaluation_id']);current=int(second.json()['data']['evaluation_id'])
    assert not screen(evaluations,rid).is_current
    with factory() as uow:
        assert uow.session.get(Application,i['apps'][0]).current_evaluation_id==current
        assert uow.session.scalar(select(OutboxEvent.id).where(OutboxEvent.event_type=='evaluation.match.requested',OutboxEvent.aggregate_id==rid)) is None
    assert screen(evaluations,current).is_current

def test_override_keeps_original_result(evaluations):
    imports,factory,i=evaluations
    with factory() as uow:
        uow.session.get(JobVersion,i['jv']).conditions=[{'key':'education','field':'education','operator':'gte','expected':'bachelor','required':True}];uow.commit()
    response=start(evaluations);assert response.status_code==202,response.text
    rid=int(response.json()['data']['evaluation_id']);original=screen(evaluations,rid)
    assert original.screening_result=='unknown'
    url=f'/api/v1/evaluations/{rid}/override';body={'reason':'项目经历优秀，人工继续复核','decision':'continue'};headers={**login(imports[0],'hr'),'Idempotency-Key':'override'}
    result=imports[0][0].post(url,json=body,headers=headers);assert result.status_code==200,result.text
    assert imports[0][0].post(url,json=body,headers=headers).json()['data']==result.json()['data']
    with factory() as uow:
        run=uow.session.get(EvaluationRun,rid);assert run.screening_result=='unknown' and run.invitation_mode=='manual_only' and run.state=='matching'
        assert len(list(uow.session.scalars(select(ScreeningDetail).where(ScreeningDetail.evaluation_run_id==rid))))==1
        event=uow.session.scalar(select(RecruitmentEvent).where(RecruitmentEvent.event_type=='evaluation.override',RecruitmentEvent.application_id==i['apps'][0]));assert event.content['reason']==body['reason']
    login(imports[0],'hr');detail=imports[0][0].get(url.removesuffix('/override')).json()['data'];assert len(detail['override_events'])==1 and detail['screening_result']=='unknown'

def test_department_scope_and_source_injection(evaluations):
    response=start(evaluations,who='other');assert response.status_code in [403,404],response.text
    response=start(evaluations,screening_context={'as_of':'2000-01-01'});assert response.status_code==422,response.text
    response=start(evaluations,resume_version_id=evaluations[2]['br']);assert response.status_code==409,response.text

def test_one_canonical_application_per_job(evaluations):
    imports,factory,i=evaluations
    # 合成已完成合并的别名关系；真实合并事务在T16独立验收。
    with factory() as uow:
        uow.session.get(Candidate,i['a']).merged_into_id=i['b']
        old=uow.session.get(Application,i['apps'][0]);old.relationship_state='merged';old.canonical_application_id=i['apps'][1];uow.commit()
    response=imports[0][0].post(f"/api/v1/jobs/{i['job']}/applications",json={'candidate_ids':[i['a'],i['b']],'source':'talent_pool'},headers={**login(imports[0],'hr'),'Idempotency-Key':'canonical-app'})
    assert response.status_code==202,response.text
    assert len(response.json()['data'])==1 and int(response.json()['data'][0]['id'])==i['apps'][1]
    with factory() as uow:assert uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.job_type=='application.evaluate',BackgroundJob.entity_id.in_(i['apps']))) is None


@pytest.mark.parametrize('blocked',[False,True])
def test_new_relation_initial_evaluation_once(evaluations,blocked):
    imports,factory,i=evaluations
    with factory() as uow:uow.session.get(Application,i['apps'][0]).job_id=i['job'];uow.commit()
    # 独立人才根无此岗位关系，用既有合成导入工厂构造。
    # 删除不了历史关系，改用新岗位，并在finally清理其全部引用。
    ids=imports[0][4]
    with factory() as uow:
        job=Job(title='T19-new-position',department_id=ids['d1'],owner_hr_id=ids['hr'],headcount=1,status='open',auto_invite_enabled=False);uow.session.add(job);uow.session.flush()
        v=JobVersion(job_id=job.id,version_no=1,description='Synthetic',conditions=[],match_weights={},invite_threshold=70,invite_valid_hours=24,mail_template={},status='published');uow.session.add(v);uow.session.flush();job.current_version_id=v.id;jid=job.id;vid=v.id;uow.commit()
    try:
        url=f'/api/v1/jobs/{jid}/applications';body={'candidate_ids':[i['a'],i['a']],'source':'talent_pool'}
        if blocked:
            with factory() as uow:uow.session.get(Candidate,i['a']).email_valid=False;uow.commit()
        response=imports[0][0].post(url,json=body,headers={**login(imports[0],'hr'),'Idempotency-Key':'new-relation'});assert response.status_code==202,response.text
        data=response.json()['data'];assert len(data)==1
        if blocked:
            assert data[0]['task_ids']==[] and data[0]['current_evaluation_id'] is None
            from app.evaluation.initial_evaluation import InitialEvaluation
            from app.runtime.job_service import utc_naive
            from app.core.clock import Clock
            recovery=InitialEvaluation(factory);assert recovery.consume_due()==0
            with factory() as uow:
                uow.session.get(Candidate,i['a']).email_valid=True
                event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key==f"application-initial:{data[0]['id']}"));event.next_attempt_at=utc_naive(Clock().now());uow.commit()
            assert recovery.consume_due()==1 and recovery.consume_due()==0
            response=imports[0][0].post(url,json=body,headers={**login(imports[0],'hr'),'Idempotency-Key':'new-relation'})
            data=response.json()['data']
        assert len(data[0]['task_ids'])==1
        second=imports[0][0].post(url,json=body,headers={**login(imports[0],'hr'),'Idempotency-Key':'new-selection'});assert second.json()['data']==data
        from app.evaluation.service import EvaluationService
        from app.evaluation.worker import EvaluationHandler
        from app.runtime.job_service import JobRunner,BackgroundJobService
        tid=int(data[0]['task_ids'][0]);rid=int(data[0]['current_evaluation_id'])
        JobRunner(BackgroundJobService(factory),{'application.evaluate':EvaluationHandler(EvaluationService(factory))}).execute(tid)
        with factory() as uow:
            assert uow.session.get(BackgroundJob,tid).state=='succeeded'
            assert uow.session.get(EvaluationRun,rid).invitation_mode=='auto_allowed'
            assert uow.session.get(EvaluationRun,rid).screening_result=='pass'
            assert uow.session.scalar(select(OutboxEvent.id).where(OutboxEvent.event_type=='evaluation.match.requested',OutboxEvent.aggregate_id==rid))
    finally:
        with factory() as uow:
            aids=list(uow.session.scalars(select(Application.id).where(Application.job_id==jid)))
            rids=list(uow.session.scalars(select(EvaluationRun.id).where(EvaluationRun.application_id.in_(aids))))
            tids=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.entity_type=='application',BackgroundJob.entity_id.in_(aids))))
            uow.session.execute(delete(OutboxEvent).where(OutboxEvent.event_type=='job.dispatch',OutboxEvent.aggregate_id.in_(tids)))
            uow.session.execute(delete(OutboxEvent).where(OutboxEvent.event_type.in_(['evaluation.match.requested','application.evaluate.requested']),OutboxEvent.aggregate_id.in_(rids+aids)))
            uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(tids)))
            uow.session.execute(update(Application).where(Application.id.in_(aids)).values(current_evaluation_id=None))
            uow.session.execute(delete(ScreeningDetail).where(ScreeningDetail.evaluation_run_id.in_(rids)))
            uow.session.execute(delete(EvaluationRun).where(EvaluationRun.id.in_(rids)))
            uow.session.execute(delete(RecruitmentEvent).where(RecruitmentEvent.application_id.in_(aids)))
            uow.session.execute(delete(Application).where(Application.id.in_(aids)))
            uow.session.get(Job,jid).current_version_id=None;uow.session.flush();uow.session.execute(delete(JobVersion).where(JobVersion.id==vid));uow.session.execute(delete(Job).where(Job.id==jid));uow.commit()

@pytest.mark.parametrize('gate',['email','job','profile'])
def test_override_cannot_bypass_technical_gates(evaluations,gate):
    imports,factory,i=evaluations
    with factory() as uow:
        uow.session.get(JobVersion,i['jv']).conditions=[{'key':'education','field':'education','operator':'gte','expected':'bachelor','required':True}];uow.commit()
    r=start(evaluations);assert r.status_code==202,r.text
    rid=int(r.json()['data']['evaluation_id']);screen(evaluations,rid)
    with factory() as uow:
        if gate=='email':uow.session.get(Candidate,i['a']).email_valid=False
        elif gate=='job':uow.session.get(Job,i['job']).status='paused'
        else:uow.session.get(Candidate,i['a']).current_profile_id=None
        uow.commit()
    response=imports[0][0].post(f'/api/v1/evaluations/{rid}/override',json={'reason':'优秀人才','decision':'continue'},headers={**login(imports[0],'hr'),'Idempotency-Key':'override-blocked'})
    assert response.status_code==409,response.text
    with factory() as uow:assert uow.session.get(EvaluationRun,rid).override_by is None


def test_changed_frozen_content_fails_closed(evaluations):
    _,factory,i=evaluations;r=start(evaluations);assert r.status_code==202,r.text
    rid=int(r.json()['data']['evaluation_id'])
    with factory() as uow:uow.session.get(JobVersion,i['jv']).description='illegal in-place mutation';uow.commit()
    result=screen(evaluations,rid);assert result.state=='evaluation_failed' and result.screening_result is None


def test_context_migration_refuses_loss(evaluations):
    from alembic import command
    from alembic.config import Config
    r=start(evaluations);assert r.status_code==202,r.text
    config=Config('backend/alembic.ini')
    engine=evaluations[0][0][1]
    assert engine.url.database=='talent_test'
    config.set_main_option('sqlalchemy.url',engine.url.render_as_string(hide_password=False).replace('%','%%'))
    with pytest.raises(RuntimeError,match='screening contexts'):command.downgrade(config,'0007_import_upload_failures')


def test_department_read_and_csrf(evaluations):
    imports,_,_=evaluations;r=start(evaluations);assert r.status_code==202,r.text
    rid=r.json()['data']['evaluation_id'];login(imports[0],'other')
    response=imports[0][0].get(f'/api/v1/evaluations/{rid}');assert response.status_code==404,response.text
    login(imports[0],'hr')
    response=imports[0][0].post(f'/api/v1/evaluations/{rid}/override',json={'reason':'x','decision':'continue'},headers={'Idempotency-Key':'no-csrf'})
    assert response.status_code==403


def test_queued_evaluation_survives_identity_merge(evaluations):
    """任务中的旧人才引用仍合法，但合并后只能保存历史结果。"""
    from app.evaluation.service import EvaluationService
    from app.evaluation.worker import EvaluationHandler
    from app.runtime.job_service import JobRunner,BackgroundJobService
    _,factory,i=evaluations
    response=start(evaluations);assert response.status_code==202,response.text
    data=response.json()['data'];rid=int(data['evaluation_id']);tid=int(data['task_id'])
    with factory() as uow:
        uow.session.get(Candidate,i['a']).merged_into_id=i['b']
        other=uow.session.get(Application,i['apps'][1]);other.relationship_state='merged';other.canonical_application_id=i['apps'][0]
        pointer=uow.session.get(Application,i['apps'][0]).current_evaluation_id;uow.commit()
    JobRunner(BackgroundJobService(factory),{'application.evaluate':EvaluationHandler(EvaluationService(factory))}).execute(tid)
    with factory() as uow:
        assert uow.session.get(BackgroundJob,tid).state=='succeeded'
        run=uow.session.get(EvaluationRun,rid);assert run.state!='pending' and run.screening_result=='pass' and run.error_code=='EVALUATION_SUPERSEDED'
        assert uow.session.get(Application,i['apps'][0]).current_evaluation_id==pointer
        assert uow.session.scalar(select(OutboxEvent.id).where(OutboxEvent.event_type=='evaluation.match.requested',OutboxEvent.aggregate_id==rid)) is None
