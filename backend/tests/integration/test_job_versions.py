"""T12岗位版本、部门隔离、就绪门和事件原子性集成测试；仅talent_test。"""
from uuid import uuid4
from copy import deepcopy
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select,delete,func
import pytest
from tests.integration.test_identity import identity,login
from tests.integration.test_paper_versions import papers,prepare,approved_question,version_body,request
from app.jobs.models import Job,JobVersion
from app.identity.models import Role,UserRole
from app.ai_runtime.models import ModelConfig,PromptVersion,WorkflowConfig
from app.notifications.models import MailConfig
from app.runtime.models import OutboxEvent
from app.core.secrets import SecretCipher

@pytest.fixture
def jobs(papers):
    client,engine,uid,password,ids,*_=papers
    uows=client.app.state.identity.uow_factory
    with uows() as uow:
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==ids['hr']))
        role.permission_codes=sorted(set(role.permission_codes)|{'job.read','job.write','exam.invite'})
        snapshots={w.task_type:{key:getattr(w,key) for key in ['model_config_id','prompt_version_id','enabled','timeout_seconds','max_retries','config_revision']} for w in uow.session.scalars(select(WorkflowConfig))}
        uow.commit()
    yield papers
    with uows() as uow:
        owned=list(uow.session.scalars(select(Job).where(Job.title.like(uid+'%'))))
        job_ids=[j.id for j in owned]
        for row in owned: row.current_version_id=None
        uow.session.flush()
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_type=='job',OutboxEvent.aggregate_id.in_(job_ids)))
        uow.session.execute(delete(JobVersion).where(JobVersion.job_id.in_(job_ids)))
        uow.session.execute(delete(Job).where(Job.id.in_(job_ids)))
        for w in uow.session.scalars(select(WorkflowConfig)):
            for key,value in snapshots[w.task_type].items(): setattr(w,key,value)
        uow.session.flush()
        uow.session.execute(delete(ModelConfig).where(ModelConfig.logical_key.like(uid+'%')))
        uow.session.execute(delete(PromptVersion).where(PromptVersion.content.like(uid+'%')))
        uow.session.execute(delete(MailConfig).where(MailConfig.sender_address==uid+'@example.com'))
        uow.commit()

def body(paper_id=None):
    return {'description':'Python后端开发，负责接口和数据库',
        'conditions':[{'key':'degree','field':'education','operator':'gte','expected':'bachelor','required':True}],
        'match_weights':{'skills':50,'experience':35,'responsibilities':15},'invite_threshold':'75.00',
        'paper_version_id':paper_id,'invite_valid_hours':72,
        'mail_template':{'subject':'{job_title}测评邀请','body':'{candidate_name}，请访问{exam_url}，有效期{valid_until}。'}}

def create(jobs):
    client,engine,uid,password,ids,*_=jobs
    headers=login(jobs,'hr')
    data=request(client,headers,'/jobs',{'title':uid+'-backend','department_id':str(ids['d1']),'headcount':2})
    return client,headers,data

def current(jobs,job_id):
    with jobs[0].app.state.identity.uow_factory() as uow:
        row=uow.session.get(Job,int(job_id))
        return {'version':row.row_version,'status':row.status,'auto':row.auto_invite_enabled,'current':row.current_version_id}

def state(jobs,headers,job_id,action,status=200):
    return request(jobs[0],{**headers,'If-Match':str(current(jobs,job_id)['version'])},'/jobs/'+job_id+'/state',{'action':action,'reopen_reason':'synthetic lifecycle test'},status)

def published(jobs,paper_id=None):
    client,headers,job=create(jobs)
    draft=request(client,headers,'/jobs/'+job['id']+'/versions',body(paper_id))
    version=request(client,headers,'/job-versions/'+draft['id']+'/publish',{'reason':'HR reviewed standard'},200)
    state(jobs,headers,job['id'],'open')
    return client,headers,job,version

def ready(jobs):
    client,headers,bank,paper=prepare(jobs)
    q=approved_question(client,headers,bank['id'])
    draft=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(q['id']))
    pv=request(client,headers,'/paper-versions/'+draft['id']+'/publish',{'reason':'reviewed'},200)
    uows=client.app.state.identity.uow_factory
    key=Fernet.generate_key().decode();client.app.state.identity.settings.encryption_key=SecretStr(key)
    cipher=SecretCipher(key);client.app.state.ai_runtime.cipher=cipher;uid=jobs[2]
    with uows() as uow:
        llm=ModelConfig(logical_key=uid+'-llm',revision_no=1,provider_type='compatible_http',base_url='https://api.deepseek.com/v1',model_name='deepseek-flash',enabled=True,capabilities={'verified':True,'text':True,'json':True},secret_ciphertext=cipher.encrypt('synthetic-never-called'))
        emb=ModelConfig(logical_key=uid+'-embed',revision_no=1,provider_type='compatible_http',base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',model_name='text-embedding-v3',enabled=True,embedding_dimension=1024,capabilities={'verified':True,'embedding':True},secret_ciphertext=cipher.encrypt('synthetic-never-called'))
        uow.session.add_all([llm,emb]);uow.session.flush()
        for task in ['extract','profile','match','embedding','grade']:
            w=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type==task))
            w.model_config_id=emb.id if task=='embedding' else llm.id;w.enabled=True
            if task!='embedding':
                number=(uow.session.scalar(select(func.max(PromptVersion.revision_no)).where(PromptVersion.task_type==task)) or 0)+1
                p=PromptVersion(task_type=task,revision_no=number,content=uid+'-'+task,output_schema={'type':'object'},status='published')
                uow.session.add(p);uow.session.flush();w.prompt_version_id=p.id
        revision=(uow.session.scalar(select(func.max(MailConfig.revision_no))) or 0)+1
        uow.session.add(MailConfig(revision_no=revision,smtp_host='mailpit',smtp_port=1025,tls_mode='none',sender_address=uid+'@example.com',public_base_url='http://localhost:13000',state='active'))
        uow.commit()
    return published(jobs,pv['id'])

def enable(jobs,headers,job_id,enabled=True,status=200,version=None):
    return request(jobs[0],{**headers,'If-Match':str(version or current(jobs,job_id)['version'])},'/jobs/'+job_id+'/automation',{'enabled':enabled},status,'put')

def test_default_automation_off(jobs):
    client,headers,job=create(jobs)
    assert job['status']=='draft' and job['auto_invite_enabled'] is False
    assert job['current_version_id'] is None
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_type=='job',OutboxEvent.aggregate_id==int(job['id'])))==0

def test_weights_and_conditions_rejected_without_partial_version(jobs):
    client,headers,job=create(jobs)
    for mutate in ['weights','duplicate','type','template','age']:
        cmd=body()
        if mutate=='weights': cmd['match_weights']['skills']=49
        if mutate=='duplicate': cmd['conditions']*=2
        if mutate=='type': cmd['conditions'][0]['expected']=100
        if mutate=='template': cmd['mail_template']['body']='{candidate_name.__class__}'
        if mutate=='age': cmd['conditions'][0]['field']='age'
        request(client,headers,'/jobs/'+job['id']+'/versions',cmd,422)
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(JobVersion).where(JobVersion.job_id==int(job['id'])))==0

def test_published_version_immutable_and_metadata_cas(jobs):
    client,headers,job,version=published(jobs)
    edited=client.patch('/api/v1/job-versions/'+version['id'],json=body(),headers={**headers,'If-Match':str(version['version'])})
    assert edited.status_code==409
    stale=client.patch('/api/v1/jobs/'+job['id'],json={'title':jobs[2]+'-renamed'},headers={**headers,'If-Match':'1'})
    assert stale.status_code==409
    forbidden=client.patch('/api/v1/jobs/'+job['id'],json={'current_version_id':version['id']},headers={**headers,'If-Match':str(current(jobs,job['id'])['version'])})
    assert forbidden.status_code==422

def test_admin_and_other_department_denied(jobs):
    client,headers,job=create(jobs)
    for who,status_code in [('admin',403),('other',404)]:
        h=login(jobs,who)
        response=client.patch('/api/v1/jobs/'+job['id'],json={'title':'not allowed'},headers={**h,'If-Match':'1'})
        assert response.status_code==status_code

def test_missing_read_permission_rolls_back_before_create(jobs):
    client,engine,uid,password,ids,*_=jobs
    headers=login(jobs,'hr')
    with client.app.state.identity.uow_factory() as uow:
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==ids['hr']))
        role.permission_codes=[p for p in role.permission_codes if p!='job.read'];uow.commit()
    request(client,headers,'/jobs',{'title':uid+'-no-read','department_id':str(ids['d1']),'headcount':1},403)
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(Job).where(Job.title==uid+'-no-read'))==0

def test_required_before_enable_and_no_event(jobs):
    client,headers,job,version=published(jobs)
    response=client.put('/api/v1/jobs/'+job['id']+'/automation',json={'enabled':True},headers={**headers,'If-Match':str(current(jobs,job['id'])['version'])})
    assert response.status_code==409
    reasons=response.json()['data']['blocking_reasons']
    assert {'PAPER_NOT_PUBLISHED','MODEL_UNAVAILABLE','MAIL_NOT_VERIFIED'}<=set(reasons)
    assert current(jobs,job['id'])['auto'] is False

def test_current_version_owner_mismatch_blocks_open(jobs):
    client,headers,job=create(jobs)
    other=request(client,headers,'/jobs',{'title':jobs[2]+'-second','department_id':str(jobs[4]['d1']),'headcount':1})
    v=request(client,headers,'/jobs/'+other['id']+'/versions',body())
    v=request(client,headers,'/job-versions/'+v['id']+'/publish',{'reason':'reviewed'},200)
    with client.app.state.identity.uow_factory() as uow:
        uow.session.get(Job,int(job['id'])).current_version_id=int(v['id']);uow.commit()
    response=client.post('/api/v1/jobs/'+job['id']+'/state',json={'action':'open','reason':'reviewed'},headers={**headers,'If-Match':str(current(jobs,job['id'])['version']),'Idempotency-Key':uuid4().hex})
    assert response.status_code==409 and response.json()['code']=='CURRENT_VERSION_MISMATCH'

def test_enable_once_pause_reopen_and_publish_reset(jobs):
    client,headers,job,version=ready(jobs)
    result=enable(jobs,headers,job['id'])
    assert result['readiness']['ready'] is True and result['job']['auto_invite_enabled'] is True
    enable(jobs,headers,job['id'])
    with client.app.state.identity.uow_factory() as uow:
        events=list(uow.session.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='invite.scan',OutboxEvent.aggregate_id==int(job['id']))))
        assert len(events)==1 and events[0].state=='pending'
        assert events[0].payload_refs['job_version_id']==int(version['id'])
    state(jobs,headers,job['id'],'pause');state(jobs,headers,job['id'],'open')
    assert current(jobs,job['id'])['auto'] is False
    enable(jobs,headers,job['id'])
    draft=request(client,headers,'/jobs/'+job['id']+'/versions',body(version['paper_version_id']))
    request(client,headers,'/job-versions/'+draft['id']+'/publish',{'reason':'updated standard'},200)
    assert current(jobs,job['id'])['auto'] is False

def test_disabled_model_blocks_enable(jobs):
    client,headers,job,version=ready(jobs)
    with client.app.state.identity.uow_factory() as uow:
        model=uow.session.scalar(select(ModelConfig).where(ModelConfig.logical_key==jobs[2]+'-llm'));model.enabled=False;uow.commit()
    result=client.put('/api/v1/jobs/'+job['id']+'/automation',json={'enabled':True},headers={**headers,'If-Match':str(current(jobs,job['id'])['version'])})
    assert result.status_code==409 and 'MODEL_UNAVAILABLE' in result.json()['data']['blocking_reasons']

def test_create_idempotency_replay_and_conflict(jobs):
    client,engine,uid,password,ids,*_=jobs
    headers={**login(jobs,'hr'),'Idempotency-Key':uuid4().hex}
    cmd={'title':uid+'-idempotent','department_id':str(ids['d1']),'headcount':1}
    a=client.post('/api/v1/jobs',json=cmd,headers=headers);b=client.post('/api/v1/jobs',json=cmd,headers=headers)
    assert a.status_code==b.status_code==201 and a.json()['data']['id']==b.json()['data']['id']
    c=client.post('/api/v1/jobs',json={**cmd,'headcount':2},headers=headers)
    assert c.status_code==409

@pytest.mark.parametrize('kind',['mail','model'])
def test_config_disabled_after_authorization_snapshot_blocks_enable(jobs,monkeypatch,kind):
    """锁前并发停用必须使用当前读，不能回到权限查询建立的旧快照。"""
    import app.jobs.service as module
    client,headers,job,_=ready(jobs)
    original=module.lock_dependencies
    def disable_before_lock(session):
        with client.app.state.identity.uow_factory() as uow:
            if kind=='mail':
                row=uow.session.scalar(select(MailConfig).where(MailConfig.sender_address==jobs[2]+'@example.com'));row.state='disabled'
            else:
                row=uow.session.scalar(select(ModelConfig).where(ModelConfig.logical_key==jobs[2]+'-llm'));row.enabled=False
            uow.commit()
        snapshot=original(session)
        import gc;gc.collect()
        return snapshot
    monkeypatch.setattr(module,'lock_dependencies',disable_before_lock)
    result=client.put('/api/v1/jobs/'+job['id']+'/automation',json={'enabled':True},headers={**headers,'If-Match':str(current(jobs,job['id'])['version'])})
    assert result.status_code==409
    assert ('MAIL_NOT_VERIFIED' if kind=='mail' else 'MODEL_UNAVAILABLE') in result.json()['data']['blocking_reasons']
    assert current(jobs,job['id'])['auto'] is False

def test_concurrent_drafts_allocate_current_version_numbers(jobs,monkeypatch):
    """两次授权快照先建立，再争岗位锁，草稿序号仍须连续且不丢一个请求。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.jobs.service import JobService
    from app.jobs.schemas import JobVersionDraft
    from app.identity.models import User
    from app.identity.views import resolve_user
    client,headers,job=create(jobs);uows=client.app.state.identity.uow_factory
    with uows() as uow: actor=resolve_user(uow.session,uow.session.get(User,jobs[4]['hr']))
    original=JobService._job;barrier=Barrier(2)
    def synchronize(self,uow,job_id,expected_version=None):
        barrier.wait(timeout=10)
        return original(self,uow,job_id,expected_version)
    monkeypatch.setattr(JobService,'_job',synchronize)
    def draft(_):
        from app.core.errors import DomainError
        try: return JobService(uows,uuid4().hex,client.app.state.identity.settings).draft(actor,int(job['id']),JobVersionDraft.model_validate(body())).version_no
        except DomainError as exc: return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(draft,range(2)))
    assert set(result)=={1,2}

def test_enable_event_rolls_back_with_audit_failure(jobs,monkeypatch):
    """开关和事件先写入再遇审计失败，三者必须整体回滚。"""
    from app.jobs.service import JobService
    from app.core.errors import DomainError
    client,headers,job,_=ready(jobs)
    original=JobService.audit
    def fail(self,uow,actor,action,*args):
        if action=='job.automation': raise DomainError('SYNTHETIC_ABORT',409,'synthetic abort')
        return original(self,uow,actor,action,*args)
    monkeypatch.setattr(JobService,'audit',fail)
    result=client.put('/api/v1/jobs/'+job['id']+'/automation',json={'enabled':True},headers={**headers,'If-Match':str(current(jobs,job['id'])['version'])})
    assert result.status_code==409 and result.json()['code']=='SYNTHETIC_ABORT'
    assert current(jobs,job['id'])['auto'] is False
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type=='invite.scan',OutboxEvent.aggregate_id==int(job['id'])))==0

def test_concurrent_enable_creates_one_scan_event(jobs):
    """同一CAS版本的两个开启者只能一个成功，且只产生一个扫描事件。"""
    from concurrent.futures import ThreadPoolExecutor
    from app.jobs.service import JobService
    from app.identity.models import User
    from app.identity.views import resolve_user
    from app.core.errors import DomainError
    client,headers,job,_=ready(jobs);uows=client.app.state.identity.uow_factory
    version=current(jobs,job['id'])['version']
    with uows() as uow: actor=resolve_user(uow.session,uow.session.get(User,jobs[4]['hr']))
    def enable_one(_):
        try:
            JobService(uows,settings=client.app.state.identity.settings).set_automation(actor,int(job['id']),True,version)
            return 'succeeded'
        except DomainError as exc: return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(enable_one,range(2)))
    assert sorted(results)==['VERSION_CONFLICT','succeeded']
    with uows() as uow:
        assert uow.session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type=='invite.scan',OutboxEvent.aggregate_id==int(job['id'])))==1

def test_cross_department_paper_rejected_even_with_company_read(jobs):
    """全企业可读试卷不等于可以给另一个部门岗位绑定该卷。"""
    client,headers,job=create(jobs)
    other=login(jobs,'other')
    paper=request(client,other,'/papers',{'name':jobs[2]+'-other-paper','department_id':str(jobs[4]['d2'])})
    # A draft version is enough to exercise ownership; it never reaches publication.
    with client.app.state.identity.uow_factory() as uow:
        from app.assessment.models.papers import PaperVersion
        pv=PaperVersion(paper_id=int(paper['id']),version_no=1,duration_minutes=60,total_score=10,status='draft')
        uow.session.add(pv);uow.session.flush();pv_id=pv.id
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==jobs[4]['hr']))
        role.data_scope='company';uow.commit()
    # login(other) changed this client's cookie; restore matching HR session/CSRF.
    headers=login(jobs,'hr')
    response=client.post('/api/v1/jobs/'+job['id']+'/versions',json=body(pv_id),headers={**headers,'Idempotency-Key':uuid4().hex})
    assert response.status_code==422 and response.json()['code']=='PAPER_DEPARTMENT_MISMATCH'

@pytest.mark.parametrize('mutation',['boolean_years','subject_newline','invalid_operator'])
def test_rule_and_template_edge_values_rejected(jobs,mutation):
    client,headers,job=create(jobs);cmd=body()
    if mutation=='boolean_years': cmd['conditions'][0].update(field='relevant_years',expected=True)
    if mutation=='subject_newline': cmd['mail_template']['subject']='subject\nBcc: attacker@example.com'
    if mutation=='invalid_operator': cmd['conditions'][0].update(field='major',operator='gte',expected='软件工程')
    request(client,headers,'/jobs/'+job['id']+'/versions',cmd,422)
