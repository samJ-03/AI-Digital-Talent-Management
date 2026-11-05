from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Job(Base):
    __tablename__ = "jobs"
    department_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_jobs_department_id_departments", ondelete='RESTRICT'), nullable=False)
    owner_hr_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_jobs_owner_hr_id_users", ondelete='RESTRICT'), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    headcount: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","open","paused","closed"]})
    current_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("job_versions.id", name="fk_jobs_current_version_id_job_versions", ondelete='RESTRICT', use_alter=True), nullable=True)
    auto_invite_enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0")
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
    __tablename__ = "job_versions"
    job_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("jobs.id", name="fk_job_versions_job_id_jobs", ondelete='RESTRICT'), nullable=False)
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    conditions: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    match_weights: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    invite_threshold: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False)
    paper_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("paper_versions.id", name="fk_job_versions_paper_version_id_paper_versions", ondelete='RESTRICT'), nullable=True)
    invite_valid_hours: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    mail_template: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","published"]})
    published_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_job_versions_published_by_users", ondelete='RESTRICT'), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
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

