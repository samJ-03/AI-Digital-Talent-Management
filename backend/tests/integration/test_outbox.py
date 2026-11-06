"""平台开发工具：验证outbox的正常与失败场景；测试数据仅用于隔离环境。"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command as migration
from alembic.config import Config
from sqlalchemy import create_engine,select,delete,func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.clock import FrozenClock
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.core.uow import SqlAlchemyUow
from app.identity.models import Department
from app.runtime.models import BackgroundJob,OutboxEvent
from app.runtime.job_service import BackgroundJobService,JobSpec,JobRunner
from app.runtime.outbox import OutboxDispatcher
from app.runtime.scheduler import LeaseRecovery

@pytest.fixture
def jobs():
    url=os.environ['TALENT_TEST_DATABASE_URL']
    assert make_url(url).database=='talent_test'
    cfg=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'));cfg.set_main_option('sqlalchemy.url',url.replace('%','%%'));migration.upgrade(cfg,'head')
    engine=create_engine(url,pool_pre_ping=True)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    uows=lambda:SqlAlchemyUow(factory)
    clock=FrozenClock(datetime.now(timezone.utc))
    uid=uuid4().hex
    service=BackgroundJobService(uows,clock)
    yield service,uows,clock,uid
    with factory() as s:
        ids=list(s.scalars(select(BackgroundJob.id).where(BackgroundJob.idempotency_key.like(uid+'%'))))
        s.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_type=='background_job',OutboxEvent.aggregate_id.in_(ids)))
        s.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(ids)))
        s.execute(delete(Department).where(Department.name.like(uid+'%')))
        s.commit()
    engine.dispose()

def enqueue(jobs):
    service,uows,clock,uid=jobs
    with uows() as uow:
        job_id=service.enqueue(uow,JobSpec('system.verify','system',1,uid,{}))
        uow.commit()
    return job_id

def effect(uid):
    def handler(uow,job):
        row=Department(name=uid)
        uow.session.add(row);uow.session.flush()
        return ResultRef('department',row.id,201)
    return handler

def test_redis_down_keeps_outbox(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    def unavailable(job_id): raise ConnectionError('broker unavailable')
    report=OutboxDispatcher(uows,unavailable,clock).dispatch_due(10)
    assert report.failed==1
    with uows() as uow:
        row=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.aggregate_id==job_id,OutboxEvent.aggregate_type=='background_job'))
        assert row.state in {'pending','failed'}
        assert row.private_payload_ciphertext is None
    clock.instant+=timedelta(seconds=31)
    delivered=[]
    assert OutboxDispatcher(uows,delivered.append,clock).dispatch_due(10).sent==1
    assert delivered==[job_id]

def test_duplicate_delivery_single_effect(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    runner=JobRunner(service,{'system.verify':effect(uid)})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(runner.execute,job_id) for _ in range(2)]
        for future in futures: future.result(timeout=15)
    runner.execute(job_id)
    with uows() as uow:
        assert uow.session.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==1
        assert uow.session.get(BackgroundJob,job_id).state=='succeeded'

def test_expired_lease_recovered(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    old=service.claim(job_id,'worker-old')
    clock.instant+=timedelta(seconds=301)
    assert LeaseRecovery(uows,clock).requeue_expired(clock.now(),10)>=1
    new=service.claim(job_id,'worker-new')
    assert new is not None and new.lease_owner!=old.lease_owner
    with pytest.raises(DomainError) as error: service.complete(old,ResultRef('system',1,200))
    assert error.value.code=='STALE_JOB_LEASE'
    service.complete(new,ResultRef('system',1,200))

def test_outbox_commit_order(jobs):
    service,uows,clock,uid=jobs
    delivered=[]
    with uows() as uow:
        job_id=service.enqueue(uow,JobSpec('system.verify','system',1,uid,{}))
        assert OutboxDispatcher(uows,delivered.append,clock).dispatch_due(10).claimed==0
        assert delivered==[]
        uow.commit()
    assert OutboxDispatcher(uows,delivered.append,clock).dispatch_due(10).sent==1
    assert delivered==[job_id]

def test_unknown_job_type_rejected(jobs):
    service,uows,clock,uid=jobs
    with uows() as uow:
        with pytest.raises(DomainError) as error: service.enqueue(uow,JobSpec('arbitrary.python','system',1,uid,{}))
        assert error.value.http_status==422

def test_handler_failure_rolls_back_business_and_retries(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    def bad(uow,job):
        effect(uid)(uow,job)
        raise ValueError('sensitive exception details')
    JobRunner(service,{'system.verify':bad}).execute(job_id)
    with uows() as uow:
        row=uow.session.get(BackgroundJob,job_id)
        assert row.state=='retry'
        assert row.error_code=='HANDLER_FAILED'
        assert uow.session.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0

def test_expired_during_handler_cannot_commit(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    def slow(uow,job):
        result=effect(uid)(uow,job)
        clock.instant+=timedelta(seconds=301)
        return result
    JobRunner(service,{'system.verify':slow}).execute(job_id)
    with uows() as uow: assert uow.session.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0

def test_enqueue_duplicate_key_requires_identical_spec(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    with uows() as uow:
        assert service.enqueue(uow,JobSpec('system.verify','system',1,uid,{}))==job_id
        uow.commit()
    with uows() as uow:
        with pytest.raises(DomainError) as error: service.enqueue(uow,JobSpec('system.verify','system',2,uid,{}))
        assert error.value.http_status==409

def test_task_payload_contains_only_reference_ids(jobs):
    service,uows,clock,uid=jobs
    with uows() as uow:
        with pytest.raises(DomainError): service.enqueue(uow,JobSpec('system.verify','system',1,uid,{'password':'sensitive'}))


def test_job_enqueue_inside_idempotency_transaction(jobs):
    from hashlib import sha256
    from app.core.access import ActorContext
    from app.core.idempotency import IdempotencyService
    from app.core.models import IdempotencyRecord
    service,uows,clock,uid=jobs
    command_service=IdempotencyService(uows,clock)
    def command(uow):
        job_id=service.enqueue(uow,JobSpec('system.verify','system',1,uid,{}))
        return ResultRef('background_job',job_id,202)
    result=command_service.execute(ActorContext('system'),uid,'key',sha256(b'a').hexdigest(),command)
    with uows() as uow:
        assert uow.session.get(BackgroundJob,result.entity_id).state=='queued'
        uow.session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.operation==uid))
        uow.commit()

def test_scheduler_allows_only_one_instance(jobs):
    from app.runtime.scheduler import SchedulerLease
    service,uows,clock,uid=jobs
    with uows() as uow:
        engine=uow.session.get_bind()
        with SchedulerLease(engine,name=uid) as lease:
            lease.check()
            with pytest.raises(RuntimeError,match='already active'):
                with SchedulerLease(engine,name=uid): pass
        with SchedulerLease(engine,name=uid) as second: second.check()


@pytest.fixture
def scoped_jobs(jobs):
    from app.identity.models import User
    from app.jobs.models import Job
    from app.talents.models import Candidate
    from app.recruitment.models import Application
    service,uows,clock,uid=jobs
    with uows() as uow:
        d1=Department(name=uid+'-scope-a');d2=Department(name=uid+'-scope-b')
        uow.session.add_all([d1,d2]);uow.session.flush()
        owner=User(login_name=uid,password_hash='synthetic-not-login',department_id=d1.id)
        candidate=Candidate(display_name=uid)
        uow.session.add_all([owner,candidate]);uow.session.flush()
        job=Job(department_id=d1.id,owner_hr_id=owner.id,title=uid,headcount=1)
        uow.session.add(job);uow.session.flush()
        application=Application(candidate_id=candidate.id,job_id=job.id,source='import',stage='evaluating',relationship_state='active')
        uow.session.add(application);uow.session.flush()
        private=service.enqueue(uow,JobSpec('application.evaluate','application',application.id,uid+'-private',{}))
        shared=service.enqueue(uow,JobSpec('profile.build','candidate',candidate.id,uid+'-shared',{}))
        ids=(d1.id,d2.id,owner.id,candidate.id,job.id,application.id)
        uow.commit()
    yield private,shared,ids
    with uows() as uow:
        for model,row_id in [(Application,ids[5]),(Job,ids[4]),(Candidate,ids[3]),(User,ids[2])]:
            uow.session.execute(delete(model).where(model.id==row_id))
        uow.session.execute(delete(Department).where(Department.id.in_(ids[:2])))
        uow.commit()

def test_task_queries_enforce_department_and_omit_internal_payload(jobs,scoped_jobs):
    from app.core.access import ActorContext
    from app.runtime.queries import RuntimeQueries
    service,uows,clock,uid=jobs
    private,shared,ids=scoped_jobs
    own=ActorContext('hr',user_id=ids[2],department_ids=frozenset({ids[0]}),permissions=frozenset({'evaluation.read','talent.read'}))
    other=ActorContext('hr',user_id=ids[2],department_ids=frozenset({ids[1]}),permissions=own.permissions)
    query=RuntimeQueries(uows)
    view=query.task(own,private)
    assert view.state=='queued'
    assert view.progress=={'stage':'queued'}
    assert 'input_refs' not in view.model_dump() and 'idempotency_key' not in view.model_dump()
    with pytest.raises(DomainError) as error: query.task(other,private)
    assert error.value.http_status==404
    assert query.task(other,shared).id==str(shared)

def test_business_task_endpoint_does_not_grant_admin_hr_data(jobs,scoped_jobs):
    from app.core.access import ActorContext
    from app.runtime.queries import RuntimeQueries
    service,uows,clock,uid=jobs
    private,shared,ids=scoped_jobs
    actor=ActorContext('admin',user_id=ids[2],permissions=frozenset({'runtime.read'}))
    with pytest.raises(DomainError) as error: RuntimeQueries(uows).task(actor,private)
    assert error.value.http_status==403

def test_recovery_limit_does_not_starve_expired_jobs_behind_pending_queue(jobs):
    service,uows,clock,uid=jobs
    enqueue(jobs)
    with uows() as uow:
        second=service.enqueue(uow,JobSpec('system.verify','system',1,uid+'-second',{}));uow.commit()
    service.claim(second,'old-worker')
    clock.instant+=timedelta(seconds=301)
    assert LeaseRecovery(uows,clock).requeue_expired(clock.now(),1)==1
    with uows() as uow: assert uow.session.get(BackgroundJob,second).state=='queued'


def test_retry_budget_is_finite_and_not_recovered_again(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    def bad(uow,job): raise RuntimeError('do not store this exception')
    runner=JobRunner(service,{'system.verify':bad})
    for attempt in range(3):
        runner.execute(job_id)
        clock.instant+=timedelta(seconds=61)
        LeaseRecovery(uows,clock).requeue_expired(clock.now(),10)
    with uows() as uow:
        job=uow.session.get(BackgroundJob,job_id)
        assert job.state=='failed' and job.attempt_count==3
    assert service.claim(job_id,'extra') is None

def test_broker_loss_after_sent_is_redispatched_and_remains_single_effect(jobs):
    service,uows,clock,uid=jobs
    job_id=enqueue(jobs)
    delivered=[]
    assert OutboxDispatcher(uows,delivered.append,clock).dispatch_due(10).sent==1
    with uows() as uow:
        event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key==f'dispatch:{job_id}:0'))
        event.updated_at=clock.now().replace(tzinfo=None)-timedelta(seconds=61)
        uow.commit()
    assert LeaseRecovery(uows,clock).requeue_expired(clock.now(),10)==1
    assert OutboxDispatcher(uows,delivered.append,clock).dispatch_due(10).sent==1
    assert delivered==[job_id,job_id]
    runner=JobRunner(service,{'system.verify':effect(uid)})
    for message in delivered: runner.execute(message)
    with uows() as uow:
        assert uow.session.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==1
