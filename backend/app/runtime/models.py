from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    job_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False)
    input_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="queued", server_default="queued", info={"allowed_values":["queued","running","succeeded","retry","failed","cancelled"]})
    attempt_count: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    __table_args__ = (
        sa.UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        sa.CheckConstraint("state IN ('queued','running','succeeded','retry','failed','cancelled')", name="ck_background_jobs_state"),
        sa.Index("ix_background_jobs_state_next_run_at", "state", "next_run_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"持久任务与租约"},
    )

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    aggregate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), nullable=False)
    event_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False)
    payload_refs: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict)
    private_payload_ciphertext: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","processing","sent","failed","unknown","cancelled"]})
    lease_until: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    __table_args__ = (
        sa.UniqueConstraint("event_key", name="uq_outbox_events_event_key"),
        sa.CheckConstraint("state IN ('pending','processing','sent','failed','unknown','cancelled')", name="ck_outbox_events_state"),
        sa.Index("ix_outbox_events_state_next_attempt_at", "state", "next_attempt_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"事务外发事件"},
    )

