"""岗位筛选与匹配：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class EvaluationRun(Base):
    """evaluation_runs：一次粗筛匹配快照。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "evaluation_runs"
    application_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_evaluation_runs_application_id_applications", ondelete='RESTRICT'), nullable=False, comment='人才与岗位招聘关系ID')
    resume_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_evaluation_runs_resume_version_id_resume_versions", ondelete='RESTRICT'), nullable=False, comment='冻结的简历修订ID')
    profile_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidate_profiles.id", name="fk_evaluation_runs_profile_id_candidate_profiles", ondelete='RESTRICT'), nullable=False, comment='评估时冻结的通用人才画像ID')
    job_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("job_versions.id", name="fk_evaluation_runs_job_version_id_job_versions", ondelete='RESTRICT'), nullable=False, comment='评估时冻结的岗位发布版本ID')
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","screening","needs_review","screened_out","matching","matched","evaluation_failed"]}, comment='领域对象运行或审核状态；允许值：pending,screening,needs_review,screened_out,matching,matched,evaluation_failed')
    screening_result: Mapped[str | None] = mapped_column(sa.String(16), nullable=True, info={"allowed_values":["pass","fail","unknown"]}, comment='硬条件筛选结论：通过、不通过或未知；允许值：pass,fail,unknown')
    override_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_evaluation_runs_override_by_users", ondelete='RESTRICT'), nullable=True, comment='人工覆盖筛选结果的HR账号ID')
    override_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='人工覆盖原因；必留审计')
    invitation_mode: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["auto_allowed","manual_only"]}, comment='首次允许自动邀考或仅人工邀请；允许值：auto_allowed,manual_only')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, comment='允许记录的稳定错误码')
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
    """screening_details：粗筛逐条件证据。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "screening_details"
    evaluation_run_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_screening_details_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'), nullable=False, comment='所属粗筛匹配运行ID')
    condition_key: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='岗位条件的稳定键')
    required: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, comment='是否硬性条件；未知不得冒充不满足')
    expected: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='岗位规则期望值')
    actual: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='实际观测值；未知为NULL')
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False, info={"allowed_values":["met","unmet","unknown"]}, comment='筛选或操作结果；允许值：met,unmet,unknown')
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='可追溯的事实证据与来源定位')
    __table_args__ = (
        sa.CheckConstraint("result IN ('met','unmet','unknown')", name="ck_screening_details_result"),
        sa.UniqueConstraint("evaluation_run_id", "condition_key", name="uq_screening_details_evaluation_run_id_condition_key"),
        sa.Index("ix_screening_details_evaluation_run_id", "evaluation_run_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"粗筛逐条件证据"},
    )

class MatchResult(Base):
    """match_results：岗位匹配结果。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "match_results"
    evaluation_run_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_match_results_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'), nullable=False, comment='所属粗筛匹配运行ID')
    ai_run_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("ai_runs.id", name="fk_match_results_ai_run_id_ai_runs", ondelete='RESTRICT'), nullable=True, comment='关联的模型生成运行记录ID')
    total_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2), nullable=True, comment="岗位匹配加权总分（0至100）；不等于考试成绩")
    dimension_scores: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='各匹配维度的分数及依据')
    strengths: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='岗位优势及证据')
    gaps: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='岗位能力差距及证据')
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='可追溯的事实证据与来源定位')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="valid", server_default="valid", info={"allowed_values":["valid","needs_review","failed"]}, comment='领域对象运行或审核状态；允许值：valid,needs_review,failed')
    __table_args__ = (
        sa.UniqueConstraint("evaluation_run_id", name="uq_match_results_evaluation_run_id"),
        sa.CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_match_results_total_score_range"),
        sa.CheckConstraint("state IN ('valid','needs_review','failed')", name="ck_match_results_state"),
        sa.Index("ix_match_results_evaluation_run_id", "evaluation_run_id"),
        sa.Index("ix_match_results_ai_run_id", "ai_run_id"),
        sa.Index("ix_match_results_state_total_score", "state", "total_score"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"岗位匹配结果"},
    )

