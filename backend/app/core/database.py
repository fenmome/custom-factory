"""数据库引擎与会话管理（SQLAlchemy 2.0 / MySQL 8.0）。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.base import Base  # noqa: F401  (统一 DeclarativeBase 注册表)


def _engine_options() -> dict[str, Any]:
    return {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "echo": settings.DB_ECHO,
        "future": True,
    }


engine: Engine = create_engine(settings.DATABASE_URL, **_engine_options())

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_engine() -> Engine:
    return engine


def get_session() -> Iterator[Session]:
    """FastAPI 依赖项：请求级会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class UnitOfWork:
    """显式事务边界辅助类。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
