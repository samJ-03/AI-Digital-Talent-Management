"""持久后台任务与Outbox：事务外投递已提交事件，仅向队列传递任务ID。"""
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import select,or_,and_,update
from app.core.clock import Clock
from app.core.uow import make_uow
from app.runtime.job_service import utc_naive
from app.runtime.models import OutboxEvent

@dataclass(frozen=True,slots=True)
class DispatchReport:
    """DispatchReport：持久后台任务与Outbox中的协作类型。"""
    claimed: int
    sent: int
    failed: int

class OutboxDispatcher:
    """OutboxDispatcher：持久后台任务与Outbox中的协作类型。"""
    def __init__(self,uow_factory=make_uow,publisher=None,clock: Clock|None=None):
        self.uow_factory=uow_factory;self.publisher=publisher;self.clock=clock or Clock()

    def dispatch_due(self,limit: int) -> DispatchReport:
        """投递已到期且尚未确认交付的Outbox事件。"""
        if not 1<=limit<=1000: raise ValueError('Dispatch limit must be 1..1000')
        now=utc_naive(self.clock.now())
        claimed=[]
        with self.uow_factory() as uow:
            rows=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='job.dispatch',or_(
                and_(OutboxEvent.state.in_(['pending','failed']),or_(OutboxEvent.next_attempt_at.is_(None),OutboxEvent.next_attempt_at<=now)),
                and_(OutboxEvent.state=='processing',OutboxEvent.lease_until<=now))).order_by(OutboxEvent.id).limit(limit).with_for_update(skip_locked=True)))
            for row in rows:
                row.state='processing';row.lease_until=now+timedelta(seconds=60)
            uow.session.flush()
            for row in rows: claimed.append((row.id,row.row_version,row.aggregate_type,row.aggregate_id,row.payload_refs,row.private_payload_ciphertext is not None))
            uow.commit()
        sent=failed=0
        for event_id,version,aggregate_type,aggregate_id,refs,private in claimed:
            valid=aggregate_type=='background_job' and isinstance(refs,dict) and refs=={'job_id':aggregate_id} and type(aggregate_id) is int and aggregate_id>0 and not private
            state='cancelled'
            if valid:
                try:
                    if self.publisher is None: raise RuntimeError('Publisher is not configured')
                    self.publisher(aggregate_id)
                    state='sent'
                except Exception:
                    state='failed'
            if state=='sent': sent+=1
            else: failed+=1
            with self.uow_factory() as uow:
                uow.session.execute(update(OutboxEvent).where(OutboxEvent.id==event_id,OutboxEvent.row_version==version,OutboxEvent.state=='processing').values(
                    state=state,lease_until=None,next_attempt_at=now+timedelta(seconds=30) if state=='failed' else None,row_version=version+1))
                uow.commit()
        return DispatchReport(len(claimed),sent,failed)
