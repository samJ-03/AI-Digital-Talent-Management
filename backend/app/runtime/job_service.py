"""持久后台任务与Outbox：管理任务入队、租约、重试和终态转换。"""
from __future__ import annotations
from dataclasses import dataclass
from contextlib import nullcontext
from datetime import datetime,timedelta,timezone
import re
from typing import Callable
from uuid import uuid4
from sqlalchemy import select,event
from sqlalchemy.exc import IntegrityError
from app.core.clock import Clock
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.core.uow import SqlAlchemyUow,make_uow
from app.runtime.models import BackgroundJob,OutboxEvent

JOB_TYPES=frozenset({'system.verify','resume.parse','profile.build','application.evaluate','profile.index','exam.grade','notification.send','mail.test','question.generate','knowledge.index'})
ENTITY_TYPES=frozenset({'system','candidate','resume_version','candidate_profile','import_batch','import_item','application','exam_attempt','notification','mail_config','knowledge_document','question_bank','paper_version'})
REF_IDS=frozenset({'candidate_id','resume_version_id','profile_id','job_id','job_version_id','evaluation_id','attempt_id','notification_id','mail_config_id','model_config_id','prompt_version_id','file_id','document_id','bank_id','paper_version_id','import_item_id','batch_id'})
REF_REVISIONS=frozenset({'submission_revision','parser_revision','profile_revision','embedding_revision','review_revision'})

@dataclass(frozen=True,slots=True)
class TerminalJobFailure:
    """TerminalJobFailure：持久后台任务与Outbox中的协作类型。"""
    error_code: str

@dataclass(frozen=True,slots=True)
class JobSpec:
    """JobSpec：持久后台任务与Outbox中的协作类型。"""
    job_type: str
    entity_type: str
    entity_id: int
    idempotency_key: str
    input_refs: dict

@dataclass(frozen=True,slots=True)
class JobLease:
    """JobLease：持久后台任务与Outbox中的协作类型。"""
    job_id: int
    lease_owner: str
    lease_until: datetime

def utc_naive(value: datetime) -> datetime:
    """把时间规范化为数据库使用的无时区UTC值。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('UTC operation requires an aware datetime')
    return value.astimezone(timezone.utc).replace(tzinfo=None)

def add_dispatch(session,job: BackgroundJob,now: datetime) -> None:
    """在当前事务追加队列交付所需的Outbox记录。"""
    key=f'dispatch:{job.id}:{job.attempt_count}'
    existing=session.scalar(select(OutboxEvent).where(OutboxEvent.event_key==key).with_for_update())
    if existing is None:
        session.add(OutboxEvent(event_type='job.dispatch',aggregate_type='background_job',aggregate_id=job.id,
            event_key=key,payload_refs={'job_id':job.id},state='pending',next_attempt_at=now))
    elif existing.state in {'sent','failed','cancelled'}:
        existing.state='pending';existing.next_attempt_at=now;existing.lease_until=None

class BackgroundJobService:
    """BackgroundJobService：持久后台任务与Outbox中的协作类型。"""
    MAX_ATTEMPTS=3
    LEASE_SECONDS=300
    def __init__(self,uow_factory=make_uow,clock: Clock|None=None):
        self.uow_factory=uow_factory
        self.clock=clock or Clock()

    def enqueue(self,uow: SqlAlchemyUow,spec: JobSpec) -> int:
        """在业务同一事务保存持久任务及交付事件。 uow属于当前调用方事务，回调不得提交外层事务。"""
        if spec.job_type not in JOB_TYPES or spec.entity_type not in ENTITY_TYPES:
            raise DomainError('INVALID_JOB_TYPE',422,'任务类型或关联类型无效')
        if type(spec.entity_id) is not int or spec.entity_id<=0 or not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,190}',spec.idempotency_key):
            raise DomainError('INVALID_JOB_SPEC',422,'任务参数无效')
        if not isinstance(spec.input_refs,dict) or len(spec.input_refs)>30:
            raise DomainError('INVALID_JOB_REFS',422,'任务只允许引用参数')
        for key,value in spec.input_refs.items():
            valid=False
            if key in REF_IDS:
                valid=type(value) is int and value>0 or isinstance(value,str) and value.isascii() and value.isdigit() and 0<len(value)<=20 and int(value)>0
            elif key in REF_REVISIONS:
                valid=type(value) is int and value>=0 or isinstance(value,str) and bool(re.fullmatch(r'[a-zA-Z0-9_.-]{1,60}',value))
            elif key=='input_hash': valid=isinstance(value,str) and bool(re.fullmatch(r'[a-f0-9]{64}',value))
            if not valid: raise DomainError('INVALID_JOB_REFS',422,'任务只允许引用参数')
        now=utc_naive(self.clock.now())
        job=BackgroundJob(job_type=spec.job_type,entity_type=spec.entity_type,entity_id=spec.entity_id,
            idempotency_key=spec.idempotency_key,input_refs=dict(spec.input_refs),state='queued',attempt_count=0,next_run_at=now)
        try:
            with uow.savepoint():
                uow.session.add(job);uow.session.flush()
        except IntegrityError as error:
            if error.orig.args[0]!=1062: raise
            existing=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.idempotency_key==spec.idempotency_key).with_for_update())
            if existing is None: raise RuntimeError('Task unique record unavailable') from None
            if (existing.job_type,existing.entity_type,existing.entity_id,existing.input_refs)!=(spec.job_type,spec.entity_type,spec.entity_id,spec.input_refs):
                raise DomainError('JOB_KEY_CONFLICT',409,'任务键对应不同输入')
            return existing.id
        add_dispatch(uow.session,job,now)
        return job.id

    def claim(self,job_id: int,worker_id: str) -> JobLease|None:
        """原子领取任务租约，拒绝重复或已失效的执行权。"""
        if not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,60}',worker_id):
            raise ValueError('Invalid worker identifier')
        now=utc_naive(self.clock.now())
        with self.uow_factory() as uow:
            job=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.id==job_id).with_for_update())
            if job is None or job.state not in {'queued','retry'} or job.next_run_at and job.next_run_at>now:
                return None
            if job.job_type not in JOB_TYPES:
                job.state='failed';job.error_code='UNKNOWN_JOB_TYPE';uow.commit();return None
            if job.attempt_count>=self.MAX_ATTEMPTS:
                job.state='failed';job.error_code='ATTEMPT_LIMIT';uow.commit();return None
            job.state='running';job.attempt_count+=1
            job.lease_owner=worker_id+':'+uuid4().hex
            job.lease_until=now+timedelta(seconds=self.LEASE_SECONDS)
            job.error_code=None
            lease=JobLease(job.id,job.lease_owner,job.lease_until.replace(tzinfo=timezone.utc))
            uow.commit()
            return lease

    def _owned(self,uow,lease):
        job=uow.session.scalar(select(BackgroundJob).where(BackgroundJob.id==lease.job_id).with_for_update())
        if (job is None or job.state!='running' or job.lease_owner!=lease.lease_owner
            or job.lease_until!=utc_naive(lease.lease_until) or job.lease_until<=utc_naive(self.clock.now())):
            raise DomainError('STALE_JOB_LEASE',409,'任务租约已失效')
        return job

    def _success(self,job,result):
        if not isinstance(result,(ResultRef,TerminalJobFailure)): raise TypeError('Handler must return a result reference or terminal failure')
        if job.lease_until<=utc_naive(self.clock.now()):
            raise DomainError('STALE_JOB_LEASE',409,'任务租约已失效')
        failure=isinstance(result,TerminalJobFailure)
        safe={'SMTP_DELIVERY_UNKNOWN','SMTP_TEST_FAILED','MAIL_CONFIG_DISABLED','MAIL_TEST_EXPIRED','INVALID_OUTPUT','DEPENDENCY_UNAVAILABLE'}
        job.state='failed' if failure else 'succeeded'
        job.error_code=result.error_code if failure and result.error_code in safe else ('HANDLER_FAILED' if failure else None)
        job.lease_owner=None;job.lease_until=None;job.next_run_at=None

    def complete(self,lease: JobLease,result: ResultRef) -> None:
        """在有效租约下完成任务并保存结果引用。"""
        with self.uow_factory() as uow:
            job=self._owned(uow,lease)
            self._success(job,result)
            uow.commit()

    def run_atomic(self,lease: JobLease,handler: Callable) -> None:
        """校验有效租约并在同一事务执行领域回调与任务完成。"""
        with self.uow_factory() as uow:
            job=self._owned(uow,lease)
            transaction=uow.session.get_transaction()
            def forbid_commit(session):
                approved=session.info.get('approved_savepoint')
                if approved is not None and session.get_nested_transaction() is approved: return
                raise RuntimeError('job callback cannot commit')
            event.listen(uow.session,'before_commit',forbid_commit)
            try:
                result=handler(uow,job)
                if uow.session.get_transaction() is not transaction:
                    raise RuntimeError('job callback cannot end transaction')
            finally:
                event.remove(uow.session,'before_commit',forbid_commit)
            self._success(job,result)
            uow.commit()

    def fail(self,lease: JobLease,error_code: str,retryable: bool=True) -> None:
        """在有效租约下记录脱敏错误并决定重试或失败终态。"""
        if error_code not in {'HANDLER_FAILED','HANDLER_NOT_REGISTERED','DEPENDENCY_UNAVAILABLE','INVALID_OUTPUT'}:
            error_code='HANDLER_FAILED'
        with self.uow_factory() as uow:
            job=self._owned(uow,lease)
            job.state='retry' if retryable and job.attempt_count<self.MAX_ATTEMPTS else 'failed'
            job.error_code=error_code;job.lease_owner=None;job.lease_until=None
            job.next_run_at=utc_naive(self.clock.now())+timedelta(seconds=15*2**(job.attempt_count-1)) if job.state=='retry' else None
            uow.commit()

class JobRunner:
    """JobRunner：持久后台任务与Outbox中的协作类型。"""
    def __init__(self,service: BackgroundJobService,handlers: dict[str,Callable]):
        self.service=service;self.handlers=dict(handlers)

    def execute(self,job_id: int) -> None:
        """执行受控操作；具体事务与幂等边界由当前服务定义。"""
        lease=self.service.claim(job_id,'worker')
        if lease is None: return
        with self.service.uow_factory() as uow:
            job=uow.session.get(BackgroundJob,job_id)
            handler=self.handlers.get(job.job_type)
        if handler is None:
            self.service.fail(lease,'HANDLER_NOT_REGISTERED',False)
            return
        try:
            callback=handler.prepare(lease) if hasattr(handler,'prepare') else handler
            # Identity serialization must include the outer commit, not just callback execution.
            with handler.finalization_context() if hasattr(handler,'finalization_context') else nullcontext():
                self.service.run_atomic(lease,callback)
        except Exception:
            # Never persist exception messages, raw model output, credentials or source material.
            try: self.service.fail(lease,'HANDLER_FAILED')
            except DomainError as error:
                if error.code!='STALE_JOB_LEASE': raise
