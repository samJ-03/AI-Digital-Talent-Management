from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Notification(Base):
    __tablename__ = "notifications"
    attempt_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_attempts.id", name="fk_notifications_attempt_id_exam_attempts", ondelete='RESTRICT'), nullable=True)
    event_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False)
    purpose: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["exam_invite","verify_code"]})
    recipient_snapshot: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","sending","accepted","failed","unknown","cancelled"]})
    provider_message_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    attempt_count: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    last_error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True)
    mail_config_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("mail_configs.id", name="fk_notifications_mail_config_id_mail_configs", ondelete='RESTRICT'), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("event_key", name="uq_notifications_event_key"),
        sa.CheckConstraint("purpose IN ('exam_invite','verify_code')", name="ck_notifications_purpose"),
        sa.CheckConstraint("status IN ('pending','sending','accepted','failed','unknown','cancelled')", name="ck_notifications_status"),
        sa.Index("ix_notifications_attempt_id", "attempt_id"),
        sa.Index("ix_notifications_mail_config_id", "mail_config_id"),
        sa.Index("ix_notifications_status_created_at", "status", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"邮件发送记录"},
    )

class MailConfig(Base):
    __tablename__ = "mail_configs"
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    smtp_host: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False)
    tls_mode: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["starttls","tls","none"]})
    sender_address: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    username: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    secret_ciphertext: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    public_base_url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","verified","active","disabled"]})
    __table_args__ = (
        sa.UniqueConstraint("revision_no", name="uq_mail_configs_revision_no"),
        sa.CheckConstraint("tls_mode IN ('starttls','tls','none')", name="ck_mail_configs_tls_mode"),
        sa.CheckConstraint("state IN ('draft','verified','active','disabled')", name="ck_mail_configs_state"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"邮件连接修订"},
    )

