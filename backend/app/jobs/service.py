"""HR岗位服务：部门授权、不可变版本、CAS和原子自动邀请事件。"""
from datetime import datetime,timezone
from copy import deepcopy
from sqlalchemy import select
from pydantic import ValidationError
from app.core.access import ResourceScope,AccessPolicy,ActorContext
from app.core.errors import DomainError
from app.core.hr_service import HrServiceBase
from app.core.idempotency import ResultRef
from app.core.settings import Settings
from app.identity.models import Department,User
from app.identity.views import resolve_user
from app.assessment.models.papers import Paper,PaperVersion
from app.runtime.models import OutboxEvent
from app.jobs.models import Job,JobVersion
from app.jobs.readiness import AutomationReadiness,lock_dependencies
from app.jobs.schemas import JobCreate,JobPatch,JobVersionDraft,JobView,JobVersionView,AutomationView
from app.jobs.views import job_view,version_view

class JobService(HrServiceBase):
    """只接受服务端Actor；所有公开写操作在本模块内控制事务。"""
    def __init__(self,uow_factory=None,idempotency_key=None,settings=None):
        from app.core.uow import make_uow
        super().__init__(uow_factory or make_uow,idempotency_key)
        self.settings=settings if settings is not None else Settings.load()

    def _scope(self,job_id):
        with self.uow_factory() as uow:
            row=uow.session.get(Job,job_id)
            if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'岗位不存在')
            return ResourceScope('job',id=row.id,department_id=row.department_id)

    def _version_scope(self,version_id):
        with self.uow_factory() as uow:
            job_id=uow.session.scalar(select(JobVersion.job_id).where(JobVersion.id==version_id))
            if job_id is None: raise DomainError('RESOURCE_NOT_FOUND',404,'岗位版本不存在')
        return self._scope(job_id)

    def _job(self,uow,job_id,expected_version=None):
        row=uow.session.scalar(select(Job).where(Job.id==job_id).with_for_update().execution_options(populate_existing=True))
        if row is None: raise DomainError('RESOURCE_NOT_FOUND',404,'岗位不存在')
        if expected_version is not None and row.row_version!=expected_version:
            raise DomainError('VERSION_CONFLICT',409,'岗位已被修改，请刷新后重试')
        return row

    def _department(self,uow,department_id):
        row=uow.session.get(Department,department_id)
        if row is None or row.status!='active': raise DomainError('INVALID_DEPARTMENT',422,'部门不存在或已停用')

    def _owner(self,uow,user_id,department_id):
        user=uow.session.get(User,user_id)
        if user is None: raise DomainError('INVALID_JOB_OWNER',422,'负责人须为有本部门岗位权限的有效HR')
        try:
            owner=resolve_user(uow.session,user)
            if owner.actor_type!='hr': raise ValueError()
            AccessPolicy().require(owner,'job.write',ResourceScope('job',department_id=department_id))
        except (DomainError,ValueError): raise DomainError('INVALID_JOB_OWNER',422,'负责人须为有本部门岗位权限的有效HR') from None

    def _paper(self,uow,actor,paper_version_id,department_id,published=False):
        if paper_version_id is None: return
        version=uow.session.get(PaperVersion,paper_version_id)
        if version is None: raise DomainError('RESOURCE_NOT_FOUND',404,'试卷版本不存在')
        paper=uow.session.scalar(select(Paper).where(Paper.id==version.paper_id).with_for_update())
        if paper is None: raise DomainError('RESOURCE_NOT_FOUND',404,'试卷不存在')
        self.authorize(uow,actor,'paper.read',ResourceScope('paper',id=paper.id,department_id=paper.department_id))
        if paper.department_id!=department_id: raise DomainError('PAPER_DEPARTMENT_MISMATCH',422,'岗位只能引用同部门试卷')
        version=uow.session.scalar(select(PaperVersion).where(PaperVersion.id==paper_version_id).with_for_update().execution_options(populate_existing=True))
        if paper.status!='active' or published and version.status!='published':
            raise DomainError('PAPER_NOT_PUBLISHED',409,'试卷须为有效发布版本')

    def _current(self,uow,job):
        version=uow.session.get(JobVersion,job.current_version_id) if job.current_version_id else None
        if version is not None and version.job_id!=job.id:
            raise DomainError('CURRENT_VERSION_MISMATCH',409,'当前版本不属于本岗位')
        if version is None or version.status!='published':
            raise DomainError('JOB_VERSION_NOT_PUBLISHED',409,'岗位尚无有效发布版本')
        return version

    def _fill(self,row,cmd):
        data=cmd.model_dump(mode='json')
        for name in ['description','conditions','match_weights','invite_threshold','paper_version_id','invite_valid_hours','mail_template']:
            setattr(row,name,deepcopy(data[name]))

    def get(self,actor: ActorContext,job_id: int) -> JobView:
        """读取岗位元数据，重新核对当前身份和部门范围。"""
        scope=self._scope(job_id)
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'job.read',scope)
            return job_view(uow.session.get(Job,job_id))

    def get_version(self,actor: ActorContext,version_id: int) -> JobVersionView:
        """读取岗位标准版本；不展开试卷答案或配置秘密。"""
        scope=self._version_scope(version_id)
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'job.read',scope)
            return version_view(uow.session.get(JobVersion,version_id))

    def create(self,actor: ActorContext,cmd: JobCreate) -> JobView:
        """建岗默认draft/off；元数据、审计和幂等结果同事务。"""
        scope=ResourceScope('job',department_id=cmd.department_id)
        def command(uow,fresh):
            self._department(uow,cmd.department_id)
            self._owner(uow,fresh.user_id,cmd.department_id)
            row=Job(title=cmd.title,department_id=cmd.department_id,owner_hr_id=fresh.user_id,headcount=cmd.headcount,status='draft',auto_invite_enabled=False)
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'job.create','job',row.id,{'department_id':row.department_id})
            return ResultRef('job',row.id,201)
        result=self.execute(actor,'job.write',scope,'job.create',cmd.model_dump(mode='json'),command,response_permission='job.read')
        return self.get(actor,result.entity_id)

    def update(self,actor: ActorContext,job_id: int,cmd: JobPatch,expected_version: int) -> JobView:
        """CAS更新允许的可变元数据，不接受部门或current指针覆盖。"""
        scope=self._scope(job_id)
        with self.transaction(actor,'job.write',scope,response_permission='job.read') as (uow,fresh):
            row=self._job(uow,job_id,expected_version);self._department(uow,row.department_id)
            values=cmd.model_dump(exclude_unset=True)
            if 'owner_hr_id' in values: self._owner(uow,cmd.owner_hr_id,row.department_id)
            for name,value in values.items(): setattr(row,name,value)
            self.audit(uow,fresh,'job.update','job',job_id,{'changed_fields':sorted(values)})
        return self.get(actor,job_id)

    def draft(self,actor: ActorContext,job_id: int,cmd: JobVersionDraft) -> JobVersionView:
        """锁岗位分配连续版本号，草稿不改变当前发布版本。"""
        scope=self._scope(job_id)
        def command(uow,fresh):
            job=self._job(uow,job_id);self._department(uow,job.department_id)
            self._paper(uow,fresh,cmd.paper_version_id,job.department_id)
            # Locking read sees a prior lock holder's commit under MySQL REPEATABLE READ.
            last=uow.session.scalar(select(JobVersion.version_no).where(JobVersion.job_id==job_id).order_by(JobVersion.version_no.desc()).limit(1).with_for_update())
            number=(last or 0)+1
            row=JobVersion(job_id=job_id,version_no=number,status='draft');self._fill(row,cmd)
            uow.session.add(row);uow.session.flush()
            self.audit(uow,fresh,'job.draft','job_version',row.id,{'revision':number})
            return ResultRef('job_version',row.id,201)
        result=self.execute(actor,'job.write',scope,'job.draft',{'job_id':job_id,**cmd.model_dump(mode='json')},command,response_permission='job.read')
        return self.get_version(actor,result.entity_id)

    def edit_draft(self,actor: ActorContext,version_id: int,cmd: JobVersionDraft,expected_version: int) -> JobVersionView:
        """只修改draft且检查CAS；发布内容始终不可原位覆盖。"""
        scope=self._version_scope(version_id)
        with self.transaction(actor,'job.write',scope,response_permission='job.read') as (uow,fresh):
            job=self._job(uow,scope.id);self._department(uow,job.department_id)
            row=uow.session.scalar(select(JobVersion).where(JobVersion.id==version_id).with_for_update())
            if row.row_version!=expected_version: raise DomainError('VERSION_CONFLICT',409,'岗位草稿已被修改')
            if row.status!='draft': raise DomainError('JOB_VERSION_IMMUTABLE',409,'发布版本不可修改，请创建新草稿')
            self._paper(uow,fresh,cmd.paper_version_id,job.department_id)
            self._fill(row,cmd)
            self.audit(uow,fresh,'job.edit','job_version',row.id,{'changed_fields':sorted(type(cmd).model_fields)})
        return self.get_version(actor,version_id)

    def publish(self,actor: ActorContext,version_id: int,reason: str) -> JobVersionView:
        """发布后切换本岗位current，关闭自动邀请以重新确认新标准。"""
        if not reason.strip(): raise DomainError('REASON_REQUIRED',422,'发布原因不可为空')
        scope=self._version_scope(version_id)
        def command(uow,fresh):
            lock_dependencies(uow.session)
            job=self._job(uow,scope.id);self._department(uow,job.department_id)
            row=uow.session.scalar(select(JobVersion).where(JobVersion.id==version_id).with_for_update())
            if row.job_id!=job.id: raise DomainError('CURRENT_VERSION_MISMATCH',409,'版本不属于本岗位')
            if row.status=='published':
                if job.current_version_id==row.id: return ResultRef('job_version',row.id,200)
                raise DomainError('JOB_VERSION_IMMUTABLE',409,'已发布历史版本不能重新切换为当前版本')
            # Revalidate stored drafts at publication, including manually damaged data.
            try: JobVersionDraft.model_validate({name:getattr(row,name) for name in JobVersionDraft.model_fields})
            except ValidationError: raise DomainError('JOB_VERSION_INVALID',409,'岗位草稿数据无效，请修正后发布') from None
            self._paper(uow,fresh,row.paper_version_id,job.department_id,published=True)
            row.status='published';row.published_by=fresh.user_id;row.published_at=datetime.now(timezone.utc).replace(tzinfo=None)
            job.current_version_id=row.id;job.auto_invite_enabled=False
            uow.session.flush()
            self.audit(uow,fresh,'job.publish','job_version',row.id,{'reason':reason,'revision':row.version_no})
            return ResultRef('job_version',row.id,200)
        result=self.execute(actor,'job.write',scope,'job.publish',{'version_id':version_id,'reason':reason},command,response_permission='job.read')
        return self.get_version(actor,result.entity_id)

    def transition(self,actor: ActorContext,job_id: int,action: str,expected_version: int,reason: str) -> JobView:
        """显式状态转换；暂停、关闭与重新开放均不恢复旧自动邀请。"""
        if action not in {'open','pause','close'} or not reason.strip(): raise DomainError('INVALID_JOB_TRANSITION',422,'动作及原因无效')
        scope=self._scope(job_id);target={'open':'open','pause':'paused','close':'closed'}[action]
        def command(uow,fresh):
            row=self._job(uow,job_id,expected_version);self._department(uow,row.department_id)
            if target=='open': self._current(uow,row)
            if row.status==target: return ResultRef('job',job_id,200)
            if target=='paused' and row.status!='open': raise DomainError('INVALID_JOB_TRANSITION',409,'只有开放岗位可以暂停')
            row.status=target;row.auto_invite_enabled=False
            self.audit(uow,fresh,'job.state','job',row.id,{'reason':reason,'state':target})
            return ResultRef('job',row.id,200)
        result=self.execute(actor,'job.write',scope,'job.state',{'job_id':job_id,'action':action,'version':expected_version,'reason':reason},command,response_permission='job.read')
        return self.get(actor,result.entity_id)

    def set_automation(self,actor: ActorContext,job_id: int,enabled: bool,expected_version: int) -> AutomationView:
        """开启必须就绪；仅false到true原子追加一次扫描事件。"""
        if type(enabled) is not bool: raise DomainError('INVALID_AUTOMATION',422,'开关须为布尔值')
        scope=self._scope(job_id)
        with self.transaction(actor,'job.write',scope,response_permission='job.read') as (uow,fresh):
            dependencies=lock_dependencies(uow.session) if enabled else None
            row=self._job(uow,job_id,expected_version);self._department(uow,row.department_id)
            if enabled:
                self.authorize(uow,fresh,'exam.invite',scope)
                self.authorize(uow,fresh,'paper.read',scope)
                readiness=AutomationReadiness(self.settings).check(uow.session,row,dependencies)
                if not readiness.ready:
                    raise DomainError('AUTOMATION_NOT_READY',409,'自动邀请尚未就绪',{'blocking_reasons':readiness.blocking_reasons})
                if not row.auto_invite_enabled:
                    row.auto_invite_enabled=True;uow.session.flush()
                    uow.session.add(OutboxEvent(event_type='invite.scan',aggregate_type='job',aggregate_id=row.id,
                        event_key=f'invite-scan:job:{row.id}:revision:{row.row_version}',
                        payload_refs={'job_id':row.id,'job_version_id':row.current_version_id,'automation_revision':row.row_version},
                        state='pending',next_attempt_at=datetime.now(timezone.utc).replace(tzinfo=None)))
                    self.audit(uow,fresh,'job.automation','job',job_id,{'enabled':True,'revision':row.row_version})
            elif row.auto_invite_enabled:
                row.auto_invite_enabled=False
                self.audit(uow,fresh,'job.automation','job',job_id,{'enabled':False})
        with self.uow_factory() as uow:
            self.authorize(uow,actor,'job.read',scope)
            row=uow.session.get(Job,job_id)
            return AutomationView(job=job_view(row),readiness=AutomationReadiness(self.settings).check(uow.session,row))
