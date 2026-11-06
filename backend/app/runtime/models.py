"""持久后台任务与Outbox：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class BackgroundJob(Base):
    """background_jobs：持久任务与租约。MySQL事实记录与租约共同决定执行权，Redis仅承载交付。"""
    __tablename__ = "background_jobs"
    job_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='代码白名单中的后台任务类型')
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='关联业务实体类型')
    entity_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False, comment='关联业务实体ID；结合entity_type解释')
    idempotency_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False, comment='客户端或系统请求幂等键')
    input_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='任务允许访问的业务输入引用')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="queued", server_default="queued", info={"allowed_values":["queued","running","succeeded","retry","failed","cancelled"]}, comment='领域对象运行或审核状态；允许值：queued,running,succeeded,retry,failed,cancelled')
    attempt_count: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default="0", comment='已尝试执行或发送次数')
    lease_owner: Mapped[str | None] = mapped_column(sa.String(100), nullable=True, comment='任务租约持有者随机标识')
    lease_until: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='租约到期时间（UTC）')
    next_run_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='任务下次允许执行时间（UTC）')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, comment='允许记录的稳定错误码')
    __table_args__ = (
        sa.UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        sa.CheckConstraint("state IN ('queued','running','succeeded','retry','failed','cancelled')", name="ck_background_jobs_state"),
        sa.Index("ix_background_jobs_state_next_run_at", "state", "next_run_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"持久任务与租约"},
    )

class OutboxEvent(Base):
    """outbox_events：事务外发事件。与领域状态同事务写入，事务提交后异步投递。"""
    __tablename__ = "outbox_events"
    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='业务事件类型')
    aggregate_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='业务聚合类型')
    aggregate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False, comment='业务聚合ID')
    event_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False, comment='业务事件唯一幂等键')
    payload_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='Outbox业务引用；禁止写入原始敏感正文')
    private_payload_ciphertext: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='短期私有载荷密文；不得进入队列或日志')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","processing","sent","failed","unknown","cancelled"]}, comment='领域对象运行或审核状态；允许值：pending,processing,sent,failed,unknown,cancelled')
    lease_until: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='租约到期时间（UTC）')
    next_attempt_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment="下一次Outbox事件投递尝试时间（UTC）")
    expires_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='记录或私有载荷过期时间（UTC）')
    __table_args__ = (
        sa.UniqueConstraint("event_key", name="uq_outbox_events_event_key"),
        sa.CheckConstraint("state IN ('pending','processing','sent','failed','unknown','cancelled')", name="ck_outbox_events_state"),
        sa.Index("ix_outbox_events_state_next_attempt_at", "state", "next_attempt_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"事务外发事件"},
    )

