from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class QuestionBank(Base):
    __tablename__ = "question_banks"
    department_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_question_banks_department_id_departments", ondelete='RESTRICT'), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","archived"]})
    created_by: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_question_banks_created_by_users", ondelete='RESTRICT'), nullable=False)
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','archived')", name="ck_question_banks_status"),
        sa.Index("ix_question_banks_department_id", "department_id"),
        sa.Index("ix_question_banks_created_by", "created_by"),
        sa.Index("ix_question_banks_department_id_status", "department_id", "status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"题库"},
    )

class Question(Base):
    __tablename__ = "questions"
    bank_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("question_banks.id", name="fk_questions_bank_id_question_banks", ondelete='RESTRICT'), nullable=False)
    logical_key: Mapped[str] = mapped_column(sa.CHAR(36, collation='utf8mb4_bin'), nullable=False)
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    question_type: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["single_choice","multiple_choice","short_answer"]})
    stem: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    options: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    answer_key: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    rubric: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    reference_sources: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","approved","archived"]})
    __table_args__ = (
        sa.CheckConstraint("question_type IN ('single_choice','multiple_choice','short_answer')", name="ck_questions_question_type"),
        sa.CheckConstraint("state IN ('draft','approved','archived')", name="ck_questions_state"),
        sa.UniqueConstraint("logical_key", "revision_no", name="uq_questions_logical_key_revision_no"),
        sa.Index("ix_questions_bank_id", "bank_id"),
        sa.Index("ix_questions_bank_id_state", "bank_id", "state"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"题库题目修订"},
    )

class Paper(Base):
    __tablename__ = "papers"
    department_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_papers_department_id_departments", ondelete='RESTRICT'), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    created_by: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_papers_created_by_users", ondelete='RESTRICT'), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","archived"]})
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','archived')", name="ck_papers_status"),
        sa.Index("ix_papers_department_id", "department_id"),
        sa.Index("ix_papers_created_by", "created_by"),
        sa.Index("ix_papers_department_id_status", "department_id", "status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"试卷主对象"},
    )

class PaperVersion(Base):
    __tablename__ = "paper_versions"
    paper_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("papers.id", name="fk_paper_versions_paper_id_papers", ondelete='RESTRICT'), nullable=False)
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)
    reference_pass_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","published"]})
    published_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_paper_versions_published_by_users", ondelete='RESTRICT'), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("duration_minutes > 0", name="ck_paper_versions_duration_minutes_positive"),
        sa.CheckConstraint("total_score > 0", name="ck_paper_versions_total_score_positive"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_paper_versions_status"),
        sa.UniqueConstraint("paper_id", "version_no", name="uq_paper_versions_paper_id_version_no"),
        sa.Index("ix_paper_versions_paper_id", "paper_id"),
        sa.Index("ix_paper_versions_published_by", "published_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"试卷版本"},
    )

class PaperItem(Base):
    __tablename__ = "paper_items"
    paper_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("paper_versions.id", name="fk_paper_items_paper_version_id_paper_versions", ondelete='RESTRICT'), nullable=False)
    source_question_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("questions.id", name="fk_paper_items_source_question_id_questions", ondelete='RESTRICT'), nullable=True)
    position_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    question_type: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    stem: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    options: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    max_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False)
    answer_key: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    rubric: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    reference_sources: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    __table_args__ = (
        sa.CheckConstraint("max_score >= 0", name="ck_paper_items_max_score_nonnegative"),
        sa.UniqueConstraint("paper_version_id", "position_no", name="uq_paper_items_paper_version_id_position_no"),
        sa.Index("ix_paper_items_paper_version_id", "paper_version_id"),
        sa.Index("ix_paper_items_source_question_id", "source_question_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"冻结试题与评分标准"},
    )

