"""共享人才档案：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Candidate(Base):
    """candidates：人才身份。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "candidates"
    display_name: Mapped[str] = mapped_column(sa.String(120), nullable=False, comment='人才显示姓名')
    email: Mapped[str | None] = mapped_column(sa.String(254), nullable=True, comment='人才原始邮箱；未补齐时可空')
    email_normalized: Mapped[str | None] = mapped_column(sa.String(254, collation='utf8mb4_bin'), nullable=True, comment='规范化邮箱；不擅自删除本地部分点号或加号')
    email_valid: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0", comment='邮箱格式已校验标记；不等于验证收件人身份')
    phone: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, comment='原始联系电话')
    phone_normalized: Mapped[str | None] = mapped_column(sa.String(64, collation='utf8mb4_bin'), nullable=True, comment='规范化联系电话；不作为唯一身份约束')
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending_email", server_default="pending_email", info={"allowed_values":["pending_email","duplicate_review","ready","archived","merged"]}, comment='业务生命周期状态；允许值：pending_email,duplicate_review,ready,archived,merged')
    current_resume_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_candidates_current_resume_version_id_resume_versions", ondelete='RESTRICT', use_alter=True), nullable=True, comment='当前简历修订ID')
    current_profile_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidate_profiles.id", name="fk_candidates_current_profile_id_candidate_profiles", ondelete='RESTRICT', use_alter=True), nullable=True, comment='当前通用人才画像版本ID')
    merged_into_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_candidates_merged_into_id_candidates", ondelete='RESTRICT'), nullable=True, comment='合并后保留的人才ID；不得形成环')
    __table_args__ = (
        sa.CheckConstraint("status IN ('pending_email','duplicate_review','ready','archived','merged')", name="ck_candidates_status"),
        sa.Index("ix_candidates_current_resume_version_id", "current_resume_version_id"),
        sa.Index("ix_candidates_current_profile_id", "current_profile_id"),
        sa.Index("ix_candidates_merged_into_id", "merged_into_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"人才身份"},
    )

class ResumeVersion(Base):
    """resume_versions：简历与校正版本。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "resume_versions"
    candidate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_resume_versions_candidate_id_candidates", ondelete='RESTRICT'), nullable=False, comment='所属人才身份ID')
    file_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("stored_files.id", name="fk_resume_versions_file_id_stored_files", ondelete='RESTRICT'), nullable=False, comment='私有原始文件ID')
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='同一主对象下的业务版本序号')
    parent_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_resume_versions_parent_version_id_resume_versions", ondelete='RESTRICT'), nullable=True, comment='来源简历修订ID')
    raw_text: Mapped[str | None] = mapped_column(mysql.LONGTEXT(), nullable=True, comment='解析得到的简历原文；按敏感数据授权访问')
    structured_data: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='经过类型校验的结构化简历事实')
    field_sources: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='结构化简历各字段的页码或段落证据')
    parser_revision: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='解析器或解析流程修订')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="extracted", server_default="extracted", info={"allowed_values":["extracted","confirmed","superseded"]}, comment='领域对象运行或审核状态；允许值：extracted,confirmed,superseded')
    change_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='创建修订的变更原因')
    __table_args__ = (
        sa.CheckConstraint("state IN ('extracted','confirmed','superseded')", name="ck_resume_versions_state"),
        sa.UniqueConstraint("candidate_id", "version_no", name="uq_resume_versions_candidate_id_version_no"),
        sa.Index("ix_resume_versions_candidate_id", "candidate_id"),
        sa.Index("ix_resume_versions_file_id", "file_id"),
        sa.Index("ix_resume_versions_parent_version_id", "parent_version_id"),
        sa.Index("ix_resume_versions_candidate_id_created_at", "candidate_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"简历与校正版本"},
    )

class CandidateProfile(Base):
    """candidate_profiles：通用人才画像版本。共享画像只包含简历事实，不混入部门私有考试或面试评价。"""
    __tablename__ = "candidate_profiles"
    candidate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_candidate_profiles_candidate_id_candidates", ondelete='RESTRICT'), nullable=False, comment='所属人才身份ID')
    resume_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_candidate_profiles_resume_version_id_resume_versions", ondelete='RESTRICT'), nullable=False, comment='冻结的简历修订ID')
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='同一主对象下的业务版本序号')
    summary: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='通用画像摘要或审计摘要；按所属表授权')
    skills: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='来自简历的技能事实')
    experiences: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='来自简历的经历事实')
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='可追溯的事实证据与来源定位')
    source_record_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='共享画像只允许简历来源引用；禁止部门私有考试和面试评价')
    ai_run_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("ai_runs.id", name="fk_candidate_profiles_ai_run_id_ai_runs", ondelete='RESTRICT'), nullable=True, comment='关联的模型生成运行记录ID')
    confirmed_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_candidate_profiles_confirmed_by_users", ondelete='RESTRICT'), nullable=True, comment='人工确认者账号ID')
    __table_args__ = (
        sa.UniqueConstraint("candidate_id", "version_no", name="uq_candidate_profiles_candidate_id_version_no"),
        sa.Index("ix_candidate_profiles_candidate_id", "candidate_id"),
        sa.Index("ix_candidate_profiles_resume_version_id", "resume_version_id"),
        sa.Index("ix_candidate_profiles_ai_run_id", "ai_run_id"),
        sa.Index("ix_candidate_profiles_confirmed_by", "confirmed_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"通用人才画像版本"},
    )

class DuplicateCase(Base):
    """duplicate_cases：疑似重复与合并审计。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "duplicate_cases"
    candidate_a_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_duplicate_cases_candidate_a_id_candidates", ondelete='RESTRICT'), nullable=False, comment='疑似重复人才A的ID；小于B')
    candidate_b_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_duplicate_cases_candidate_b_id_candidates", ondelete='RESTRICT'), nullable=False, comment='疑似重复人才B的ID；大于A')
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='可追溯的事实证据与来源定位')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","same_person","different_person"]}, comment='业务生命周期状态；允许值：pending,same_person,different_person')
    resolved_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_duplicate_cases_resolved_by_users", ondelete='RESTRICT'), nullable=True, comment='重复身份判定者账号ID')
    resolution_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='疑似重复身份的人工判定理由')
    __table_args__ = (
        sa.CheckConstraint("status IN ('pending','same_person','different_person')", name="ck_duplicate_cases_status"),
        sa.UniqueConstraint("candidate_a_id", "candidate_b_id", name="uq_duplicate_cases_candidate_a_id_candidate_b_id"),
        sa.Index("ix_duplicate_cases_candidate_a_id", "candidate_a_id"),
        sa.Index("ix_duplicate_cases_candidate_b_id", "candidate_b_id"),
        sa.Index("ix_duplicate_cases_resolved_by", "resolved_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"疑似重复与合并审计"},
    )

