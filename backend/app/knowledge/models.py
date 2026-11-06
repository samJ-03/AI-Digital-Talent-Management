"""知识资料：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class KnowledgeDocument(Base):
    """knowledge_documents：招聘资料版本。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "knowledge_documents"
    logical_key: Mapped[str] = mapped_column(sa.CHAR(36, collation='utf8mb4_bin'), nullable=False, comment='跨修订保持稳定的逻辑标识')
    version_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='同一主对象下的业务版本序号')
    file_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("stored_files.id", name="fk_knowledge_documents_file_id_stored_files", ondelete='RESTRICT'), nullable=False, comment='私有原始文件ID')
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False, comment='岗位或知识标题')
    category: Mapped[str] = mapped_column(sa.String(50), nullable=False, info={"allowed_values":["job","technical","rubric","reference"]}, comment='知识分类；允许值：job,technical,rubric,reference')
    scope: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["company","department"]}, comment='知识可见范围；允许值：company,department')
    department_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_knowledge_documents_department_id_departments", ondelete='RESTRICT'), nullable=True, comment='归属部门ID；用于部门数据权限')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","processing","published","failed","archived"]}, comment='领域对象运行或审核状态；允许值：draft,processing,published,failed,archived')
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
    """knowledge_chunks：带来源切片。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "knowledge_chunks"
    document_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("knowledge_documents.id", name="fk_knowledge_chunks_document_id_knowledge_documents", ondelete='RESTRICT'), nullable=False, comment='所属知识文档ID')
    chunk_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='文档片段序号')
    content: Mapped[str] = mapped_column(sa.Text(), nullable=False, comment='领域结构化内容或文本；按所属表解释')
    source_locator: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='知识片段页码或段落定位')
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False, comment='内容指纹；用于变更和索引一致性检查')
    __table_args__ = (
        sa.UniqueConstraint("document_id", "chunk_no", name="uq_knowledge_chunks_document_id_chunk_no"),
        sa.Index("ix_knowledge_chunks_document_id", "document_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"带来源切片"},
    )

