"""模型配置与受控AI执行：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ModelConfig(Base):
    """model_configs：模型连接及修订。连接修订不可变，凭据仅保存密文；云端权重digest允许为空。"""
    __tablename__ = "model_configs"
    logical_key: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False, comment='跨修订保持稳定的逻辑标识')
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='不可变配置或题目修订序号')
    provider_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["ollama","compatible_http"]}, comment='受支持的模型协议类型；允许值：ollama,compatible_http')
    base_url: Mapped[str] = mapped_column(sa.String(500), nullable=False, comment='经供应商白名单校验的服务地址')
    model_name: Mapped[str] = mapped_column(sa.String(150), nullable=False, comment='供应商模型名称')
    model_digest: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, comment='本地真实权重摘要；云端未提供时为NULL')
    capabilities: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='已实测模型能力与verified标记')
    embedding_dimension: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), nullable=True, comment='实测向量维度；整批必须一致')
    secret_ciphertext: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='Fernet加密凭据；只写不回显')
    enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0", comment='配置启用状态')
    __table_args__ = (
        sa.CheckConstraint("provider_type IN ('ollama','compatible_http')", name="ck_model_configs_provider_type"),
        sa.UniqueConstraint("logical_key", "revision_no", name="uq_model_configs_logical_key_revision_no"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"模型连接及修订"},
    )

class PromptVersion(Base):
    """prompt_versions：提示词版本。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "prompt_versions"
    task_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='代码固定的AI流程类型')
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='不可变配置或题目修订序号')
    content: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='领域结构化内容或文本；按所属表解释')
    output_schema: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='发布时冻结的离线JSON Schema')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","published"]}, comment='业务生命周期状态；允许值：draft,published')
    published_by: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_prompt_versions_published_by_users", ondelete='RESTRICT'), nullable=True, comment='发布者后台账号ID')
    __table_args__ = (
        sa.CheckConstraint("status IN ('draft','published')", name="ck_prompt_versions_status"),
        sa.UniqueConstraint("task_type", "revision_no", name="uq_prompt_versions_task_type_revision_no"),
        sa.Index("ix_prompt_versions_published_by", "published_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"提示词版本"},
    )

class WorkflowConfig(Base):
    """workflow_configs：固定流程配置。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "workflow_configs"
    task_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='代码固定的AI流程类型')
    model_config_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("model_configs.id", name="fk_workflow_configs_model_config_id_model_configs", ondelete='RESTRICT'), nullable=True, comment='固定模型连接修订ID')
    prompt_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("prompt_versions.id", name="fk_workflow_configs_prompt_version_id_prompt_versions", ondelete='RESTRICT'), nullable=True, comment='冻结的已发布提示词版本ID')
    enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default="0", comment='配置启用状态')
    timeout_seconds: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='模型请求超时配置（秒）')
    max_retries: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='允许的额外重试次数')
    config_revision: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='固定流程配置修订；运行前校验快照')
    __table_args__ = (
        sa.UniqueConstraint("task_type", name="uq_workflow_configs_task_type"),
        sa.Index("ix_workflow_configs_model_config_id", "model_config_id"),
        sa.Index("ix_workflow_configs_prompt_version_id", "prompt_version_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"固定流程配置"},
    )

class AiRun(Base):
    """ai_runs：模型运行证据。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "ai_runs"
    background_job_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("background_jobs.id", name="fk_ai_runs_background_job_id_background_jobs", ondelete='RESTRICT'), nullable=True, comment='关联持久后台任务ID')
    task_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='代码固定的AI流程类型')
    model_config_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("model_configs.id", name="fk_ai_runs_model_config_id_model_configs", ondelete='RESTRICT'), nullable=False, comment='固定模型连接修订ID')
    prompt_version_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("prompt_versions.id", name="fk_ai_runs_prompt_version_id_prompt_versions", ondelete='RESTRICT'), nullable=False, comment='冻结的已发布提示词版本ID')
    input_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False, comment='规范化模型输入的SHA256；不保存原始输入')
    source_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='模型生成所用的已授权来源引用')
    validated_output: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='仅保存通过schema和引用校验的模型结果')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="running", server_default="running", info={"allowed_values":["running","succeeded","invalid","failed"]}, comment='领域对象运行或审核状态；允许值：running,succeeded,invalid,failed')
    duration_ms: Mapped[int | None] = mapped_column(mysql.INTEGER(unsigned=True), nullable=True, comment='执行耗时（毫秒）')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, comment='允许记录的稳定错误码')
    __table_args__ = (
        sa.CheckConstraint("state IN ('running','succeeded','invalid','failed')", name="ck_ai_runs_state"),
        sa.Index("ix_ai_runs_background_job_id", "background_job_id"),
        sa.Index("ix_ai_runs_model_config_id", "model_config_id"),
        sa.Index("ix_ai_runs_prompt_version_id", "prompt_version_id"),
        sa.Index("ix_ai_runs_task_type_created_at", "task_type", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"模型运行证据"},
    )

