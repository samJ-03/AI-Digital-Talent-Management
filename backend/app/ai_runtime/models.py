from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ModelConfig(Base):
    __tablename__ = "model_configs"
    logical_key: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False)
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    provider_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["ollama","compatible_http"]})
    base_url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    model_name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    model_digest: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    capabilities: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    embedding_dimension: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), nullable=True)
    secret_ciphertext: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0")
    __table_args__ = (
        sa.CheckConstraint("provider_type IN ('ollama','compatible_http')", name="ck_model_configs_provider_type"),
        sa.UniqueConstraint("logical_key", "revision_no", name="uq_model_configs_logical_key_revision_no"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"模型连接及修订"},
    )

class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    task_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    output_schema: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","published"]})
    published_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_prompt_versions_published_by_users", ondelete='RESTRICT'), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("status IN ('draft','published')", name="ck_prompt_versions_status"),
        sa.UniqueConstraint("task_type", "revision_no", name="uq_prompt_versions_task_type_revision_no"),
        sa.Index("ix_prompt_versions_published_by", "published_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"提示词版本"},
    )

class WorkflowConfig(Base):
    __tablename__ = "workflow_configs"
    task_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("model_configs.id", name="fk_workflow_configs_model_config_id_model_configs", ondelete='RESTRICT'), nullable=True)
    prompt_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("prompt_versions.id", name="fk_workflow_configs_prompt_version_id_prompt_versions", ondelete='RESTRICT'), nullable=True)
    enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0")
    timeout_seconds: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    max_retries: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    config_revision: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("task_type", name="uq_workflow_configs_task_type"),
        sa.Index("ix_workflow_configs_model_config_id", "model_config_id"),
        sa.Index("ix_workflow_configs_prompt_version_id", "prompt_version_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"固定流程配置"},
    )

class AiRun(Base):
    __tablename__ = "ai_runs"
    background_job_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("background_jobs.id", name="fk_ai_runs_background_job_id_background_jobs", ondelete='RESTRICT'), nullable=True)
    task_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    model_config_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("model_configs.id", name="fk_ai_runs_model_config_id_model_configs", ondelete='RESTRICT'), nullable=False)
    prompt_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("prompt_versions.id", name="fk_ai_runs_prompt_version_id_prompt_versions", ondelete='RESTRICT'), nullable=False)
    input_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False)
    source_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    validated_output: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="running", server_default="running", info={"allowed_values":["running","succeeded","invalid","failed"]})
    duration_ms: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    __table_args__ = (
        sa.CheckConstraint("state IN ('running','succeeded','invalid','failed')", name="ck_ai_runs_state"),
        sa.Index("ix_ai_runs_background_job_id", "background_job_id"),
        sa.Index("ix_ai_runs_model_config_id", "model_config_id"),
        sa.Index("ix_ai_runs_prompt_version_id", "prompt_version_id"),
        sa.Index("ix_ai_runs_task_type_created_at", "task_type", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"模型运行证据"},
    )

