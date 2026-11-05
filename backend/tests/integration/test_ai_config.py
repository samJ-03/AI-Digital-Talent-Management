import json
from uuid import uuid4
import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select,delete
from tests.integration.test_identity import identity,login
from app.identity.models import Role,UserRole
from app.ai_runtime.models import ModelConfig,PromptVersion,WorkflowConfig
from app.core.models import IdempotencyRecord

@pytest.fixture
def ai(identity):
    client,engine,uid,password,ids,*_=identity
    runtime=client.app.state.identity
    with runtime.uow_factory() as uow:
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==ids['admin']))
        role.permission_codes=sorted(set(role.permission_codes)|{'model.manage','prompt.manage','workflow.manage'})
        uow.commit()
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/chat/completions'):
            return httpx.Response(200,json={'model':'deepseek-flash','choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'stop'}]})
        return httpx.Response(404,json={'error':'not a supported test route'})
    if hasattr(client.app.state,'ai_runtime'):
        from app.ai_runtime.capability_probe import CapabilityProbe
        from app.core.secrets import SecretCipher
        client.app.state.ai_runtime.cipher=SecretCipher(Fernet.generate_key().decode())
        client.app.state.ai_runtime.probe=CapabilityProbe(transport=httpx.MockTransport(handler))
    yield identity,calls
    with runtime.uow_factory() as uow:
        model_ids=list(uow.session.scalars(select(ModelConfig.id).where(ModelConfig.logical_key.like(uid+'%'))))
        prompt_ids=list(uow.session.scalars(select(PromptVersion.id).where(PromptVersion.content.like(uid+'%'))))
        for row in uow.session.scalars(select(WorkflowConfig).where((WorkflowConfig.model_config_id.in_(model_ids))|(WorkflowConfig.prompt_version_id.in_(prompt_ids)))):
            row.model_config_id=None;row.prompt_version_id=None;row.enabled=False
        uow.session.flush()
        uow.session.execute(delete(ModelConfig).where(ModelConfig.id.in_(model_ids)))
        uow.session.execute(delete(PromptVersion).where(PromptVersion.id.in_(prompt_ids)))
        uow.session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.actor_scope=='admin:'+str(ids['admin'])))
        uow.commit()

def create_model(ai,headers):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    secret='synthetic-key-'+uuid4().hex
    body={'logical_key':uid+'-llm','provider_type':'compatible_http','base_url':'https://api.deepseek.com/v1','model_name':'deepseek-flash','secret':secret}
    result=client.post('/api/v1/admin/model-configs',json=body,headers=headers)
    assert result.status_code==201,result.text
    return result,secret

def publish_prompt(ai,headers,task_type='match'):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    body={'task_type':task_type,'content':uid+'-instructions: use evidence only','output_schema':{'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}}
    response=client.post('/api/v1/admin/prompts',json=body,headers=headers)
    assert response.status_code==201,response.text
    prompt_id=response.json()['data']['id']
    published=client.post('/api/v1/admin/prompts/'+prompt_id+'/publish',json={'reason':'synthetic test publish'},headers={**headers,'Idempotency-Key':uuid4().hex})
    assert published.status_code==200,published.text
    return published.json()['data']

def test_secret_write_only(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    response,secret=create_model(ai,headers)
    assert secret not in response.text and 'secret_ciphertext' not in response.text
    data=response.json()['data']
    assert data['secret_configured'] is True and data['enabled'] is False
    with client.app.state.identity.uow_factory() as uow:
        stored=uow.session.get(ModelConfig,int(data['id']))
        assert stored.secret_ciphertext and secret not in stored.secret_ciphertext
        assert client.app.state.ai_runtime.cipher.decrypt(stored.secret_ciphertext)==secret

def test_url_allowlist_blocks_ssrf_at_create_and_rechecks_before_test(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    rejected=client.post('/api/v1/admin/model-configs',json={'logical_key':uid+'-bad','provider_type':'compatible_http','base_url':'http://169.254.169.254/latest/meta-data','model_name':'deepseek-flash'},headers=headers)
    assert rejected.status_code==422
    response,secret=create_model(ai,headers);model_id=response.json()['data']['id']
    with client.app.state.identity.uow_factory() as uow:
        uow.session.get(ModelConfig,int(model_id)).base_url='https://api.deepseek.com.evil.example/v1';uow.commit()
    tested=client.post('/api/v1/admin/model-configs/'+model_id+'/test',headers=headers)
    assert tested.status_code==422 and calls==[]

def test_unverified_model_cannot_enable(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    model,secret=create_model(ai,headers);prompt=publish_prompt(ai,headers)
    workflows=client.get('/api/v1/admin/workflows')
    assert workflows.status_code==200,workflows.text
    flow=next(row for row in workflows.json()['data'] if row['task_type']=='match')
    response=client.put('/api/v1/admin/workflows/match',json={'model_config_id':model.json()['data']['id'],'prompt_version_id':prompt['id'],'enabled':True,'timeout_seconds':60,'max_retries':1},headers={**headers,'If-Match':str(flow['version'])})
    assert response.status_code==409 and response.json()['code']=='MODEL_NOT_VERIFIED'

def test_verified_model_and_matching_published_prompt_can_enable_with_cas(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    model,secret=create_model(ai,headers);model_id=model.json()['data']['id']
    tested=client.post('/api/v1/admin/model-configs/'+model_id+'/test',headers=headers)
    assert tested.status_code==200,tested.text
    assert tested.json()['data']['verified'] is True and len(calls)==1
    assert secret not in tested.text
    prompt=publish_prompt(ai,headers)
    flow=next(row for row in client.get('/api/v1/admin/workflows').json()['data'] if row['task_type']=='match')
    body={'model_config_id':model_id,'prompt_version_id':prompt['id'],'enabled':True,'timeout_seconds':60,'max_retries':1}
    response=client.put('/api/v1/admin/workflows/match',json=body,headers={**headers,'If-Match':str(flow['version'])})
    assert response.status_code==200,response.text
    assert response.json()['data']['enabled'] is True
    assert client.put('/api/v1/admin/workflows/match',json=body,headers={**headers,'If-Match':str(flow['version'])}).status_code==409

def test_prompt_published_immutable_and_publish_retries_idempotent(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity);prompt=publish_prompt(ai,headers)
    new=client.post('/api/v1/admin/prompts',json={'task_type':'match','content':uid+'-new revision','output_schema':{'type':'object'}},headers=headers)
    assert new.status_code==201 and new.json()['data']['revision_no']>prompt['revision_no']
    with client.app.state.identity.uow_factory() as uow: assert uow.session.get(PromptVersion,int(prompt['id'])).content==prompt['content']
    assert client.patch('/api/v1/admin/prompts/'+prompt['id'],json={'content':'overwrite'},headers=headers).status_code in {404,405}

def test_fixed_task_types_and_remote_schema_references_rejected(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    for task,schema in [('execute_python',{'type':'object'}),('match',{'$ref':'https://evil.example/schema.json'})]:
        response=client.post('/api/v1/admin/prompts',json={'task_type':task,'content':uid+'-blocked','output_schema':schema},headers=headers)
        assert response.status_code==422
    assert client.put('/api/v1/admin/workflows/execute_python',json={'enabled':True,'timeout_seconds':30,'max_retries':0},headers={**headers,'If-Match':'1'}).status_code==422

def test_hr_cannot_manage_model_configs(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity,'hr')
    response=client.post('/api/v1/admin/model-configs',json={'logical_key':uid,'provider_type':'compatible_http','base_url':'https://api.deepseek.com/v1','model_name':'deepseek-flash'},headers=headers)
    assert response.status_code==403 and not calls


def test_publish_same_key_replay_and_changed_payload_conflict(ai):
    identity,calls=ai
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    created=client.post('/api/v1/admin/prompts',json={'task_type':'match','content':uid+'-replay','output_schema':{'type':'object'}},headers=headers)
    assert created.status_code==201
    path='/api/v1/admin/prompts/'+created.json()['data']['id']+'/publish'
    headers={**headers,'Idempotency-Key':uuid4().hex}
    first=client.post(path,json={'reason':'publish'},headers=headers)
    replay=client.post(path,json={'reason':'publish'},headers=headers)
    assert first.status_code==replay.status_code==200
    assert first.json()['data']==replay.json()['data']
    assert client.post(path,json={'reason':'changed reason'},headers=headers).status_code==409
