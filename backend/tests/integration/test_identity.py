"""平台开发工具：验证identity的正常与失败场景；测试数据仅用于隔离环境。"""
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command as migration
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from redis import Redis
from app.main import create_app
from app.core.settings import Settings
from app.identity.models import User, Role, UserRole, Department
from app.audit.models import AuditLog

@pytest.fixture
def identity():
    url=os.environ['TALENT_TEST_DATABASE_URL']
    assert make_url(url).database=='talent_test'
    cfg=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    cfg.set_main_option('sqlalchemy.url',url.replace('%','%%'))
    migration.upgrade(cfg,'head')
    uid=uuid4().hex[:16]
    password='test-'+uuid4().hex+'-A8!'
    engine=create_engine(url,pool_pre_ping=True)
    with Session(engine) as s:
        d1=Department(name=uid+'-D1');d2=Department(name=uid+'-D2')
        admin_role=Role(code=uid+'-admin',name='管理员',permission_codes=['user.manage','role.manage','department.manage'],data_scope='company')
        hr_role=Role(code=uid+'-hr',name='HR',permission_codes=['talent.read','job.write','exam.read'],data_scope='department')
        s.add_all([d1,d2,admin_role,hr_role]);s.flush()
        hashed=PasswordHasher().hash(password)
        admin=User(login_name=uid+'-admin',password_hash=hashed)
        hr=User(login_name=uid+'-hr',password_hash=hashed,department_id=d1.id)
        other=User(login_name=uid+'-other',password_hash=hashed,department_id=d2.id)
        s.add_all([admin,hr,other]);s.flush()
        s.add_all([UserRole(user_id=admin.id,role_id=admin_role.id),UserRole(user_id=hr.id,role_id=hr_role.id),UserRole(user_id=other.id,role_id=hr_role.id)])
        ids={'admin':admin.id,'hr':hr.id,'other':other.id,'d1':d1.id,'d2':d2.id,'hr_role':hr_role.id}
        s.commit()
    redis_url=os.environ['TALENT_REDIS_URL']
    namespace='talent:test:'+uid
    settings=Settings(environment='test',database_url=url,redis_url=redis_url,monitor_token='monitor-test',session_namespace=namespace,trusted_origins=['http://testserver'])
    app=create_app(settings)
    with TestClient(app) as client:
        yield client,engine,uid,password,ids,namespace,redis_url
    redis=Redis.from_url(redis_url)
    keys=list(redis.scan_iter(match=namespace+':*'))
    if keys: redis.delete(*keys)
    redis.close()
    with Session(engine) as s:
        users=list(s.scalars(select(User.id).where(User.login_name.like(uid+'%'))))
        s.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(users)))
        s.execute(delete(UserRole).where(UserRole.user_id.in_(users)))
        s.execute(delete(User).where(User.id.in_(users)))
        s.execute(delete(Role).where(Role.code.like(uid+'%')))
        depts=list(s.scalars(select(Department).where(Department.name.like(uid+'%'))))
        for d in depts: d.parent_id=None
        s.flush()
        s.execute(delete(Department).where(Department.name.like(uid+'%')))
        s.commit()
    engine.dispose()

def login(identity,who='admin',client=None):
    original,engine,uid,password,ids,*_=identity
    client=client or original
    response=client.post('/api/v1/auth/login',json={'login_name':uid+'-'+who,'password':password})
    assert response.status_code==200,response.text
    data=response.json()['data']
    assert 'session_id' not in data
    return {'X-CSRF-Token':data['csrf_token'],'Origin':'http://testserver'}

def test_argon2_hash_only(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    response=client.post('/api/v1/admin/users',json={'login_name':uid+'-new','password':password,'department_id':ids['d1'],'status':'active'},headers=headers)
    assert response.status_code==201,response.text
    assert password not in response.text and 'password_hash' not in response.text
    with Session(engine) as s:
        row=s.get(User,int(response.json()['data']['id']))
        assert row.password_hash.startswith('$argon2id$')
        assert row.password_hash!=password
        assert PasswordHasher().verify(row.password_hash,password)

def test_disable_revokes_cookie(identity):
    client,engine,uid,password,ids,*_=identity
    with TestClient(client.app) as hr:
        login(identity,'hr',hr)
        headers=login(identity)
        with Session(engine) as s: version=s.get(User,ids['hr']).row_version
        response=client.patch('/api/v1/admin/users/'+str(ids['hr']),json={'status':'disabled'},headers={**headers,'If-Match':str(version)})
        assert response.status_code==200,response.text
        assert hr.get('/api/v1/auth/me').status_code==401

def test_role_change_refreshes_permissions(identity):
    client,engine,uid,password,ids,*_=identity
    with TestClient(client.app) as hr:
        login(identity,'hr',hr)
        headers=login(identity)
        with Session(engine) as s: version=s.get(Role,ids['hr_role']).row_version
        response=client.patch('/api/v1/admin/roles/'+str(ids['hr_role']),json={'permission_codes':['talent.read']},headers={**headers,'If-Match':str(version)})
        assert response.status_code==200,response.text
        state=hr.get('/api/v1/auth/me')
        assert state.status_code in {200,401}
        if state.status_code==200: assert 'job.write' not in state.json()['data']['permission_codes']
        login(identity,'hr',hr)
        assert hr.get('/api/v1/auth/me').json()['data']['permission_codes']==['talent.read']

def test_department_no_cycle(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    a=client.patch('/api/v1/admin/departments/'+str(ids['d2']),json={'parent_id':str(ids['d1'])},headers={**headers,'If-Match':'1'})
    assert a.status_code==200,a.text
    b=client.patch('/api/v1/admin/departments/'+str(ids['d1']),json={'parent_id':str(ids['d2'])},headers={**headers,'If-Match':'1'})
    assert b.status_code==422,b.text

def test_csrf_required_for_write(identity):
    client,engine,uid,password,ids,*_=identity
    login(identity)
    response=client.post('/api/v1/admin/users',json={'login_name':uid+'-blocked','password':password})
    assert response.status_code==403

def test_hr_cannot_administer(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity,'hr')
    assert client.post('/api/v1/admin/departments',json={'name':uid+'-denied'},headers=headers).status_code==403

def test_login_wrong_password_does_not_set_session(identity):
    client,engine,uid,password,ids,*_=identity
    response=client.post('/api/v1/auth/login',json={'login_name':uid+'-admin','password':'wrong-password-value'})
    assert response.status_code==401
    assert not response.cookies
    assert client.get('/api/v1/auth/me').status_code==401

def test_session_cookie_flags_logout_and_candidate_cookie_separation(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    response=client.get('/api/v1/auth/me')
    assert response.status_code==200
    assert isinstance(response.json()['data']['id'],str)
    assert response.json()['data']['actor_type']=='admin'
    assert client.post('/api/v1/auth/logout',headers=headers).status_code==200
    assert client.get('/api/v1/auth/me').status_code==401
    client.cookies.set('talent_exam','fake-candidate-session')
    assert client.get('/api/v1/auth/me').status_code==401

def test_stale_version_rejected(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    path='/api/v1/admin/users/'+str(ids['hr'])
    first=client.patch(path,json={'department_id':str(ids['d2'])},headers={**headers,'If-Match':'1'})
    assert first.status_code==200
    assert first.headers['ETag']=='"2"'
    second=client.patch(path,json={'status':'disabled'},headers={**headers,'If-Match':'1'})
    assert second.status_code==409

def test_role_permission_allowlist_and_mixed_role_rejected(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    invalid=client.post('/api/v1/admin/roles',json={'code':uid+'-bad','name':'bad','permission_codes':['*'],'data_scope':'company','status':'active'},headers=headers)
    assert invalid.status_code==422
    mixed=client.post('/api/v1/admin/roles',json={'code':uid+'-mixed','name':'bad','permission_codes':['user.manage','talent.read'],'data_scope':'company','status':'active'},headers=headers)
    assert mixed.status_code==422

def test_login_rate_limit_is_not_disabled_by_wrong_password(identity):
    client,engine,uid,password,ids,*_=identity
    statuses=[]
    for _ in range(11): statuses.append(client.post('/api/v1/auth/login',json={'login_name':uid+'-missing','password':password}).status_code)
    assert statuses[-1]==429

def test_cross_site_login_and_write_rejected(identity):
    client,engine,uid,password,ids,*_=identity
    response=client.post('/api/v1/auth/login',json={'login_name':uid+'-admin','password':password},headers={'Origin':'https://evil.example'})
    assert response.status_code==403
    headers=login(identity)
    response=client.post('/api/v1/admin/departments',json={'name':uid+'-evil'},headers={**headers,'Origin':'https://evil.example'})
    assert response.status_code==403


def test_admin_queries_and_last_administrator_guard(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    for path in ['users','departments','roles']:
        response=client.get('/api/v1/admin/'+path)
        assert response.status_code==200,response.text
        assert 'password_hash' not in response.text
    with Session(engine) as s: version=s.get(User,ids['admin']).row_version
    response=client.patch('/api/v1/admin/users/'+str(ids['admin']),json={'status':'disabled'},headers={**headers,'If-Match':str(version)})
    assert response.status_code==422
    assert client.get('/api/v1/auth/me').status_code==200

def test_assigning_mixed_roles_rolls_back_and_valid_role_assignment_revokes(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    with Session(engine) as s: admin_role=s.scalar(select(UserRole.role_id).where(UserRole.user_id==ids['admin']))
    path='/api/v1/admin/users/'+str(ids['hr'])+'/roles'
    response=client.put(path,json={'role_ids':[str(admin_role),str(ids['hr_role'])]},headers={**headers,'If-Match':'1'})
    assert response.status_code==422
    with TestClient(client.app) as hr:
        login(identity,'hr',hr)
        response=client.put(path,json={'role_ids':[]},headers={**headers,'If-Match':'1'})
        assert response.status_code==200,response.text
        assert hr.get('/api/v1/auth/me').status_code==401

def test_cookie_security_and_password_reset_revoke_session(identity):
    client,engine,uid,password,ids,*_=identity
    response=client.post('/api/v1/auth/login',json={'login_name':uid+'-admin','password':password})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/api/v1' in cookie
    headers={'X-CSRF-Token':response.json()['data']['csrf_token']}
    with TestClient(client.app) as hr:
        login(identity,'hr',hr)
        updated=client.patch('/api/v1/admin/users/'+str(ids['hr']),json={'password':'reset-'+uuid4().hex+'-9!'},headers={**headers,'If-Match':'1'})
        assert updated.status_code==200,updated.text
        assert hr.get('/api/v1/auth/me').status_code==401

def test_audit_uses_request_id_and_excludes_password(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    request_id=str(uuid4())
    response=client.post('/api/v1/admin/users',json={'login_name':uid+'-audit','password':password},headers={**headers,'X-Request-ID':request_id})
    assert response.status_code==201,response.text
    with Session(engine) as s:
        log=s.scalar(select(AuditLog).where(AuditLog.request_id==request_id))
        assert log is not None and log.action=='user.create'
        assert password not in str(log.change_summary)


def test_redis_failure_is_fail_closed(identity,monkeypatch):
    from redis.exceptions import ConnectionError
    client,engine,uid,password,ids,*_=identity
    login(identity)
    def unavailable(*args,**kwargs): raise ConnectionError('test unavailable')
    monkeypatch.setattr(client.app.state.identity.store.redis,'get',unavailable)
    response=client.get('/api/v1/auth/me')
    assert response.status_code==503
    assert 'ConnectionError' not in response.text

def test_production_cookie_requires_https(identity):
    client,engine,uid,password,ids,namespace,redis_url=identity
    settings=Settings(environment='production',database_url=os.environ['TALENT_TEST_DATABASE_URL'],redis_url=redis_url,monitor_token='monitor-test-production-token-32characters',session_namespace=namespace,trusted_origins=['https://testserver'])
    with TestClient(create_app(settings),base_url='https://testserver') as production:
        response=production.post('/api/v1/auth/login',json={'login_name':uid+'-admin','password':password},headers={'Origin':'https://testserver'})
        assert response.status_code==200,response.text
        assert 'secure' in response.headers['set-cookie'].lower()
        assert production.get('/api/v1/auth/me').status_code==200

def test_disabling_parent_department_revokes_child_sessions(identity):
    client,engine,uid,password,ids,*_=identity
    headers=login(identity)
    response=client.patch('/api/v1/admin/departments/'+str(ids['d2']),json={'parent_id':str(ids['d1'])},headers={**headers,'If-Match':'1'})
    assert response.status_code==200
    with TestClient(client.app) as other:
        login(identity,'other',other)
        response=client.patch('/api/v1/admin/departments/'+str(ids['d1']),json={'status':'disabled'},headers={**headers,'If-Match':'1'})
        assert response.status_code==200,response.text
        assert other.get('/api/v1/auth/me').status_code==401
