from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    logical_key: Mapped[str] = mapped_column(sa.CHAR(36, collation='utf8mb4_bin'), nullable=False)
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    file_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("stored_files.id", name="fk_knowledge_documents_file_id_stored_files", ondelete='RESTRICT'), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(50), nullable=False, info={"allowed_values":["job","technical","rubric","reference"]})
    scope: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["company","department"]})
    department_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_knowledge_documents_department_id_departments", ondelete='RESTRICT'), nullable=True)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","processing","published","failed","archived"]})
    __table_args__ = (
        sa.CheckConstraint("category IN ('job','technical','rubric','reference')", name="ck_knowledge_documents_category"),
        sa.CheckConstraint("scope IN ('company','department')", name="ck_knowledge_documents_scope"),
        sa.CheckConstraint("state IN ('draft','processing','published','failed','archived')", name="ck_knowledge_documents_state"),
        sa.UniqueConstraint("logical_key", "version_no", name="uq_knowledge_documents_logical_key_version_no"),
        sa.Index("ix_knowledge_documents_file_id", "file_id"),
        sa.Index("ix_knowledge_documents_department_id", "department_id"),
        sa.Index("ix_knowledge_documents_scope_department_id_state", "scope", "department_id", "state"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"招聘资料版本"},
    )

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    document_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("knowledge_documents.id", name="fk_knowledge_chunks_document_id_knowledge_documents", ondelete='RESTRICT'), nullable=False)
    chunk_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    source_locator: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("document_id", "chunk_no", name="uq_knowledge_chunks_document_id_chunk_no"),
        sa.Index("ix_knowledge_chunks_document_id", "document_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"带来源切片"},
    )

