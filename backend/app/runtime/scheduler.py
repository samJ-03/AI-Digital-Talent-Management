from datetime import datetime,timedelta
import signal
import threading
from sqlalchemy import select,or_,and_,text,create_engine,exists,func
from app.core.clock import Clock
from app.core.settings import Settings
from app.core.uow import make_uow
from app.runtime.job_service import BackgroundJobService,utc_naive,add_dispatch
from app.runtime.models import BackgroundJob,OutboxEvent

class LeaseRecovery:
    def __init__(self,uow_factory=make_uow,clock: Clock|None=None):
        self.uow_factory=uow_factory;self.clock=clock or Clock()

    def requeue_expired(self,now: datetime,limit: int) -> int:
        if not 1<=limit<=1000: raise ValueError('Recovery limit must be 1..1000')
        now=utc_naive(now)
        recovered=0
        with self.uow_factory() as uow:
            blocked_queue_event=exists(select(OutboxEvent.id).where(
                OutboxEvent.event_key==func.concat('dispatch:',BackgroundJob.id,':',BackgroundJob.attempt_count),
                or_(OutboxEvent.state!='sent',OutboxEvent.updated_at>now-timedelta(seconds=60))))
            jobs=list(uow.session.scalars(select(BackgroundJob).where(or_(
                and_(BackgroundJob.state=='running',BackgroundJob.lease_until<=now),
                and_(BackgroundJob.state=='retry',BackgroundJob.next_run_at<=now),
                and_(BackgroundJob.state=='queued',~blocked_queue_event))).order_by(BackgroundJob.id).limit(limit).with_for_update(skip_locked=True)))
            for job in jobs:
                if job.state=='queued':
                    event=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key==f'dispatch:{job.id}:{job.attempt_count}').with_for_update())
                    if event is not None and (event.state!='sent' or event.updated_at>now-timedelta(seconds=60)):
                        continue
                if job.attempt_count>=BackgroundJobService.MAX_ATTEMPTS:
                    job.state='failed';job.error_code='ATTEMPT_LIMIT';job.lease_owner=None;job.lease_until=None;job.next_run_at=None
                    recovered+=1
                    continue
                job.state='queued';job.lease_owner=None;job.lease_until=None;job.next_run_at=now
                add_dispatch(uow.session,job,now)
                recovered+=1
            uow.commit()
        return recovered

class SchedulerLease:
    """MySQL connection-owned advisory lock; a second scheduler fails closed."""
    def __init__(self,engine,name='ai-talent:scheduler'):
        self.engine=engine;self.name=name;self.connection=None
    def __enter__(self):
        self.connection=self.engine.connect()
        if self.connection.scalar(text('SELECT GET_LOCK(:name,0)'),{'name':self.name})!=1:
            self.connection.close();self.connection=None
            raise RuntimeError('Another scheduler is already active')
        self.connection.commit()
        return self
    def check(self):
        if self.connection.scalar(text('SELECT IS_USED_LOCK(:name)=CONNECTION_ID()'),{'name':self.name})!=1:
            raise RuntimeError('Scheduler lease was lost')
        self.connection.commit()
    def __exit__(self,*args):
        if self.connection is not None:
            try:
                self.connection.execute(text('SELECT RELEASE_LOCK(:name)'),{'name':self.name});self.connection.commit()
            finally: self.connection.close()


def main():
    from app.runtime.outbox import OutboxDispatcher
    from app.runtime.worker import publish_job
    engine=create_engine(Settings.load().database_url.get_secret_value(),pool_pre_ping=True)
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:stop.set())
    try:
        with SchedulerLease(engine) as lease:
            while not stop.is_set():
                lease.check()
                LeaseRecovery().requeue_expired(Clock().now(),100)
                OutboxDispatcher(publisher=publish_job).dispatch_due(100)
                stop.wait(3)
    finally: engine.dispose()

if __name__=='__main__': main()
