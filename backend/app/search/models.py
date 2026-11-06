"""语义索引：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class IndexRecord(Base):
    """index_records：关系数据与向量索引映射。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "index_records"
    entity_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["profile","knowledge_chunk","job_version"]}, comment='关联业务实体类型；允许值：profile,knowledge_chunk,job_version')
    entity_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False, comment='关联业务实体ID；结合entity_type解释')
    model_config_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("model_configs.id", name="fk_index_records_model_config_id_model_configs", ondelete='RESTRICT'), nullable=False, comment='固定模型连接修订ID')
    collection_name: Mapped[str] = mapped_column(sa.String(120), nullable=False, comment='Milvus集合名；按模型配置与维度隔离')
    vector_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False, comment='Milvus向量记录的稳定键')
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False, comment='内容指纹；用于变更和索引一致性检查')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","ready","failed","stale","deleted"]}, comment='领域对象运行或审核状态；允许值：pending,ready,failed,stale,deleted')
    __table_args__ = (
        sa.CheckConstraint("entity_type IN ('profile','knowledge_chunk','job_version')", name="ck_index_records_entity_type"),
        sa.CheckConstraint("state IN ('pending','ready','failed','stale','deleted')", name="ck_index_records_state"),
        sa.UniqueConstraint("entity_type", "entity_id", "model_config_id", name="uq_index_records_entity_type_entity_id_model_config_id"),
        sa.UniqueConstraint("collection_name", "vector_key", name="uq_index_records_collection_name_vector_key"),
        sa.Index("ix_index_records_model_config_id", "model_config_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"关系数据与向量索引映射"},
    )

