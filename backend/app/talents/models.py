from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Candidate(Base):
    __tablename__ = "candidates"
    display_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(sa.String(254), nullable=True)
    email_normalized: Mapped[str | None] = mapped_column(sa.String(254, collation='utf8mb4_bin'), nullable=True)
    email_valid: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0")
    phone: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    phone_normalized: Mapped[str | None] = mapped_column(sa.String(64, collation='utf8mb4_bin'), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending_email", server_default="pending_email", info={"allowed_values":["pending_email","duplicate_review","ready","archived","merged"]})
    current_resume_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_candidates_current_resume_version_id_resume_versions", ondelete='RESTRICT', use_alter=True), nullable=True)
    current_profile_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidate_profiles.id", name="fk_candidates_current_profile_id_candidate_profiles", ondelete='RESTRICT', use_alter=True), nullable=True)
    merged_into_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_candidates_merged_into_id_candidates", ondelete='RESTRICT'), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("status IN ('pending_email','duplicate_review','ready','archived','merged')", name="ck_candidates_status"),
        sa.Index("ix_candidates_current_resume_version_id", "current_resume_version_id"),
        sa.Index("ix_candidates_current_profile_id", "current_profile_id"),
        sa.Index("ix_candidates_merged_into_id", "merged_into_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"人才身份"},
    )

class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    candidate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_resume_versions_candidate_id_candidates", ondelete='RESTRICT'), nullable=False)
    file_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("stored_files.id", name="fk_resume_versions_file_id_stored_files", ondelete='RESTRICT'), nullable=False)
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    parent_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_resume_versions_parent_version_id_resume_versions", ondelete='RESTRICT'), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(mysql.LONGTEXT(), nullable=True)
    structured_data: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    field_sources: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    parser_revision: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="extracted", server_default="extracted", info={"allowed_values":["extracted","confirmed","superseded"]})
    change_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
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
    __tablename__ = "candidate_profiles"
    candidate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_candidate_profiles_candidate_id_candidates", ondelete='RESTRICT'), nullable=False)
    resume_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_candidate_profiles_resume_version_id_resume_versions", ondelete='RESTRICT'), nullable=False)
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    summary: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    skills: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    experiences: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    source_record_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    ai_run_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("ai_runs.id", name="fk_candidate_profiles_ai_run_id_ai_runs", ondelete='RESTRICT'), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_candidate_profiles_confirmed_by_users", ondelete='RESTRICT'), nullable=True)
    __table_args__ = (
        sa.UniqueConstraint("candidate_id", "version_no", name="uq_candidate_profiles_candidate_id_version_no"),
        sa.Index("ix_candidate_profiles_candidate_id", "candidate_id"),
        sa.Index("ix_candidate_profiles_resume_version_id", "resume_version_id"),
        sa.Index("ix_candidate_profiles_ai_run_id", "ai_run_id"),
        sa.Index("ix_candidate_profiles_confirmed_by", "confirmed_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"通用人才画像版本"},
    )

class DuplicateCase(Base):
    __tablename__ = "duplicate_cases"
    candidate_a_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_duplicate_cases_candidate_a_id_candidates", ondelete='RESTRICT'), nullable=False)
    candidate_b_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_duplicate_cases_candidate_b_id_candidates", ondelete='RESTRICT'), nullable=False)
    evidence: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","same_person","different_person"]})
    resolved_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_duplicate_cases_resolved_by_users", ondelete='RESTRICT'), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("status IN ('pending','same_person','different_person')", name="ck_duplicate_cases_status"),
        sa.UniqueConstraint("candidate_a_id", "candidate_b_id", name="uq_duplicate_cases_candidate_a_id_candidate_b_id"),
        sa.Index("ix_duplicate_cases_candidate_a_id", "candidate_a_id"),
        sa.Index("ix_duplicate_cases_candidate_b_id", "candidate_b_id"),
        sa.Index("ix_duplicate_cases_resolved_by", "resolved_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"疑似重复与合并审计"},
    )

