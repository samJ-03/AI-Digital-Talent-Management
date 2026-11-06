"""平台开发工具：验证schema contract的正常与失败场景；测试数据仅用于隔离环境。"""
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DBAPIError
from app.models import TABLE_MODELS, register_models
from app.core.uow import SqlAlchemyUow
from tests.factories import make_row

EXPECTED_TABLES=set(["departments","users","roles","user_roles","stored_files","jobs","job_versions","import_batches","import_items","candidates","resume_versions","candidate_profiles","duplicate_cases","applications","evaluation_runs","screening_details","match_results","recruitment_events","question_banks","questions","papers","paper_versions","paper_items","exam_attempts","exam_answers","score_reviews","notifications","knowledge_documents","knowledge_chunks","model_configs","prompt_versions","workflow_configs","background_jobs","outbox_events","ai_runs","index_records","audit_logs","score_reports","idempotency_records","mail_configs"])

@pytest.fixture(scope='module')
def db_engine():
    url=os.environ.get('TALENT_TEST_DATABASE_URL','')
    assert url and make_url(url).database == 'talent_test', 'Only isolated talent_test is allowed'
    config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    config.set_main_option('sqlalchemy.url',url.replace('%','%%'))
    command.upgrade(config,'head')
    engine=create_engine(url,pool_pre_ping=True)
    yield engine
    engine.dispose()

@pytest.fixture
def session(db_engine):
    with Session(db_engine) as s:
        yield s
        s.rollback()

def test_all_40_tables_present(db_engine):
    actual=set(inspect(db_engine).get_table_names())-{'alembic_version'}
    assert actual == EXPECTED_TABLES
    assert set(register_models().tables) == EXPECTED_TABLES

def test_initial_answer_revision_zero(session):
    answer=make_row(session,'exam_answers')
    assert answer.answer_revision == 0

def test_attempt_round_unique(session):
    first=make_row(session,'exam_attempts',round_no=1)
    with pytest.raises(IntegrityError):
        make_row(session,'exam_attempts',application_id=first.application_id,round_no=1)

def test_application_candidate_job_unique(session):
    first=make_row(session,'applications')
    with pytest.raises(IntegrityError):
        make_row(session,'applications',candidate_id=first.candidate_id,job_id=first.job_id)

def test_current_pointers_nullable_then_fk(db_engine):
    inspector=inspect(db_engine)
    for table,column in [('jobs','current_version_id'),('candidates','current_resume_version_id'),('candidates','current_profile_id'),('applications','current_evaluation_id'),('exam_attempts','current_score_report_id')]:
        columns={c['name']:c for c in inspector.get_columns(table)}
        assert columns[column]['nullable'] is True
        assert any(column in fk['constrained_columns'] for fk in inspector.get_foreign_keys(table))

def test_uow_rollback_without_commit(db_engine):
    model=TABLE_MODELS.get('departments')
    assert model is not None
    name='rollback-'+uuid4().hex[:12]
    with SqlAlchemyUow(lambda: Session(db_engine)) as uow:
        row=make_row(uow.session,'departments',name=name)
        row_id=row.id
    with Session(db_engine) as check:
        assert check.get(model,row_id) is None

def test_uow_explicit_commit_persists(db_engine):
    model=TABLE_MODELS.get('departments')
    assert model is not None
    with SqlAlchemyUow(lambda: Session(db_engine)) as uow:
        row=make_row(uow.session,'departments')
        row_id=row.id
        uow.commit()
    with Session(db_engine) as check:
        assert check.get(model,row_id) is not None

def test_migration_roundtrip(db_engine):
    url=os.environ['TALENT_TEST_DATABASE_URL']
    config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    config.set_main_option('sqlalchemy.url',url.replace('%','%%'))
    command.downgrade(config,'base')
    assert set(inspect(db_engine).get_table_names()) <= {'alembic_version'}
    command.upgrade(config,'head')
    assert set(inspect(db_engine).get_table_names())-{'alembic_version'} == EXPECTED_TABLES

def test_uow_closes_connections(db_engine):
    before=db_engine.pool.checkedout()
    uow=SqlAlchemyUow(lambda: Session(db_engine))
    with uow:
        make_row(uow.session,'departments')
    assert db_engine.pool.checkedout() == before

def test_invalid_state_rejected(session):
    with pytest.raises(DBAPIError) as error:
        make_row(session,'jobs',status='invalid-state')
    assert error.value.orig.args[0] == 3819

def test_uow_exception_propagates_without_persistence(db_engine):
    model=TABLE_MODELS['departments']
    before=db_engine.pool.checkedout()
    row_id=None
    with pytest.raises(RuntimeError,match='cancel command'):
        with SqlAlchemyUow(lambda: Session(db_engine)) as uow:
            row=make_row(uow.session,'departments')
            row_id=row.id
            raise RuntimeError('cancel command')
    assert db_engine.pool.checkedout()==before
    with Session(db_engine) as check:
        assert check.get(model,row_id) is None

def test_stale_entity_update_rejected(db_engine):
    from sqlalchemy.orm.exc import StaleDataError
    model=TABLE_MODELS['departments']
    with Session(db_engine) as seed:
        row=make_row(seed,'departments')
        row_id=row.id
        seed.commit()
    with Session(db_engine) as first, Session(db_engine) as stale:
        a=first.get(model,row_id)
        b=stale.get(model,row_id)
        a.name='first-writer'
        first.commit()
        b.name='stale-writer'
        with pytest.raises(StaleDataError):
            stale.commit()
