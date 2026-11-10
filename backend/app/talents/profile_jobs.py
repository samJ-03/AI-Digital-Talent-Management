"""所有画像生产者共用的活动任务判定；调用方必须持有身份短锁。"""
from sqlalchemy import select
from app.runtime.models import BackgroundJob


def active_profile_job(session,candidate_id: int,resume_version_id: int) -> int|None:
    """按来源引用识别任务而非猜测幂等键，覆盖导入、恢复与联系人生产者。"""
    stmt=select(BackgroundJob).where(BackgroundJob.job_type=='profile.build',BackgroundJob.entity_type=='candidate',BackgroundJob.entity_id==candidate_id,BackgroundJob.state.in_(['queued','running','retry'])).order_by(BackgroundJob.id)
    for job in session.scalars(stmt):
        if job.input_refs.get('candidate_id')==candidate_id and job.input_refs.get('resume_version_id')==resume_version_id:return job.id
    return None
