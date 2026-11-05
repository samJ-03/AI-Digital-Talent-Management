from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    actor_type: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["admin","hr","candidate","system"]})
    actor_user_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_audit_logs_actor_user_id_users", ondelete='RESTRICT'), nullable=True)
    actor_candidate_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_audit_logs_actor_candidate_id_candidates", ondelete='RESTRICT'), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), nullable=True)
    request_id: Mapped[str] = mapped_column(sa.CHAR(36), nullable=False)
    change_summary: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    result: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["success","denied","failed"]})
    __table_args__ = (
        sa.CheckConstraint("actor_type IN ('admin','hr','candidate','system')", name="ck_audit_logs_actor_type"),
        sa.CheckConstraint("result IN ('success','denied','failed')", name="ck_audit_logs_result"),
        sa.Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        sa.Index("ix_audit_logs_actor_candidate_id", "actor_candidate_id"),
        sa.Index("ix_audit_logs_entity_type_entity_id_created_at", "entity_type", "entity_id", "created_at"),
        sa.Index("ix_audit_logs_actor_user_id_created_at", "actor_user_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"操作与权限审计"},
    )

