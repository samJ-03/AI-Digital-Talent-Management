"""邮件配置与交付：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Notification(Base):
    """notifications：邮件发送记录。邮件结果未知时不得自动重发，发送修订保持冻结。"""
    __tablename__ = "notifications"
    attempt_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("exam_attempts.id", name="fk_notifications_attempt_id_exam_attempts", ondelete='RESTRICT'), nullable=True, comment='关联考试轮次ID')
    event_key: Mapped[str] = mapped_column(sa.String(190, collation='utf8mb4_bin'), nullable=False, comment='业务事件唯一幂等键')
    purpose: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["exam_invite","verify_code"]}, comment='邮件用途；允许值：exam_invite,verify_code')
    recipient_snapshot: Mapped[str] = mapped_column(sa.String(254), nullable=False, comment='本次发送冻结的收件人邮箱')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="pending", server_default="pending", info={"allowed_values":["pending","sending","accepted","failed","unknown","cancelled"]}, comment='业务生命周期状态；允许值：pending,sending,accepted,failed,unknown,cancelled')
    provider_message_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, comment='邮件供应商返回的消息标识')
    attempt_count: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=0, server_default="0", comment='已尝试执行或发送次数')
    last_error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, comment='最近一次执行或发送的脱敏错误码')
    sent_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='邮件交付时间（UTC）')
    mail_config_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("mail_configs.id", name="fk_notifications_mail_config_id_mail_configs", ondelete='RESTRICT'), nullable=False, comment='发送时冻结的邮件连接修订ID')
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
    """mail_configs：邮件连接修订。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "mail_configs"
    revision_no: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='不可变配置或题目修订序号')
    smtp_host: Mapped[str] = mapped_column(sa.String(255), nullable=False, comment='通过白名单校验的SMTP主机')
    smtp_port: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, comment='SMTP服务端口')
    tls_mode: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["starttls","tls","none"]}, comment='SMTP传输加密模式；生产须TLS；允许值：starttls,tls,none')
    sender_address: Mapped[str] = mapped_column(sa.String(254), nullable=False, comment='发送方邮箱地址')
    username: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, comment='SMTP认证用户名')
    secret_ciphertext: Mapped[str | None] = mapped_column(sa.Text(), nullable=True, comment='Fernet加密凭据；只写不回显')
    public_base_url: Mapped[str] = mapped_column(sa.String(500), nullable=False, comment='邮件中的候选人公共入口基础地址')
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="draft", server_default="draft", info={"allowed_values":["draft","verified","active","disabled"]}, comment='领域对象运行或审核状态；允许值：draft,verified,active,disabled')
    __table_args__ = (
        sa.UniqueConstraint("revision_no", name="uq_mail_configs_revision_no"),
        sa.CheckConstraint("tls_mode IN ('starttls','tls','none')", name="ck_mail_configs_tls_mode"),
        sa.CheckConstraint("state IN ('draft','verified','active','disabled')", name="ck_mail_configs_state"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"邮件连接修订"},
    )

