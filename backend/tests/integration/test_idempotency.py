import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command as migration
from alembic.config import Config
from sqlalchemy import create_engine, select, delete, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from app.core.access import ActorContext, ResourceScope
from app.core.clock import FrozenClock
from app.core.errors import DomainError
from app.core.idempotency import IdempotencyService, ResultRef
from app.core.models import IdempotencyRecord
from app.core.uow import SqlAlchemyUow
from app.identity.models import Department
from app.audit.models import AuditLog
from app.audit.service import AuditService, AuditEvent

@pytest.fixture
def db():
    url=os.environ.get('TALENT_TEST_DATABASE_URL','')
    assert make_url(url).database=='talent_test'
    cfg=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    cfg.set_main_option('sqlalchemy.url',url.replace('%','%%'))
    migration.upgrade(cfg,'head')
    engine=create_engine(url,pool_pre_ping=True)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    uid=uuid4().hex
    actor=ActorContext('system',permissions=frozenset({'department.write'}))
    service=IdempotencyService(lambda:SqlAlchemyUow(factory),FrozenClock(datetime(2026,11,5,tzinfo=timezone.utc)))
    yield service,factory,actor,uid
    with factory() as s:
        s.execute(delete(AuditLog).where(AuditLog.action==uid))
        s.execute(delete(IdempotencyRecord).where(IdempotencyRecord.operation==uid))
        s.execute(delete(Department).where(Department.name.like(uid+'%')))
        s.commit()
    engine.dispose()

def digest(text): return hashlib.sha256(text.encode()).hexdigest()
def writer(uid):
    def command(uow):
        row=Department(name=uid,status='active')
        uow.session.add(row)
        uow.session.flush()
        return ResultRef('department',row.id,201)
    return command

def test_same_key_different_hash_409(db):
    svc,factory,actor,uid=db
    svc.execute(actor,uid,'key',digest('a'),writer(uid))
    with pytest.raises(DomainError) as e: svc.execute(actor,uid,'key',digest('b'),writer(uid))
    assert e.value.http_status==409

def test_replay_same_key_returns_same_result_without_command(db):
    svc,factory,actor,uid=db
    first=svc.execute(actor,uid,'key',digest('a'),writer(uid))
    def forbidden(uow): pytest.fail('replayed command ran')
    assert svc.execute(actor,uid,'key',digest('a'),forbidden)==first

def test_idempotency_and_business_commit_together(db):
    svc,factory,actor,uid=db
    def failing(uow):
        result=writer(uid)(uow)
        AuditService().append(uow,actor,AuditEvent(uid,ResourceScope('department',id=result.entity_id),{'changed_fields':['name']},'success',str(uuid4())))
        raise RuntimeError('business rejected')
    with pytest.raises(RuntimeError): svc.execute(actor,uid,'key',digest('a'),failing)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0
        assert s.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.operation==uid))==0
        assert s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action==uid))==0
    assert svc.execute(actor,uid,'key',digest('a'),writer(uid)).response_code==201

def test_audit_redacts_secrets(db):
    svc,factory,actor,uid=db
    def command(uow):
        result=writer(uid)(uow)
        AuditService().append(uow,actor,AuditEvent(uid,ResourceScope('department',id=result.entity_id),{'password':'hidden-password','nested':{'access_token':'hidden-token','answers':['hidden-answer']},'changed_fields':['status'],'reason':'Bearer abcdef1234567890'},'success',str(uuid4())))
        return result
    svc.execute(actor,uid,'key',digest('a'),command)
    with factory() as s:
        row=s.scalar(select(AuditLog).where(AuditLog.action==uid))
        text=json.dumps(row.change_summary)
        assert all(secret not in text for secret in ['hidden-password','hidden-token','hidden-answer','abcdef1234567890'])
        assert row.change_summary['changed_fields']==['status']

def test_concurrent_duplicate_only_one_business_effect(db):
    svc,factory,actor,uid=db
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(svc.execute,actor,uid,'key',digest('a'),writer(uid)) for _ in range(2)]
        results=[f.result(timeout=15) for f in futures]
    assert results[0]==results[1]
    with factory() as s: assert s.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==1

def test_callback_cannot_commit_early(db):
    svc,factory,actor,uid=db
    def bad(uow):
        result=writer(uid)(uow)
        uow.commit()
        raise RuntimeError('too late')
    with pytest.raises(RuntimeError,match='callback cannot commit'): svc.execute(actor,uid,'key',digest('a'),bad)
    with factory() as s: assert s.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0

def test_expired_key_starts_new_transaction(db):
    svc,factory,actor,uid=db
    first=svc.execute(actor,uid,'key',digest('a'),writer(uid))
    with factory() as s:
        row=s.scalar(select(IdempotencyRecord).where(IdempotencyRecord.operation==uid))
        row.expires_at=datetime(2026,11,4)
        s.commit()
    second=svc.execute(actor,uid,'key',digest('b'),writer(uid+'-next'))
    assert first.entity_id!=second.entity_id

def test_invalid_result_rolls_back(db):
    svc,factory,actor,uid=db
    def bad(uow): writer(uid)(uow); return {'arbitrary':'not a result reference'}
    with pytest.raises((ValueError,TypeError)): svc.execute(actor,uid,'key',digest('a'),bad)
    with factory() as s: assert s.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0


def test_direct_session_commit_is_also_blocked(db):
    svc,factory,actor,uid=db
    def bad(uow):
        result=writer(uid)(uow)
        uow.session.commit()
        return result
    with pytest.raises(RuntimeError,match='callback cannot commit'): svc.execute(actor,uid,'key',digest('a'),bad)
    with factory() as s: assert s.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0

def test_callback_rollback_cannot_produce_completed_record(db):
    svc,factory,actor,uid=db
    def bad(uow):
        result=writer(uid)(uow)
        uow.session.rollback()
        return result
    with pytest.raises(RuntimeError,match='callback cannot end'): svc.execute(actor,uid,'key',digest('a'),bad)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Department).where(Department.name==uid))==0
        assert s.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.operation==uid))==0

def test_same_key_is_isolated_per_actor(db):
    svc,factory,actor,uid=db
    first=svc.execute(ActorContext('hr',user_id=101),uid,'key',digest('a'),writer(uid))
    second=svc.execute(ActorContext('hr',user_id=102),uid,'key',digest('b'),writer(uid+'-other'))
    assert first.entity_id!=second.entity_id
