"""平台开发工具：验证paper versions的正常与失败场景；测试数据仅用于隔离环境。"""
from uuid import uuid4
from decimal import Decimal
import pytest
from sqlalchemy import select,delete
from tests.integration.test_identity import identity,login
from app.identity.models import Role,UserRole
from app.assessment.models.papers import QuestionBank,Question,Paper,PaperVersion,PaperItem
from app.core.models import IdempotencyRecord

@pytest.fixture
def papers(identity):
    client,engine,uid,password,ids,*_=identity
    uows=client.app.state.identity.uow_factory
    with uows() as uow:
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==ids['hr']))
        role.permission_codes=sorted(set(role.permission_codes)|{'question.read','question.write','paper.read','paper.write'})
        uow.commit()
    yield identity
    with uows() as uow:
        banks=list(uow.session.scalars(select(QuestionBank.id).where(QuestionBank.name.like(uid+'%'))))
        paper_ids=list(uow.session.scalars(select(Paper.id).where(Paper.name.like(uid+'%'))))
        versions=list(uow.session.scalars(select(PaperVersion.id).where(PaperVersion.paper_id.in_(paper_ids))))
        uow.session.execute(delete(PaperItem).where(PaperItem.paper_version_id.in_(versions)))
        uow.session.execute(delete(PaperVersion).where(PaperVersion.id.in_(versions)))
        uow.session.execute(delete(Paper).where(Paper.id.in_(paper_ids)))
        uow.session.execute(delete(Question).where(Question.bank_id.in_(banks)))
        uow.session.execute(delete(QuestionBank).where(QuestionBank.id.in_(banks)))
        uow.session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.actor_scope.in_(['hr:'+str(ids['hr']),'hr:'+str(ids['other'])])))
        uow.commit()

def request(client,headers,path,body,status=201,method='post'):
    response=getattr(client,method)('/api/v1'+path,json=body,headers={**headers,'Idempotency-Key':uuid4().hex})
    assert response.status_code==status,response.text
    return response.json()['data']

def prepare(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity,'hr')
    bank=request(client,headers,'/question-banks',{'name':uid+'-bank','department_id':str(ids['d1'])})
    paper=request(client,headers,'/papers',{'name':uid+'-paper','department_id':str(ids['d1'])})
    return client,headers,bank,paper

def question(bank_id,stem='Original stem',selected=None):
    return {'bank_id':bank_id,'type':'single_choice','stem':stem,'options':[{'key':'A','text':'First'},{'key':'B','text':'Second'}],'answer_key':{'selected_keys':selected or ['A']},'rubric':{},'reference_sources':[]}

def approved_question(client,headers,bank_id,stem='Original stem'):
    q=request(client,headers,'/questions',question(bank_id,stem))
    return request(client,headers,'/questions/'+q['id']+'/approve',{'reason':'HR checked answer'},200)

def version_body(question_id,max_score='10.00'):
    return {'duration_minutes':60,'items':[{'source_question_id':question_id,'max_score':max_score,'position_no':1}]}

def test_only_approved_questions_publish(papers):
    client,headers,bank,paper=prepare(papers)
    q=request(client,headers,'/questions',question(bank['id']))
    version=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(q['id']))
    blocked=client.post('/api/v1/paper-versions/'+version['id']+'/publish',json={'reason':'publish'},headers={**headers,'Idempotency-Key':uuid4().hex})
    assert blocked.status_code==409
    request(client,headers,'/questions/'+q['id']+'/approve',{'reason':'confirmed'},200)
    published=request(client,headers,'/paper-versions/'+version['id']+'/publish',{'reason':'ready'},200)
    assert published['status']=='published'

def test_published_paper_frozen(papers):
    client,headers,bank,paper=prepare(papers)
    q=approved_question(client,headers,bank['id'])
    version=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(q['id']))
    frozen=request(client,headers,'/paper-versions/'+version['id']+'/publish',{'reason':'ready'},200)
    revised=request(client,headers,'/questions/'+q['id']+'/revisions',{**question(bank['id'],'Revised stem',['B']),'reason':'corrected'})
    request(client,headers,'/questions/'+revised['id']+'/approve',{'reason':'confirmed new revision'},200)
    response=client.get('/api/v1/paper-versions/'+version['id'])
    assert response.status_code==200,response.text
    item=response.json()['data']['items'][0]
    assert item['stem']=='Original stem' and item['answer_key']=={'selected_keys':['A']}
    assert item['rubric']==frozen['items'][0]['rubric']
    updated=client.patch('/api/v1/paper-versions/'+version['id'],json=version_body(revised['id']),headers={**headers,'If-Match':str(frozen['version'])})
    assert updated.status_code==409

def test_total_score_computed_and_multiple_choice_rule_frozen(papers):
    client,headers,bank,paper=prepare(papers)
    a=approved_question(client,headers,bank['id'],'Single')
    multi={**question(bank['id'],'Multiple'),'type':'multiple_choice','answer_key':{'selected_keys':['A','B']}}
    b=request(client,headers,'/questions',multi)
    request(client,headers,'/questions/'+b['id']+'/approve',{'reason':'reviewed'},200)
    body={'duration_minutes':30,'items':[{'source_question_id':a['id'],'max_score':'10.25','position_no':1},{'source_question_id':b['id'],'max_score':'20.50','position_no':2}]}
    version=request(client,headers,'/papers/'+paper['id']+'/versions',body)
    assert Decimal(version['total_score'])==Decimal('30.75')
    assert version['items'][1]['rubric']['policy']=='exact_set_all_or_nothing'
    bad=client.post('/api/v1/papers/'+paper['id']+'/versions',json={**body,'total_score':'999'},headers={**headers,'Idempotency-Key':uuid4().hex})
    assert bad.status_code==422

def test_candidate_projection_no_answer(papers):
    from app.assessment.projections import candidate_item
    from app.assessment.schemas import PaperItemView
    client,headers,bank,paper=prepare(papers)
    q=approved_question(client,headers,bank['id'])
    version=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(q['id']))
    value=candidate_item(PaperItemView.model_validate(version['items'][0])).model_dump()
    assert set(value)=={'id','type','stem','options','max_score'}
    assert 'answer_key' not in value and 'rubric' not in value and 'reference_sources' not in value

def test_cross_department_paper_read_and_question_copy_denied(papers):
    client,headers,bank,paper=prepare(papers)
    q=approved_question(client,headers,bank['id'])
    version=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(q['id']))
    other=login(papers,'other')
    assert client.get('/api/v1/paper-versions/'+version['id']).status_code==404
    response=client.post('/api/v1/questions',json=question(bank['id']),headers={**other,'Idempotency-Key':uuid4().hex})
    assert response.status_code==404

def test_invalid_answers_rubrics_and_positions_rejected(papers):
    client,headers,bank,paper=prepare(papers)
    for body in [{**question(bank['id']),'answer_key':{'selected_keys':['C']}},{**question(bank['id']),'options':[{'key':'A','text':'one'},{'key':'A','text':'duplicate'}]},{'bank_id':bank['id'],'type':'short_answer','stem':'Explain','rubric':{}}]:
        assert client.post('/api/v1/questions',json=body,headers={**headers,'Idempotency-Key':uuid4().hex}).status_code==422
    q=approved_question(client,headers,bank['id'])
    body=version_body(q['id']);body['items']*=2
    assert client.post('/api/v1/papers/'+paper['id']+'/versions',json=body,headers={**headers,'Idempotency-Key':uuid4().hex}).status_code==422

def test_create_and_publish_retry_have_single_resource_effect(papers):
    client,headers,bank,paper=prepare(papers)
    key=uuid4().hex;body=question(bank['id'])
    first=client.post('/api/v1/questions',json=body,headers={**headers,'Idempotency-Key':key})
    assert first.status_code==201,first.text
    replay=client.post('/api/v1/questions',json=body,headers={**headers,'Idempotency-Key':key})
    assert replay.status_code==201 and replay.json()['data']['id']==first.json()['data']['id']
    changed=client.post('/api/v1/questions',json=question(bank['id'],'changed'),headers={**headers,'Idempotency-Key':key})
    assert changed.status_code==409


def test_draft_child_change_increments_version_and_rejects_stale_editor(papers):
    client,headers,bank,paper=prepare(papers)
    a=approved_question(client,headers,bank['id'],'First')
    b=approved_question(client,headers,bank['id'],'Replacement')
    version=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(a['id']))
    path='/api/v1/paper-versions/'+version['id']
    edited=client.patch(path,json=version_body(b['id']),headers={**headers,'If-Match':str(version['version'])})
    assert edited.status_code==200,edited.text
    assert edited.json()['data']['version']==version['version']+1
    assert edited.json()['data']['items'][0]['stem']=='Replacement'
    assert client.patch(path,json=version_body(a['id']),headers={**headers,'If-Match':str(version['version'])}).status_code==409

def test_short_answer_criteria_allocation_has_no_negative_or_lost_cents(papers):
    client,headers,bank,paper=prepare(papers)
    rubric={'reference_answer':'Synthetic reference','criteria':[{'key':'c'+str(i),'description':'criterion '+str(i),'weight':1} for i in range(4)]}
    q=request(client,headers,'/questions',{'bank_id':bank['id'],'type':'short_answer','stem':'Explain','rubric':rubric})
    request(client,headers,'/questions/'+q['id']+'/approve',{'reason':'reviewed'},200)
    version=request(client,headers,'/papers/'+paper['id']+'/versions',version_body(q['id'],'0.02'))
    scores=[Decimal(c['max_score']) for c in version['items'][0]['rubric']['criteria']]
    assert all(s>=0 for s in scores) and sum(scores)==Decimal('0.02')

def test_no_read_permission_rejected_before_creating_a_snapshot(papers):
    from sqlalchemy import func
    client,headers,bank,paper=prepare(papers)
    q=approved_question(client,headers,bank['id'])
    ids=papers[4]
    with client.app.state.identity.uow_factory() as uow:
        role=uow.session.scalar(select(Role).join(UserRole,UserRole.role_id==Role.id).where(UserRole.user_id==ids['hr']))
        role.permission_codes=[p for p in role.permission_codes if p!='paper.read']
        uow.commit()
    headers=login(papers,'hr')
    response=client.post('/api/v1/papers/'+paper['id']+'/versions',json=version_body(q['id']),headers={**headers,'Idempotency-Key':uuid4().hex})
    assert response.status_code==403
    with client.app.state.identity.uow_factory() as uow:
        assert uow.session.scalar(select(func.count()).select_from(PaperVersion).where(PaperVersion.paper_id==int(paper['id'])))==0
