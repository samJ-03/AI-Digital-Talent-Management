"""简历导入：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class ImportBatch(Base):
    """import_batches：导入批次。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "import_batches"
    job_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("jobs.id", name="fk_import_batches_job_id_jobs", ondelete='RESTRICT'), nullable=True, comment='所属招聘岗位ID')
    created_by: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_import_batches_created_by_users", ondelete='RESTRICT'), nullable=False, comment='创建者后台账号ID')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="queued", server_default="queued", info={"allowed_values":["queued","processing","completed","partial_failed"]}, comment='业务生命周期状态；允许值：queued,processing,completed,partial_failed')
    request_key: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False, comment='批量导入请求幂等键')
    file_count: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='本批导入文件数量')
    __table_args__ = (
        sa.CheckConstraint("status IN ('queued','processing','completed','partial_failed')", name="ck_import_batches_status"),
        sa.UniqueConstraint("created_by", "request_key", name="uq_import_batches_created_by_request_key"),
        sa.Index("ix_import_batches_job_id", "job_id"),
        sa.Index("ix_import_batches_created_by", "created_by"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"导入批次"},
    )

class ImportItem(Base):
    """import_items：每份文件的导入处理。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "import_items"
    batch_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("import_batches.id", name="fk_import_items_batch_id_import_batches", ondelete='RESTRICT'), nullable=False, comment='所属简历导入批次ID')
    file_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("stored_files.id", name="fk_import_items_file_id_stored_files", ondelete='RESTRICT'), nullable=True, comment='私有原始文件ID；仅上传前置失败时可空且状态必须failed')
    resume_version_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("resume_versions.id", name="fk_import_items_resume_version_id_resume_versions", ondelete='RESTRICT'), nullable=True, comment='冻结的简历修订ID')
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="uploaded", server_default="uploaded", info={"allowed_values":["uploaded","queued","parsing","parsed","failed"]}, comment='业务生命周期状态；允许值：uploaded,queued,parsing,parsed,failed')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, comment='允许记录的稳定错误码')
    error_detail_safe: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='可展示的脱敏错误说明；禁止原始异常或秘密')
    source_order: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='导入文件在批次中的顺序')
    __table_args__ = (
        sa.CheckConstraint("status IN ('uploaded','queued','parsing','parsed','failed')", name="ck_import_items_status"),
        sa.CheckConstraint("file_id IS NOT NULL OR status = 'failed'", name="ck_import_items_failed_without_file"),
        sa.UniqueConstraint("batch_id", "source_order", name="uq_import_items_batch_id_source_order"),
        sa.Index("ix_import_items_batch_id", "batch_id"),
        sa.Index("ix_import_items_file_id", "file_id"),
        sa.Index("ix_import_items_resume_version_id", "resume_version_id"),
        sa.Index("ix_import_items_batch_id_status", "batch_id", "status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"每份文件的导入处理"},
    )

