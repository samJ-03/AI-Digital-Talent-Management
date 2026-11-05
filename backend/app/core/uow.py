from __future__ import annotations
from functools import lru_cache
from typing import Callable
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.settings import Settings

class SqlAlchemyUow:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> 'SqlAlchemyUow':
        if self.session is not None:
            raise RuntimeError('Unit of work is already active')
        self.session = self.session_factory()
        return self

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError('Unit of work is not active')
        self.session.commit()

    def rollback(self) -> None:
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
    settings=Settings.load()
    engine=create_engine(settings.database_url.get_secret_value(),pool_pre_ping=True,pool_recycle=1800,connect_args={'connect_timeout':5})
    return sessionmaker(bind=engine,expire_on_commit=False)

def make_uow() -> SqlAlchemyUow:
    return SqlAlchemyUow(default_session_factory())
