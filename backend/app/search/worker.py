"""共享画像索引任务处理与持久恢复，不自动启用模型流程。"""
from sqlalchemy import select,exists
from app.core.uow import make_uow
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.runtime.models import BackgroundJob
from app.runtime.job_service import BackgroundJobService,JobSpec,TerminalJobFailure
from app.talents.models import Candidate,CandidateProfile
from app.search.models import IndexRecord
from app.search.index_service import IndexService,embedding_identity,profile_hash
from app.search.schemas import IndexEntityRef

class ProfileIndexHandler:
    """SDK I/O在prepare执行；可信索引状态和任务结果均在有效租约事务发布。"""
    def __init__(self,service):self.service=service

    def finalization_context(self):
        """身份锁覆盖租约复验、索引可信状态和任务提交。"""
        return self.service.profiles.candidates.identity_write()

    def prepare(self,lease):
        """任务必须绑定同一profile与模型ID。"""
        tasks=BackgroundJobService(self.service.uow_factory)
        with self.service.uow_factory() as uow:
            job=tasks._owned(uow,lease);refs=dict(job.input_refs)
            if job.job_type!='profile.index' or job.entity_type!='candidate_profile' or job.entity_id!=refs.get('profile_id') or type(refs.get('model_config_id')) is not int:raise DomainError('INVALID_OUTPUT',422,'索引任务引用无效')
        prepared=self.service.prepare(IndexEntityRef('profile',refs['profile_id']),refs['model_config_id'])
        def finalize(uow,job):
            if job.input_refs!=refs:raise DomainError('INVALID_OUTPUT',422,'索引任务来源已变化')
            result=self.service.finalize(uow,prepared)
            if prepared.failure:return TerminalJobFailure('DEPENDENCY_UNAVAILABLE')
            return ResultRef('index_record',result.record_id,200)
        return finalize

class IndexRecovery:
    """从MySQL恢复当前画像索引；同来源同模型只有一个持久任务。"""
    def __init__(self,uow_factory=make_uow):self.uow_factory=uow_factory;self.service=IndexService(uow_factory)

    def recover(self,limit=100):
        """模型流程关闭则不排队；失败任务不无限新增绕过重试上限。"""
        with self.uow_factory() as uow:
            try:identity=embedding_identity(uow)
            except DomainError:return 0
            profiles=list(uow.session.scalars(select(CandidateProfile).join(Candidate,Candidate.current_profile_id==CandidateProfile.id).where(Candidate.status=='ready',Candidate.merged_into_id.is_(None)).order_by(CandidateProfile.id)))
            count=0
            for profile in profiles:
                try:self.service._source(uow,profile.id)
                except DomainError:continue
                digest=profile_hash(profile);model_id,revision,dimension,model_digest=identity[:4]
                from hashlib import sha256
                gen=sha256(str(identity).encode()).hexdigest()[:16]
                key=f'profile-index:{profile.id}:{gen}:{digest}'
                if uow.session.scalar(select(BackgroundJob.id).where(BackgroundJob.idempotency_key==key)):continue
                BackgroundJobService(self.uow_factory).enqueue(uow,JobSpec('profile.index','candidate_profile',profile.id,key,{'profile_id':profile.id,'model_config_id':model_id,'input_hash':digest,'embedding_revision':gen}));count+=1
                if count>=limit:break
            uow.commit();return count
