"""Local diagnostic: actual DB outbox -> Redis -> Celery -> DB completion."""
import json
import sys
import time
from uuid import uuid4
from sqlalchemy import select,delete
from app.core.settings import Settings
from app.core.uow import make_uow
from app.runtime.job_service import BackgroundJobService,JobSpec
from app.runtime.models import BackgroundJob,OutboxEvent

def main():
    if Settings.load().environment!='dev': raise RuntimeError('Local diagnostic only')
    key='local-queue-probe:'+uuid4().hex
    with make_uow() as uow:
        job_id=BackgroundJobService().enqueue(uow,JobSpec('system.verify','system',1,key,{}))
        uow.commit()
    states=[]
    deadline=time.monotonic()+45
    passed=False
    while time.monotonic()<deadline:
        with make_uow() as uow:
            job=uow.session.get(BackgroundJob,job_id)
            outbox=uow.session.scalar(select(OutboxEvent).where(OutboxEvent.event_key==f'dispatch:{job_id}:0'))
            states.append({'job':job.state,'outbox':outbox.state})
            passed=job.state=='succeeded' and outbox.state=='sent' and job.attempt_count==1
            if passed or job.state=='failed': break
        time.sleep(1)
    print(json.dumps({'ready':passed,'job_id':str(job_id),'observed':states,'business_module_implemented':False}))
    if passed:
        with make_uow() as uow:
            uow.session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_type=='background_job',OutboxEvent.aggregate_id==job_id))
            uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id==job_id))
            uow.commit()
    return 0 if passed else 1

if __name__=='__main__': raise SystemExit(main())
