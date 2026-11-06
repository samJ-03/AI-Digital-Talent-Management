"""题库、试卷与考试：实现papers领域协作。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class QuestionBank(Base):
    """question_banks：题库。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "question_banks"
    department_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_question_banks_department_id_departments", ondelete='RESTRICT'), nullable=False, comment='归属部门ID；用于部门数据权限')
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False, comment='业务对象名称')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","archived"]}, comment='业务生命周期状态；允许值：active,archived')
    created_by: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_question_banks_created_by_users", ondelete='RESTRICT'), nullable=False, comment='创建者后台账号ID')
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','archived')", name="ck_question_banks_status"),
        sa.Index("ix_question_banks_department_id", "department_id"),
        sa.Index("ix_question_banks_created_by", "created_by"),
        sa.Index("ix_question_banks_department_id_status", "department_id", "status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"题库"},
    )

class Question(Base):
    """questions：题库题目修订。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "questions"
    bank_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("question_banks.id", name="fk_questions_bank_id_question_banks", ondelete='RESTRICT'), nullable=False, comment='所属题库ID')
    logical_key: Mapped[str] = mapped_column(sa.CHAR(36, collation='utf8mb4_bin'), nullable=False, comment='跨修订保持稳定的逻辑标识')
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='不可变配置或题目修订序号')
    question_type: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["single_choice","multiple_choice","short_answer"]}, comment='题型；允许值：single_choice,multiple_choice,short_answer')
    stem: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='题干正文')
    options: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='题目选项结构')
    answer_key: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='标准答案；仅授权HR和评分流程可见')
    rubric: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='冻结的评分量表；候选人不可见')
    reference_sources: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='题目引用的知识或资料来源')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","approved","archived"]}, comment='领域对象运行或审核状态；允许值：draft,approved,archived')
    __table_args__ = (
        sa.CheckConstraint("question_type IN ('single_choice','multiple_choice','short_answer')", name="ck_questions_question_type"),
        sa.CheckConstraint("state IN ('draft','approved','archived')", name="ck_questions_state"),
        sa.UniqueConstraint("logical_key", "revision_no", name="uq_questions_logical_key_revision_no"),
        sa.Index("ix_questions_bank_id", "bank_id"),
        sa.Index("ix_questions_bank_id_state", "bank_id", "state"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"题库题目修订"},
    )

class Paper(Base):
    """papers：试卷主对象。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "papers"
    department_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_papers_department_id_departments", ondelete='RESTRICT'), nullable=False, comment='归属部门ID；用于部门数据权限')
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False, comment='业务对象名称')
    created_by: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_papers_created_by_users", ondelete='RESTRICT'), nullable=False, comment='创建者后台账号ID')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","archived"]}, comment='业务生命周期状态；允许值：active,archived')
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','archived')", name="ck_papers_status"),
        sa.Index("ix_papers_department_id", "department_id"),
        sa.Index("ix_papers_created_by", "created_by"),
        sa.Index("ix_papers_department_id_status", "department_id", "status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"试卷主对象"},
    )

class PaperVersion(Base):
    """paper_versions：试卷版本。发布后内容冻结，历史考次继续引用原版本。"""
    __tablename__ = "paper_versions"
    paper_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("papers.id", name="fk_paper_versions_paper_id_papers", ondelete='RESTRICT'), nullable=False, comment='所属试卷主对象ID')
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='同一主对象下的业务版本序号')
    duration_minutes: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='考试时长（分钟）')
    total_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False, comment="本版试卷满分；等于冻结题目满分之和")
    reference_pass_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), nullable=True, comment='试卷参考通过线；不自动决定淘汰')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","published"]}, comment='业务生命周期状态；允许值：draft,published')
    published_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_paper_versions_published_by_users", ondelete='RESTRICT'), nullable=True, comment='发布者后台账号ID')
    published_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='版本发布时间（UTC）')
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
    """paper_items：冻结试题与评分标准。冻结题干、答案和量表，候选人只能读取白名单投影。"""
    __tablename__ = "paper_items"
    paper_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("paper_versions.id", name="fk_paper_items_paper_version_id_paper_versions", ondelete='RESTRICT'), nullable=False, comment='固定发布试卷版本ID')
    source_question_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("questions.id", name="fk_paper_items_source_question_id_questions", ondelete='RESTRICT'), nullable=True, comment='发布试卷所引用的已批准题目修订ID')
    position_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='试题显示顺序')
    question_type: Mapped[str] = mapped_column(sa.String(24), nullable=False, comment='题型')
    stem: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='题干正文')
    options: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='题目选项结构')
    max_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), nullable=False, comment='本题冻结满分')
    answer_key: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='标准答案；仅授权HR和评分流程可见')
    rubric: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='冻结的评分量表；候选人不可见')
    reference_sources: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='题目引用的知识或资料来源')
    __table_args__ = (
        sa.CheckConstraint("max_score >= 0", name="ck_paper_items_max_score_nonnegative"),
        sa.UniqueConstraint("paper_version_id", "position_no", name="uq_paper_items_paper_version_id_position_no"),
        sa.Index("ix_paper_items_paper_version_id", "paper_version_id"),
        sa.Index("ix_paper_items_source_question_id", "source_question_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"冻结试题与评分标准"},
    )

