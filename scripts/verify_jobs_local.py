"""在本地开发库建立合成岗位，验收状态机和自动邀请失败门。

在已启动的API容器执行：python /app/scripts/verify_jobs_local.py --allow-dev-write
仅写入标为synthetic的岗位/审计/幂等记录，不发信、不调用模型、不读取账号密码。
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.engine import make_url
from app.core.errors import DomainError
from app.core.settings import Settings
from app.core.uow import make_uow
from app.identity.models import User
from app.identity.views import resolve_user
from app.jobs.service import JobService
from app.jobs.schemas import JobCreate,JobVersionDraft
from app.runtime.models import OutboxEvent

def main() -> int:
    """显式确认开发写入后运行服务验收，只输出ID、状态和安全错误码。"""
    settings=Settings.load()
    if sys.argv[1:]!=['--allow-dev-write'] or settings.environment!='dev' or make_url(settings.database_url.get_secret_value()).database!='talent_dev':
        raise RuntimeError('Local talent_dev and explicit --allow-dev-write are required')
    with make_uow() as uow:
        user=uow.session.scalar(select(User).where(User.login_name=='hr-tech'))
        if user is None: raise RuntimeError('Bootstrap the local HR account first')
        actor=resolve_user(uow.session,user)
        department_id=user.department_id
    def service(): return JobService(make_uow,'synthetic-t12-'+uuid4().hex,settings)
    job=service().create(actor,JobCreate(title='synthetic-t12-'+uuid4().hex[:12],department_id=department_id,headcount=1))
    checks={'default_draft_off':job.status=='draft' and not job.auto_invite_enabled}
    draft=service().draft(actor,int(job.id),JobVersionDraft.model_validate({
        'description':'Synthetic Python backend role for local lifecycle verification only',
        'conditions':[{'key':'degree','field':'education','operator':'gte','expected':'bachelor','required':True}],
        'match_weights':{'skills':50,'experience':35,'responsibilities':15},'invite_threshold':75,
        'invite_valid_hours':72,'mail_template':{'subject':'{job_title} assessment','body':'{candidate_name}: {exam_url} until {valid_until}'}}))
    version=service().publish(actor,int(draft.id),'Synthetic local acceptance')
    checks['published']=version.status=='published'
    job=service().get(actor,int(job.id))
    job=service().transition(actor,int(job.id),'open',job.version,'Synthetic open')
    checks['opened']=job.status=='open' and not job.auto_invite_enabled
    reasons=[]
    try: service().set_automation(actor,int(job.id),True,job.version)
    except DomainError as exc:
        reasons=(exc.safe_details or {}).get('blocking_reasons',[])
        checks['missing_paper_blocked']=exc.code=='AUTOMATION_NOT_READY' and 'PAPER_NOT_PUBLISHED' in reasons
    else: checks['missing_paper_blocked']=False
    job=service().get(actor,int(job.id))
    checks['failed_enable_unchanged']=not job.auto_invite_enabled
    job=service().transition(actor,int(job.id),'pause',job.version,'Synthetic pause')
    checks['paused']=job.status=='paused'
    job=service().transition(actor,int(job.id),'open',job.version,'Synthetic reopen')
    checks['reopen_off']=job.status=='open' and not job.auto_invite_enabled
    job=service().transition(actor,int(job.id),'close',job.version,'Synthetic acceptance finished')
    checks['closed_off']=job.status=='closed' and not job.auto_invite_enabled
    with make_uow() as uow:
        events=uow.session.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_type=='job',OutboxEvent.aggregate_id==int(job.id)))
    checks['no_invitation_event']=events==0
    print(json.dumps({'ready':all(checks.values()),'job_id':job.id,'job_version_id':version.id,'final_status':job.status,'checks':checks,'blocking_reasons':reasons},indent=2))
    return 0 if all(checks.values()) else 1

if __name__=='__main__': raise SystemExit(main())
