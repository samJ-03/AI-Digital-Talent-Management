"""公共基础设施：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class IdempotencyRecord(Base):
    """idempotency_records：关键命令幂等记录。请求指纹和业务结果在同一事务保存，防止重复副作用。"""
    __tablename__ = "idempotency_records"
    actor_scope: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False, comment='幂等主体范围（角色与账号或候选人标识）')
    operation: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False, comment='幂等业务操作标识')
    request_key: Mapped[str] = mapped_column(sa.String(100, collation='utf8mb4_bin'), nullable=False, comment="请求幂等键；结合操作者范围与操作标识唯一")
    request_hash: Mapped[str] = mapped_column(sa.CHAR(64, collation='utf8mb4_bin'), nullable=False, comment='规范化幂等请求内容SHA256')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="processing", server_default="processing", info={"allowed_values":["processing","completed","failed"]}, comment='领域对象运行或审核状态；允许值：processing,completed,failed')
    result_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=True, comment='已完成任务或幂等操作的结果引用')
    expires_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6), nullable=False, comment='记录或私有载荷过期时间（UTC）')
    __table_args__ = (
        sa.CheckConstraint("state IN ('processing','completed','failed')", name="ck_idempotency_records_state"),
        sa.UniqueConstraint("actor_scope", "operation", "request_key", name="uq_idempotency_records_actor_scope_operation_request_key"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"关键命令幂等记录"},
    )

