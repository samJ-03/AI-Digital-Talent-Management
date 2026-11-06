"""平台开发工具：验证runtime http的正常与失败场景；测试数据仅用于隔离环境。"""
from uuid import uuid4
from sqlalchemy import delete
from tests.integration.test_identity import identity,login
from app.runtime.job_service import BackgroundJobService,JobSpec
from app.runtime.models import BackgroundJob,OutboxEvent
from app.talents.models import Candidate

def test_task_http_authentication_and_safe_contract(identity):
    client,engine,uid,password,ids,*_=identity
    runtime=client.app.state.identity
    with runtime.uow_factory() as uow:
        row=Candidate(display_name='synthetic-'+uid)
        uow.session.add(row);uow.session.flush()
        candidate_id=row.id
        task_id=BackgroundJobService().enqueue(uow,JobSpec('profile.build','candidate',candidate_id,'http-probe:'+uuid4().hex,{}))
        uow.commit()
    try:
        path='/api/v1/tasks/'+str(task_id)
        assert client.get(path).status_code==401
        login(identity,'hr')
        result=client.get(path)
        assert result.status_code==200,result.text
        assert result.headers['Cache-Control']=='no-store'
        data=result.json()['data']
        assert data['id']==str(task_id) and data['progress']=={'stage':'queued'}
        assert set(data)=={'id','entity_type','entity_id','state','progress','error_code','retryable'}
        assert client.get('/api/v1/tasks/0').status_code==422
        login(identity,'admin')
        assert client.get(path).status_code==403
    finally:
        with runtime.uow_factory() as uow:
            uow.session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_type=='background_job',OutboxEvent.aggregate_id==task_id))
            uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id==task_id))
            uow.session.execute(delete(Candidate).where(Candidate.id==candidate_id))
            uow.commit()
