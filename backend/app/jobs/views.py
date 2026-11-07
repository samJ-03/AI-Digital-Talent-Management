"""岗位与版本的允许字段投影。"""
from datetime import timezone
from app.jobs.schemas import JobView,JobVersionView

def job_view(row):
    """只返回岗位元数据，不展开部门私有招聘记录。"""
    return JobView(id=str(row.id),title=row.title,department_id=str(row.department_id),owner_hr_id=str(row.owner_hr_id),
        headcount=row.headcount,status=row.status,current_version_id=str(row.current_version_id) if row.current_version_id else None,
        auto_invite_enabled=row.auto_invite_enabled,version=row.row_version)

def version_view(row):
    """返回当前发布或草稿标准，保留修订身份和UTC发布时间。"""
    return JobVersionView(id=str(row.id),job_id=str(row.job_id),version_no=row.version_no,description=row.description,
        conditions=row.conditions,match_weights=row.match_weights,invite_threshold=row.invite_threshold,
        paper_version_id=str(row.paper_version_id) if row.paper_version_id else None,invite_valid_hours=row.invite_valid_hours,
        mail_template=row.mail_template,status=row.status,published_by=str(row.published_by) if row.published_by else None,
        published_at=row.published_at.replace(tzinfo=timezone.utc) if row.published_at else None,version=row.row_version)
