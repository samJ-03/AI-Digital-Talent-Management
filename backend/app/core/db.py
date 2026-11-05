from __future__ import annotations
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase):
    __abstract__ = True
    id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6),default=utc_now,server_default=sa.func.current_timestamp(6),nullable=False)
    updated_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=6),default=utc_now,onupdate=utc_now,server_default=sa.func.current_timestamp(6),nullable=False)
    row_version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True),default=1,server_default='1',nullable=False)

    @declared_attr.directive
    def __mapper_args__(cls):
        return {'version_id_col':cls.row_version}
