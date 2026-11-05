from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class StoredFile(Base):
    __tablename__ = "stored_files"
    bucket: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    object_key: Mapped[str] = mapped_column(sa.String(500, collation='utf8mb4_bin'), nullable=False)
    sha256: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False)
    original_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False)
    uploader_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_stored_files_uploader_id_users", ondelete='RESTRICT'), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="staged", server_default="staged", info={"allowed_values":["staged","ready","quarantined","deleted"]})
    __table_args__ = (
        sa.CheckConstraint("status IN ('staged','ready','quarantined','deleted')", name="ck_stored_files_status"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_stored_files_bucket_object_key"),
        sa.Index("ix_stored_files_uploader_id", "uploader_id"),
        sa.Index("ix_stored_files_sha256", "sha256"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"私有文件"},
    )

