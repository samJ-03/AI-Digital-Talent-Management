"""招聘岗位：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Job(Base):
    """jobs：岗位主对象。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "jobs"
    department_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_jobs_department_id_departments", ondelete='RESTRICT'), nullable=False, comment='归属部门ID；用于部门数据权限')
    owner_hr_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_jobs_owner_hr_id_users", ondelete='RESTRICT'), nullable=False, comment='岗位负责HR账号ID')
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False, comment='岗位或知识标题')
    headcount: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='计划招聘人数；必须大于0')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","open","paused","closed"]}, comment='业务生命周期状态；允许值：draft,open,paused,closed')
    current_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("job_versions.id", name="fk_jobs_current_version_id_job_versions", ondelete='RESTRICT', use_alter=True), nullable=True, comment='当前发布版本ID；服务层校验属于本主对象')
    auto_invite_enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0", comment='自动邀考开关；新岗位默认关闭')
    __table_args__ = (
        sa.CheckConstraint("headcount > 0", name="ck_jobs_headcount_positive"),
        sa.CheckConstraint("status IN ('draft','open','paused','closed')", name="ck_jobs_status"),
        sa.Index("ix_jobs_department_id", "department_id"),
        sa.Index("ix_jobs_owner_hr_id", "owner_hr_id"),
        sa.Index("ix_jobs_current_version_id", "current_version_id"),
        sa.Index("ix_jobs_department_id_status", "department_id", "status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"岗位主对象"},
    )

class JobVersion(Base):
    """job_versions：岗位发布版本。发布内容不可变，关联试卷须验证归属与可见性。"""
    __tablename__ = "job_versions"
    job_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("jobs.id", name="fk_job_versions_job_id_jobs", ondelete='RESTRICT'), nullable=False, comment='所属招聘岗位ID')
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='同一主对象下的业务版本序号')
    description: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='业务说明正文')
    conditions: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='必选或优选的结构化岗位条件')
    match_weights: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='匹配维度权重；总和必须为100')
    invite_threshold: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False, comment='自动邀考匹配分参考阈值（0至100）')
    paper_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("paper_versions.id", name="fk_job_versions_paper_version_id_paper_versions", ondelete='RESTRICT'), nullable=True, comment='固定发布试卷版本ID')
    invite_valid_hours: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='邀请有效时长（小时）')
    mail_template: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='岗位邀考模板结构')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","published"]}, comment='业务生命周期状态；允许值：draft,published')
    published_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_job_versions_published_by_users", ondelete='RESTRICT'), nullable=True, comment='发布者后台账号ID')
    published_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='版本发布时间（UTC）')
    __table_args__ = (
        sa.CheckConstraint("invite_threshold >= 0 AND invite_threshold <= 100", name="ck_job_versions_invite_threshold_range"),
        sa.CheckConstraint("invite_valid_hours > 0", name="ck_job_versions_invite_valid_hours_positive"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_job_versions_status"),
        sa.UniqueConstraint("job_id", "version_no", name="uq_job_versions_job_id_version_no"),
        sa.Index("ix_job_versions_job_id", "job_id"),
        sa.Index("ix_job_versions_paper_version_id", "paper_version_id"),
        sa.Index("ix_job_versions_published_by", "published_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"岗位发布版本"},
    )

