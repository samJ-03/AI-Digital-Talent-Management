"""审计留痕：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class AuditLog(Base):
    """audit_logs：操作与权限审计。只追加脱敏审计记录，不保存秘密或原始业务正文。"""
    __tablename__ = "audit_logs"
    actor_type: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["admin","hr","candidate","system"]}, comment='操作者类型；允许值：admin,hr,candidate,system')
    actor_user_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_audit_logs_actor_user_id_users", ondelete='RESTRICT'), nullable=True, comment='后台操作者ID')
    actor_candidate_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_audit_logs_actor_candidate_id_candidates", ondelete='RESTRICT'), nullable=True, comment='候选人操作者ID')
    action: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='操作动作')
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='关联业务实体类型')
    entity_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), nullable=True, comment='关联业务实体ID；结合entity_type解释')
    request_id: Mapped[str] = mapped_column(sa.CHAR(36), nullable=False, comment='请求链路标识')
    change_summary: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='审计变更摘要；仅允许脱敏字段')
    result: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["success","denied","failed"]}, comment='筛选或操作结果；允许值：success,denied,failed')
    __table_args__ = (
        sa.CheckConstraint("actor_type IN ('admin','hr','candidate','system')", name="ck_audit_logs_actor_type"),
        sa.CheckConstraint("result IN ('success','denied','failed')", name="ck_audit_logs_result"),
        sa.Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        sa.Index("ix_audit_logs_actor_candidate_id", "actor_candidate_id"),
        sa.Index("ix_audit_logs_entity_type_entity_id_created_at", "entity_type", "entity_id", "created_at"),
        sa.Index("ix_audit_logs_actor_user_id_created_at", "actor_user_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"操作与权限审计"},
    )

