"""公共基础设施：管理显式提交、异常回滚和受控保存点。"""
from __future__ import annotations
from functools import lru_cache
from contextlib import contextmanager
from typing import Callable
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.settings import Settings

class SqlAlchemyUow:
    """SqlAlchemyUow：公共基础设施中的协作类型。"""
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> 'SqlAlchemyUow':
        if self.session is not None:
            raise RuntimeError('Unit of work is already active')
        self.session = self.session_factory()
        return self

    def commit(self) -> None:
        """显式提交当前工作单元。"""
        if self.session is None:
            raise RuntimeError('Unit of work is not active')
        self.session.commit()

    @contextmanager
    def savepoint(self):
        """管理受控保存点，禁止回调提交外层事务。"""
        if self.session is None:
            raise RuntimeError('Unit of work is not active')
        nested=self.session.begin_nested()
        try:
            yield nested
        except BaseException:
            nested.rollback()
            raise
        else:
            # Permit only this internal SAVEPOINT release, never an outer command commit.
            previous=self.session.info.get('approved_savepoint')
            self.session.info['approved_savepoint']=nested
            try:
                nested.commit()
            finally:
                if previous is None: self.session.info.pop('approved_savepoint',None)
                else: self.session.info['approved_savepoint']=previous

    def rollback(self) -> None:
        """回滚当前未提交事务。"""
        if self.session is not None:
            self.session.rollback()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        try:
            if self.session is not None and self.session.in_transaction():
                self.session.rollback()
        finally:
            if self.session is not None:
                self.session.close()
                self.session = None
        return False

@lru_cache(maxsize=1)
def default_session_factory():
    """加载完整ORM注册表并复用数据库会话工厂。"""
    from app.models import register_models
    register_models()
    settings=Settings.load()
    engine=create_engine(settings.database_url.get_secret_value(),pool_pre_ping=True,pool_recycle=1800,connect_args={'connect_timeout':5})
    return sessionmaker(bind=engine,expire_on_commit=False)

def make_uow() -> SqlAlchemyUow:
    """为一次领域操作构造新的工作单元。"""
    return SqlAlchemyUow(default_session_factory())
