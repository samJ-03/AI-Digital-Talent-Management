from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    application_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_evaluation_runs_application_id_applications", ondelete='RESTRICT'), nullable=False)
    resume_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_evaluation_runs_resume_version_id_resume_versions", ondelete='RESTRICT'), nullable=False)
    profile_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidate_profiles.id", name="fk_evaluation_runs_profile_id_candidate_profiles", ondelete='RESTRICT'), nullable=False)
    job_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("job_versions.id", name="fk_evaluation_runs_job_version_id_job_versions", ondelete='RESTRICT'), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","screening","needs_review","screened_out","matching","matched","evaluation_failed"]})
    screening_result: Mapped[str | None] = mapped_column(sa.String(16), nullable=True, info={"allowed_values":["pass","fail","unknown"]})
    override_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_evaluation_runs_override_by_users", ondelete='RESTRICT'), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    invitation_mode: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["auto_allowed","manual_only"]})
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("state IN ('pending','screening','needs_review','screened_out','matching','matched','evaluation_failed')", name="ck_evaluation_runs_state"),
        sa.CheckConstraint("screening_result IN ('pass','fail','unknown')", name="ck_evaluation_runs_screening_result"),
        sa.CheckConstraint("invitation_mode IN ('auto_allowed','manual_only')", name="ck_evaluation_runs_invitation_mode"),
        sa.Index("ix_evaluation_runs_application_id", "application_id"),
        sa.Index("ix_evaluation_runs_resume_version_id", "resume_version_id"),
        sa.Index("ix_evaluation_runs_profile_id", "profile_id"),
        sa.Index("ix_evaluation_runs_job_version_id", "job_version_id"),
        sa.Index("ix_evaluation_runs_override_by", "override_by"),
        sa.Index("ix_evaluation_runs_application_id_created_at", "application_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"一次粗筛匹配快照"},
    )

class ScreeningDetail(Base):
    __tablename__ = "screening_details"
    evaluation_run_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_screening_details_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'), nullable=False)
    condition_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    required: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    expected: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    actual: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False, info={"allowed_values":["met","unmet","unknown"]})
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    __table_args__ = (
        sa.CheckConstraint("result IN ('met','unmet','unknown')", name="ck_screening_details_result"),
        sa.UniqueConstraint("evaluation_run_id", "condition_key", name="uq_screening_details_evaluation_run_id_condition_key"),
        sa.Index("ix_screening_details_evaluation_run_id", "evaluation_run_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"粗筛逐条件证据"},
    )

class MatchResult(Base):
    __tablename__ = "match_results"
    evaluation_run_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_match_results_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'), nullable=False)
    ai_run_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("ai_runs.id", name="fk_match_results_ai_run_id_ai_runs", ondelete='RESTRICT'), nullable=True)
    total_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2), nullable=True)
    dimension_scores: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    strengths: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    gaps: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="valid", server_default="valid", info={"allowed_values":["valid","needs_review","failed"]})
    __table_args__ = (
        sa.UniqueConstraint("evaluation_run_id", name="uq_match_results_evaluation_run_id"),
        sa.CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_match_results_total_score_range"),
        sa.CheckConstraint("state IN ('valid','needs_review','failed')", name="ck_match_results_state"),
        sa.Index("ix_match_results_evaluation_run_id", "evaluation_run_id"),
        sa.Index("ix_match_results_ai_run_id", "ai_run_id"),
        sa.Index("ix_match_results_state_total_score", "state", "total_score"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"岗位匹配结果"},
    )

