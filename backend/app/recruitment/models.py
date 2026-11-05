from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Application(Base):
    __tablename__ = "applications"
    candidate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_applications_candidate_id_candidates", ondelete='RESTRICT'), nullable=False)
    job_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("jobs.id", name="fk_applications_job_id_jobs", ondelete='RESTRICT'), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["import","talent_pool"]})
    stage: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["evaluating","assessment","hr_review","interview_pending","interview_passed","offer_pending","hired","rejected","withdrawn"]})
    current_evaluation_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_applications_current_evaluation_id_evaluation_runs", ondelete='RESTRICT', use_alter=True), nullable=True)
    current_round: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=1, server_default="1")
    ended_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    relationship_state: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["active","merged"]})
    canonical_application_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_applications_canonical_application_id_applications", ondelete='RESTRICT'), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("source IN ('import','talent_pool')", name="ck_applications_source"),
        sa.CheckConstraint("stage IN ('evaluating','assessment','hr_review','interview_pending','interview_passed','offer_pending','hired','rejected','withdrawn')", name="ck_applications_stage"),
        sa.CheckConstraint("relationship_state IN ('active','merged')", name="ck_applications_relationship_state"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_id_job_id"),
        sa.Index("ix_applications_candidate_id", "candidate_id"),
        sa.Index("ix_applications_job_id", "job_id"),
        sa.Index("ix_applications_current_evaluation_id", "current_evaluation_id"),
        sa.Index("ix_applications_canonical_application_id", "canonical_application_id"),
        sa.Index("ix_applications_job_id_stage", "job_id", "stage"),
        sa.Index("ix_applications_candidate_id_created_at", "candidate_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"人×岗位招聘关系"},
    )

class RecruitmentEvent(Base):
    __tablename__ = "recruitment_events"
    application_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_recruitment_events_application_id_applications", ondelete='RESTRICT'), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    to_stage: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    content: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    actor_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_recruitment_events_actor_id_users", ondelete='RESTRICT'), nullable=False)
    __table_args__ = (
        sa.Index("ix_recruitment_events_application_id", "application_id"),
        sa.Index("ix_recruitment_events_actor_id", "actor_id"),
        sa.Index("ix_recruitment_events_application_id_created_at", "application_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"阶段与面试评价历史"},
    )

