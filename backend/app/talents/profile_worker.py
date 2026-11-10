"""固定profile.build处理器：模型I/O与租约保护的原子写入分离。"""
from app.core.errors import DomainError
from app.core.idempotency import ResultRef
from app.runtime.job_service import BackgroundJobService,TerminalJobFailure

CONFIG_ERRORS={'PROFILE_CONFIG_UNAVAILABLE','AI_WORKFLOW_UNAVAILABLE','AI_CONFIG_STALE','AI_CONFIG_INVALID','AI_PROMPT_MISMATCH','AI_SCHEMA_MISMATCH','AI_CAPABILITY_MISMATCH','MODEL_SECRET_MISSING','MODEL_AUTH_FAILED','SECRET_KEY_UNAVAILABLE'}
SOURCE_ERRORS={'PROFILE_NOT_READY','PROFILE_SOURCE_STALE','PROFILE_SOURCE_INVALID','PROFILE_SOURCE_BUDGET','MODEL_OUTPUT_INVALID'}


class ProfileBuildHandler:
    """所有输入从持久化任务引用及简历事实重新读取，不接受自由提示词。"""
    def __init__(self,service):self.service=service

    def finalization_context(self):
        """身份短锁覆盖run_atomic及其提交；模型调用不持锁。"""
        return self.service.candidates.identity_write()

    def prepare(self,lease):
        """领取后复验当前来源，已有画像直接复用；永久错误不反复调用模型。"""
        tasks=BackgroundJobService(self.service.uow_factory)
        with self.service.uow_factory() as uow:
            job=tasks._owned(uow,lease);refs=dict(job.input_refs)
            cid=refs.get('candidate_id');rid=refs.get('resume_version_id')
            if job.job_type!='profile.build' or job.entity_type!='candidate' or job.entity_id!=cid or type(cid) is not int or type(rid) is not int or cid<=0 or rid<=0:raise DomainError('INVALID_OUTPUT',422,'画像任务来源无效')
        prepared=None;existing_id=None;failure=None
        try:
            with self.service.uow_factory() as uow:
                existing=self.service.current(uow,cid,rid);existing_id=existing.id if existing else None
            if existing_id is None:prepared=self.service.prepare(cid,rid)
        except DomainError as error:
            if error.code in CONFIG_ERRORS:failure='PROFILE_CONFIG_UNAVAILABLE'
            elif error.code in SOURCE_ERRORS:failure='INVALID_OUTPUT' if error.code in {'MODEL_OUTPUT_INVALID','PROFILE_SOURCE_INVALID','PROFILE_SOURCE_BUDGET'} else 'DEPENDENCY_UNAVAILABLE'
            else:raise
        def finalize(uow,job):
            if job.input_refs!=refs or job.entity_id!=cid:raise DomainError('PROFILE_SOURCE_STALE',409,'画像任务来源已变化')
            if failure:return TerminalJobFailure(failure)
            current=self.service.current(uow,cid,rid)
            if current is not None:return ResultRef('candidate_profile',current.id,200)
            if prepared is None:raise DomainError('PROFILE_SOURCE_STALE',409,'当前画像已变化')
            profile=self.service.finalize(uow,prepared)
            return ResultRef('candidate_profile',profile.id,200)
        return finalize
