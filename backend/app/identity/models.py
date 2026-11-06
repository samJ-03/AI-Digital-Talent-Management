"""后台身份认证与权限：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Department(Base):
    """departments：部门。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "departments"
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='业务对象名称')
    parent_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_departments_parent_id_departments", ondelete='RESTRICT'), nullable=True, comment='上级部门ID')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","disabled"]}, comment='业务生命周期状态；允许值：active,disabled')
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_departments_status"),
        sa.Index("ix_departments_parent_id", "parent_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"部门"},
    )

class User(Base):
    """users：后台账号。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "users"
    department_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("departments.id", name="fk_users_department_id_departments", ondelete='RESTRICT'), nullable=True, comment='归属部门ID；用于部门数据权限')
    login_name: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='后台登录名')
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, comment='Argon2密码哈希；禁止明文或可逆密码')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","disabled"]}, comment='业务生命周期状态；允许值：active,disabled')
    auth_version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=1, server_default="1", comment='认证版本；变更后旧会话失效')
    __table_args__ = (
        sa.UniqueConstraint("login_name", name="uq_users_login_name"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
        sa.Index("ix_users_department_id", "department_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"后台账号"},
    )

class Role(Base):
    """roles：角色。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='稳定业务编码')
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, comment='业务对象名称')
    permission_codes: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=list, comment='明确授予的权限码列表')
    data_scope: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["department","company"]}, comment='数据授权范围：部门或全企业；允许值：department,company')
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="active", server_default="active", info={"allowed_values":["active","disabled"]}, comment='业务生命周期状态；允许值：active,disabled')
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_roles_code"),
        sa.CheckConstraint("data_scope IN ('department','company')", name="ck_roles_data_scope"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_roles_status"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"角色"},
    )

class UserRole(Base):
    """user_roles：账号角色。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_user_roles_user_id_users", ondelete='RESTRICT'), nullable=False, comment='关联后台账号ID')
    role_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("roles.id", name="fk_user_roles_role_id_roles", ondelete='RESTRICT'), nullable=False, comment='关联角色ID')
    __table_args__ = (
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),
        sa.Index("ix_user_roles_user_id", "user_id"),
        sa.Index("ix_user_roles_role_id", "role_id"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"账号角色"},
    )

