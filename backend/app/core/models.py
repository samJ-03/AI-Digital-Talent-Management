from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    actor_scope: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False)
    operation: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False)
    request_key: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False)
    request_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="processing", server_default="processing", info={"allowed_values":["processing","completed","failed"]})
    result_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False)
    __table_args__ = (
        sa.CheckConstraint("state IN ('processing','completed','failed')", name="ck_idempotency_records_state"),
        sa.UniqueConstraint("actor_scope", "operation", "request_key", name="uq_idempotency_records_actor_scope_operation_request_key"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"关键命令幂等记录"},
    )

