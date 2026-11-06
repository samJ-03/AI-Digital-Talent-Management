"""私有文件：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class StoredFile(Base):
    """stored_files：私有文件。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "stored_files"
    bucket: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='私有对象存储桶名')
    object_key: Mapped[str] = mapped_column(sa.String(500, collation='utf8mb4_bin'), nullable=False, comment='私有对象存储内部键；不直接返回外部')
    sha256: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False, comment='文件内容SHA256；不等于人员身份')
    original_name: Mapped[str] = mapped_column(sa.String(255), nullable=False, comment='原始文件名；不作为对象存储路径')
    mime_type: Mapped[str] = mapped_column(sa.String(120), nullable=False, comment='校验后的文件MIME类型')
    size_bytes: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False, comment='文件实际大小（字节）')
    uploader_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_stored_files_uploader_id_users", ondelete='RESTRICT'), nullable=True, comment='上传者后台账号ID')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="staged", server_default="staged", info={"allowed_values":["staged","ready","quarantined","deleted"]}, comment='业务生命周期状态；允许值：staged,ready,quarantined,deleted')
    __table_args__ = (
        sa.CheckConstraint("status IN ('staged','ready','quarantined','deleted')", name="ck_stored_files_status"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_stored_files_bucket_object_key"),
        sa.Index("ix_stored_files_uploader_id", "uploader_id"),
        sa.Index("ix_stored_files_sha256", "sha256"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"私有文件"},
    )

