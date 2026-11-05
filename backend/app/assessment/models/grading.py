from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ScoreReview(Base):
    __tablename__ = "score_reviews"
    answer_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_answers.id", name="fk_score_reviews_answer_id_exam_answers", ondelete='RESTRICT'), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_score_reviews_reviewer_id_users", ondelete='RESTRICT'), nullable=False)
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    previous_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("score >= 0", name="ck_score_reviews_score_nonnegative"),
        sa.UniqueConstraint("answer_id", "revision_no", name="uq_score_reviews_answer_id_revision_no"),
        sa.Index("ix_score_reviews_answer_id", "answer_id"),
        sa.Index("ix_score_reviews_reviewer_id", "reviewer_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"人工主观评分修订"},
    )

class ScoreReport(Base):
    __tablename__ = "score_reports"
    attempt_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_attempts.id", name="fk_score_reports_attempt_id_exam_attempts", ondelete='RESTRICT'), nullable=False)
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    objective_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)
    subjective_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)
    item_score_snapshot: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    confirmed_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_score_reports_confirmed_by_users", ondelete='RESTRICT'), nullable=True)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("attempt_id", "version_no", name="uq_score_reports_attempt_id_version_no"),
        sa.Index("ix_score_reports_attempt_id", "attempt_id"),
        sa.Index("ix_score_reports_confirmed_by", "confirmed_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"正式成绩不可变版本"},
    )

