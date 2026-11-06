"""题库、试卷与考试：实现grading领域协作。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ScoreReview(Base):
    """score_reviews：人工主观评分修订。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "score_reviews"
    answer_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_answers.id", name="fk_score_reviews_answer_id_exam_answers", ondelete='RESTRICT'), nullable=False, comment='关联答卷答案ID')
    reviewer_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_score_reviews_reviewer_id_users", ondelete='RESTRICT'), nullable=False, comment='评分复核者账号ID')
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='不可变配置或题目修订序号')
    score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False, comment='本次评分或复核分数')
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='人工操作或复核理由')
    previous_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True, comment='本次复核前的单题分数')
    __table_args__ = (
        sa.CheckConstraint("score >= 0", name="ck_score_reviews_score_nonnegative"),
        sa.UniqueConstraint("answer_id", "revision_no", name="uq_score_reviews_answer_id_revision_no"),
        sa.Index("ix_score_reviews_answer_id", "answer_id"),
        sa.Index("ix_score_reviews_reviewer_id", "reviewer_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"人工主观评分修订"},
    )

class ScoreReport(Base):
    """score_reports：正式成绩不可变版本。正式成绩为不可变快照，修改必须生成新版本。"""
    __tablename__ = "score_reports"
    attempt_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_attempts.id", name="fk_score_reports_attempt_id_exam_attempts", ondelete='RESTRICT'), nullable=False, comment='关联考试轮次ID')
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='同一主对象下的业务版本序号')
    objective_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False, comment='客观题得分小计')
    subjective_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False, comment='主观题正式得分小计')
    total_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False, comment="本次确认的考试正式总分")
    item_score_snapshot: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='正式成绩冻结的逐题评分快照')
    confirmed_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_score_reports_confirmed_by_users", ondelete='RESTRICT'), nullable=True, comment='人工确认者账号ID')
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='人工操作或复核理由')
    __table_args__ = (
        sa.UniqueConstraint("attempt_id", "version_no", name="uq_score_reports_attempt_id_version_no"),
        sa.Index("ix_score_reports_attempt_id", "attempt_id"),
        sa.Index("ix_score_reports_confirmed_by", "confirmed_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"正式成绩不可变版本"},
    )

