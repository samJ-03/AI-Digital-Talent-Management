from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Department(Base):
    __tablename__ = "departments"
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_departments_parent_id_departments", ondelete='RESTRICT'), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","disabled"]})
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_departments_status"),
        sa.Index("ix_departments_parent_id", "parent_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"部门"},
    )

class User(Base):
    __tablename__ = "users"
    department_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_users_department_id_departments", ondelete='RESTRICT'), nullable=True)
    login_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","disabled"]})
    auth_version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=1, server_default="1")
    __table_args__ = (
        sa.UniqueConstraint("login_name", name="uq_users_login_name"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
        sa.Index("ix_users_department_id", "department_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"后台账号"},
    )

class Role(Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    permission_codes: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list)
    data_scope: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["department","company"]})
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","disabled"]})
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_roles_code"),
        sa.CheckConstraint("data_scope IN ('department','company')", name="ck_roles_data_scope"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_roles_status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"角色"},
    )

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_user_roles_user_id_users", ondelete='RESTRICT'), nullable=False)
    role_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("roles.id", name="fk_user_roles_role_id_roles", ondelete='RESTRICT'), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),
        sa.Index("ix_user_roles_user_id", "user_id"),
        sa.Index("ix_user_roles_role_id", "role_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"账号角色"},
    )

