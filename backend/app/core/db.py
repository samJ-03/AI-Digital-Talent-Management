"""公共基础设施：定义ORM公共字段、UTC时间及乐观锁基类。"""
from __future__ import annotations
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr

def utc_now() -> datetime:
    """取得无时区UTC时间供MySQL DATETIME存储。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase):
    """Base：公共基础设施中的协作类型。"""
    __abstract__ = True
    id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment='无符号自增主键；API序列化为字符串')
    created_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6),default=utc_now,server_default=sa.func.current_timestamp(6),nullable=False, comment='创建时间（UTC，微秒精度）')
    updated_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6),default=utc_now,onupdate=utc_now,server_default=sa.func.current_timestamp(6),nullable=False, comment='最后业务更新时间（UTC，微秒精度）')
    row_version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True),default=1,server_default='1',nullable=False, comment='乐观锁版本；修改须匹配If-Match')

    @declared_attr.directive
    def __mapper_args__(cls):
        return {'version_id_col':cls.row_version}
