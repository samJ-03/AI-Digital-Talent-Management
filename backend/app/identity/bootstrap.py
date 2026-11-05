"""Local-only bootstrap. Passwords arrive on stdin, never command arguments."""
import json
import sys
from argon2 import PasswordHasher
from sqlalchemy import select,func
from app.core.settings import Settings
from app.core.uow import make_uow
from app.identity.models import User,Role,UserRole,Department
from app.identity.permissions import ADMIN_PERMISSIONS,HR_PERMISSIONS

def main():
    settings=Settings.load()
    if settings.environment!='dev':
        raise RuntimeError('Bootstrap is restricted to local development')
    credentials=json.load(sys.stdin)
    names=['admin','hr-tech','hr-ops']
    if set(credentials)!=set(names) or any(not isinstance(v,str) or len(v)<24 for v in credentials.values()):
        raise ValueError('Three generated non-default credentials are required')
    with make_uow() as uow:
        if uow.session.scalar(select(func.count()).select_from(User)):
            raise RuntimeError('Accounts already exist; bootstrap never resets them')
        admin_role=Role(code='platform_admin',name='系统管理员',permission_codes=sorted(ADMIN_PERMISSIONS),data_scope='company')
        hr_role=Role(code='recruiter',name='招聘 HR',permission_codes=sorted(HR_PERMISSIONS),data_scope='department')
        departments=[Department(name='技术部'),Department(name='运营部')]
        uow.session.add_all([admin_role,hr_role,*departments]);uow.session.flush()
        result=[]
        for index,name in enumerate(names):
            row=User(login_name=name,password_hash=PasswordHasher().hash(credentials[name]),department_id=None if index==0 else departments[index-1].id)
            uow.session.add(row);uow.session.flush()
            uow.session.add(UserRole(user_id=row.id,role_id=admin_role.id if index==0 else hr_role.id))
            result.append({'id':str(row.id),'login_name':name})
        uow.commit()
    print(json.dumps({'created':result}))

if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'error_type':type(error).__name__,'message':'Local bootstrap refused or failed; existing accounts are never reset.'}))
        sys.exit(1)
