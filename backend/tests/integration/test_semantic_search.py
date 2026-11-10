"""T20真实Milvus往返和MySQL过滤；embedding仅受控HTTP，不花模型额度。"""
import json
from uuid import uuid4
import pytest
from sqlalchemy import select,delete
from tests.integration.test_profile_sources import generation,profiles,merges,candidates,imports,identity
from tests.integration.test_identity import login
from app.ai_runtime.models import ModelConfig,WorkflowConfig
from app.search.models import IndexRecord
from app.talents.models import Candidate

@pytest.fixture
def semantic(generation):
    """配置独立合成embedding模型和真实测试集合，finally恢复原流程。"""
    import httpx
    from cryptography.fernet import Fernet
    from app.core.secrets import SecretCipher
    from app.ai_runtime.gateway import ModelGateway
    imports,factory,i,profile_service,_,_=generation
    profile_service.generate(i['a'],i['ar']);calls=[]
    cipher=SecretCipher(Fernet.generate_key().decode())
    with factory() as uow:
        model=ModelConfig(logical_key='test-semantic-'+uuid4().hex,revision_no=1,provider_type='compatible_http',base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',model_name='text-embedding-v3',embedding_dimension=1024,capabilities={'verified':True,'embedding':True},secret_ciphertext=cipher.encrypt('synthetic-only'),enabled=True)
        uow.session.add(model);uow.session.flush();mid=model.id
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='embedding'))
        keys=['enabled','model_config_id','prompt_version_id','config_revision','max_retries','timeout_seconds'];old={k:getattr(flow,k) for k in keys}
        flow.enabled=True;flow.model_config_id=mid;flow.prompt_version_id=None;flow.max_retries=0;flow.timeout_seconds=10;flow.config_revision+=1;uow.commit()
    def transport(request):
        body=json.loads(request.content);calls.extend(body['input']);d=body['dimensions']
        return httpx.Response(200,json={'data':[{'index':n,'embedding':[1.0,0.5]+[0.0]*(d-2)} for n,t in enumerate(body['input'])]})
    gateway=ModelGateway(factory,cipher,httpx.MockTransport(transport))
    from app.search.milvus_store import MilvusStore
    store=MilvusStore(uri='http://milvus:19530',prefix='talent_test_'+uuid4().hex[:12])
    yield imports,factory,i,gateway,store,mid,calls
    for name in store.created:
        if store.client.has_collection(name,timeout=10):store.client.drop_collection(name,timeout=10)
    store.close()
    with factory() as uow:
        from app.runtime.models import BackgroundJob,OutboxEvent
        tids=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.job_type=='profile.index',BackgroundJob.input_refs['model_config_id'].as_integer()==mid)))
        uow.session.execute(delete(OutboxEvent).where(OutboxEvent.event_type=='job.dispatch',OutboxEvent.aggregate_id.in_(tids)))
        uow.session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(tids)))
        uow.session.execute(delete(IndexRecord).where(IndexRecord.model_config_id==mid))
        flow=uow.session.scalar(select(WorkflowConfig).where(WorkflowConfig.task_type=='embedding'))
        for k,v in old.items():setattr(flow,k,v)
        uow.session.flush();uow.session.execute(delete(ModelConfig).where(ModelConfig.id==mid));uow.commit()

def index(semantic):
    """索引当前可信共享画像。"""
    from app.search.index_service import IndexService
    from app.search.schemas import IndexEntityRef
    _,factory,i,gateway,store,mid,_=semantic
    with factory() as uow:pid=uow.session.get(Candidate,i['a']).current_profile_id
    return IndexService(factory,gateway,store).sync(IndexEntityRef(type='profile',id=pid),mid)

def query(semantic,**kwargs):
    from app.search.talent_search import TalentSearchService
    from app.search.schemas import TalentSearchQuery
    from app.identity.models import User
    from app.identity.views import resolve_user
    imports,factory,_,gateway,store,_,_=semantic
    with factory() as uow:actor=resolve_user(uow.session,uow.session.get(User,imports[0][4]['hr']))
    return TalentSearchService(factory,gateway,store).search(actor,TalentSearchQuery(query='Python项目工程师',**kwargs))

def test_milvus_real_roundtrip(semantic):
    assert index(semantic).state=='ready'
    result=query(semantic);assert len(result.items)==1 and result.items[0].candidate_id==str(semantic[2]['a'])
    assert result.items[0].semantic_relevance>0 and not result.degraded

@pytest.mark.parametrize('change',['archive','merged','old_profile'])
def test_stale_vector_filtered(semantic,change):
    index(semantic);_,factory,i,_,_,_,_=semantic
    with factory() as uow:
        row=uow.session.get(Candidate,i['a'])
        if change=='archive':row.status='archived'
        elif change=='merged':row.merged_into_id=i['b']
        else:row.current_profile_id=i['profiles'][0]
        uow.commit()
    assert query(semantic).items==[]

def test_private_evidence_not_indexed(semantic):
    index(semantic);calls=semantic[-1]
    assert calls and 'PRIVATE_EVALUATION_SENTINEL' not in json.dumps(calls) and 'same@example.com' not in json.dumps(calls)

def test_new_embedding_dimension_new_collection(semantic):
    first=index(semantic);_,factory,_,_,_,mid,_=semantic
    with factory() as uow:
        model=uow.session.get(ModelConfig,mid);model.revision_no=2;model.embedding_dimension=512;uow.commit()
    second=index(semantic);assert second.collection_name!=first.collection_name
    assert len(query(semantic).items)==1

def test_index_down_503_not_empty(generation):
    imports,*_=generation
    response=imports[0][0].post('/api/v1/talents/search',json={'query':'Python项目工程师','page_size':20},headers=login(imports[0],'hr'))
    assert response.status_code==503,response.text
    assert response.json()['code']=='SEMANTIC_INDEX_UNAVAILABLE'


def test_http_search_scope_filters_and_no_private_fields(semantic):
    from app.search.talent_search import TalentSearchService
    index(semantic);imports,factory,i,gateway,store,_,_=semantic;client=imports[0][0]
    client.app.state.talent_search=TalentSearchService(factory,gateway,store)
    response=client.post('/api/v1/talents/search',json={'query':'Python工程师'},headers=login(imports[0],'hr'))
    assert response.status_code==200,response.text
    assert response.json()['data']['items'] and 'no-store' in response.headers['cache-control']
    response=client.post('/api/v1/talents/search',json={'query':'Python','filters':{'skills':['Java']}},headers=login(imports[0],'hr'))
    assert response.status_code==200 and response.json()['data']['items']==[]
    response=client.post('/api/v1/talents/search',json={'query':'Python'},headers=login(imports[0],'admin'));assert response.status_code==403
    response=client.get(f"/api/v1/jobs/{i['job']}/recommendations");assert response.status_code==403
    assert 'PRIVATE_EVALUATION_SENTINEL' not in response.text


def test_sdk_search_failure_explicit_503(semantic):
    from app.core.errors import DomainError
    index(semantic);store=semantic[4];original=store.client.search
    def unavailable(*args,**kwargs):raise ConnectionError('synthetic failure')
    store.client.search=unavailable
    try:
        with pytest.raises(DomainError,match='SEMANTIC_INDEX_UNAVAILABLE'):query(semantic)
    finally:store.client.search=original


def test_index_rebuild_after_failure(semantic):
    from app.core.errors import DomainError
    store=semantic[4];original=store.upsert
    def unavailable(*args,**kwargs):raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'不可用')
    store.upsert=unavailable
    with pytest.raises(DomainError):index(semantic)
    with semantic[1]() as uow:
        assert uow.session.scalar(select(IndexRecord).where(IndexRecord.model_config_id==semantic[5])).state=='failed'
    store.upsert=original
    assert index(semantic).state=='ready' and len(query(semantic).items)==1


def test_missing_collection_is_not_empty_success(semantic):
    from app.core.errors import DomainError
    result=index(semantic);store=semantic[4];store.client.drop_collection(result.collection_name,timeout=10)
    with pytest.raises(DomainError,match='SEMANTIC_INDEX_UNAVAILABLE'):query(semantic)
    assert index(semantic).state=='ready' and len(query(semantic).items)==1


def test_index_recovery_queues_and_worker_syncs(semantic):
    from app.search.worker import IndexRecovery,ProfileIndexHandler
    from app.search.index_service import IndexService
    from app.runtime.job_service import BackgroundJobService,JobRunner
    from app.runtime.models import BackgroundJob
    _,factory,_,gateway,store,mid,_=semantic
    recovery=IndexRecovery(factory);assert recovery.recover()>=1 and recovery.recover()==0
    with factory() as uow:tids=list(uow.session.scalars(select(BackgroundJob.id).where(BackgroundJob.job_type=='profile.index',BackgroundJob.input_refs['model_config_id'].as_integer()==mid)))
    runner=JobRunner(BackgroundJobService(factory),{'profile.index':ProfileIndexHandler(IndexService(factory,gateway,store))})
    for tid in tids:runner.execute(tid)
    with factory() as uow:assert all(uow.session.get(BackgroundJob,tid).state=='succeeded' for tid in tids)
    assert query(semantic).items


def test_recommendations_readonly_and_department_scope(semantic):
    from app.search.talent_search import TalentSearchService
    from app.jobs.models import Job
    from app.recruitment.models import Application
    from sqlalchemy import func
    index(semantic);imports,factory,i,gateway,store,_,_=semantic;client=imports[0][0]
    client.app.state.talent_search=TalentSearchService(factory,gateway,store)
    with factory() as uow:
        uow.session.get(Job,i['job']).current_version_id=i['jv'];count=uow.session.scalar(select(func.count()).select_from(Application));uow.commit()
    try:
        login(imports[0],'hr');response=client.get(f"/api/v1/jobs/{i['job']}/recommendations");assert response.status_code==200,response.text
        assert response.json()['data'] and 'semantic_relevance' in response.json()['data'][0]
        login(imports[0],'other');response=client.get(f"/api/v1/jobs/{i['job']}/recommendations");assert response.status_code in [403,404]
        with factory() as uow:assert uow.session.scalar(select(func.count()).select_from(Application))==count
    finally:
        with factory() as uow:uow.session.get(Job,i['job']).current_version_id=None;uow.commit()


def test_late_index_failure_cannot_replace_ready(semantic):
    from app.core.errors import DomainError
    store=semantic[4];original=store.upsert
    def late_failure(collection,records):
        store.upsert=original
        assert index(semantic).state=='ready'
        raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'迟到执行失败')
    store.upsert=late_failure
    with pytest.raises(DomainError):index(semantic)
    with semantic[1]() as uow:
        row=uow.session.scalar(select(IndexRecord).where(IndexRecord.model_config_id==semantic[5]))
        assert row.state=='ready'
    assert query(semantic).items


def test_index_expired_lease_cannot_publish_ready(semantic):
    from datetime import timedelta
    from app.search.worker import IndexRecovery,ProfileIndexHandler
    from app.search.index_service import IndexService
    from app.runtime.job_service import BackgroundJobService
    from app.runtime.models import BackgroundJob
    from app.core.errors import DomainError
    _,factory,i,gateway,store,mid,_=semantic;IndexRecovery(factory).recover()
    with factory() as uow:tid=uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.job_type=='profile.index',BackgroundJob.input_refs['model_config_id'].as_integer()==mid).order_by(BackgroundJob.id))
    tasks=BackgroundJobService(factory);lease=tasks.claim(tid,'test');handler=ProfileIndexHandler(IndexService(factory,gateway,store));callback=handler.prepare(lease)
    with factory() as uow:uow.session.get(BackgroundJob,tid).lease_until-=timedelta(days=1);uow.commit()
    from contextlib import nullcontext
    with pytest.raises(DomainError,match='STALE_JOB_LEASE'),handler.finalization_context() if hasattr(handler,'finalization_context') else nullcontext():tasks.run_atomic(lease,callback)
    with factory() as uow:assert uow.session.scalar(select(IndexRecord.id).where(IndexRecord.model_config_id==mid,IndexRecord.state=='ready')) is None
