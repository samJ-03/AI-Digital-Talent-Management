from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    application_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_exam_attempts_application_id_applications", ondelete='RESTRICT'), nullable=False)
    evaluation_run_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_exam_attempts_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'), nullable=False)
    paper_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("paper_versions.id", name="fk_exam_attempts_paper_version_id_paper_versions", ondelete='RESTRICT'), nullable=False)
    round_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    email_snapshot: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    invitation_token_hash: Mapped[str | None] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=True)
    invite_status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","sent","delivery_failed","delivery_unknown","revoked","expired"]})
    valid_until: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="not_started", server_default="not_started", info={"allowed_values":["not_started","in_progress","submitted","grading","pending_review","finalized","no_show"]})
    started_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    submission_reason: Mapped[str | None] = mapped_column(sa.String(24), nullable=True, info={"allowed_values":["manual","timeout"]})
    objective_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    final_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    finalized_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_exam_attempts_finalized_by_users", ondelete='RESTRICT'), nullable=True)
    current_score_report_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("score_reports.id", name="fk_exam_attempts_current_score_report_id_score_reports", ondelete='RESTRICT', use_alter=True), nullable=True)
    __table_args__ = (
        sa.UniqueConstraint("invitation_token_hash", name="uq_exam_attempts_invitation_token_hash"),
        sa.CheckConstraint("invite_status IN ('pending','sent','delivery_failed','delivery_unknown','revoked','expired')", name="ck_exam_attempts_invite_status"),
        sa.CheckConstraint("state IN ('not_started','in_progress','submitted','grading','pending_review','finalized','no_show')", name="ck_exam_attempts_state"),
        sa.CheckConstraint("submission_reason IN ('manual','timeout')", name="ck_exam_attempts_submission_reason"),
        sa.UniqueConstraint("application_id", "round_no", name="uq_exam_attempts_application_id_round_no"),
        sa.Index("ix_exam_attempts_application_id", "application_id"),
        sa.Index("ix_exam_attempts_evaluation_run_id", "evaluation_run_id"),
        sa.Index("ix_exam_attempts_paper_version_id", "paper_version_id"),
        sa.Index("ix_exam_attempts_finalized_by", "finalized_by"),
        sa.Index("ix_exam_attempts_current_score_report_id", "current_score_report_id"),
        sa.Index("ix_exam_attempts_state_deadline_at", "state", "deadline_at"),
        sa.Index("ix_exam_attempts_invite_status_valid_until", "invite_status", "valid_until"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"邀请与个人考次"},
    )

class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    attempt_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_attempts.id", name="fk_exam_answers_attempt_id_exam_attempts", ondelete='RESTRICT'), nullable=False)
    paper_item_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("paper_items.id", name="fk_exam_answers_paper_item_id_paper_items", ondelete='RESTRICT'), nullable=False)
    answer: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    answer_revision: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    saved_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    objective_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    ai_suggested_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    ai_reason: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    review_state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="not_required", server_default="not_required", info={"allowed_values":["not_required","pending","reviewed"]})
    final_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    ai_run_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("ai_runs.id", name="fk_exam_answers_ai_run_id_ai_runs", ondelete='RESTRICT'), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("review_state IN ('not_required','pending','reviewed')", name="ck_exam_answers_review_state"),
        sa.UniqueConstraint("attempt_id", "paper_item_id", name="uq_exam_answers_attempt_id_paper_item_id"),
        sa.Index("ix_exam_answers_attempt_id", "attempt_id"),
        sa.Index("ix_exam_answers_paper_item_id", "paper_item_id"),
        sa.Index("ix_exam_answers_ai_run_id", "ai_run_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"个人答案与评分"},
    )

