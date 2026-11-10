"""固定application.evaluate处理器；身份锁和租约事务共同保护结果。"""
from app.core.errors import DomainError
from app.core.idempotency import ResultRef

class EvaluationHandler:
    """只接受持久化运行引用，不接受客户端条件或自由提示词。"""
    def __init__(self,service):self.service=service

    def finalization_context(self):
        """覆盖筛选到提交的身份写边界。"""
        return self.service.candidates.identity_write()

    def __call__(self,uow,job):
        """复验任务全部来源指针后在原事务完成确定性筛选。"""
        from app.evaluation.models import EvaluationRun
        from app.recruitment.models import Application
        from app.talents.identity_resolver import CanonicalResolver
        run=uow.session.get(EvaluationRun,job.input_refs.get('evaluation_id'))
        if run is None:raise DomainError('INVALID_OUTPUT',422,'评估任务引用无效')
        app=uow.session.get(Application,run.application_id)
        cid=job.input_refs.get('candidate_id')
        if type(cid) is not int or cid<=0 or CanonicalResolver().resolve(uow,cid).root_id!=CanonicalResolver().resolve(uow,app.candidate_id).root_id:
            raise DomainError('INVALID_OUTPUT',422,'评估任务身份不一致')
        # 合并只改变根身份；原任务引用及不可变版本仍然有效。
        expected={'evaluation_id':run.id,'candidate_id':cid,'job_id':app.job_id,'resume_version_id':run.resume_version_id,'profile_id':run.profile_id,'job_version_id':run.job_version_id}
        if job.job_type!='application.evaluate' or job.entity_type!='application' or job.entity_id!=app.id or job.input_refs!=expected:raise DomainError('INVALID_OUTPUT',422,'评估任务来源不一致')
        self.service.screen_in(uow,run.id)
        return ResultRef('evaluation',run.id,200)
