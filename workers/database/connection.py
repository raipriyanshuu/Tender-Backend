from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from workers.config import Config

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker | None = None


def _normalize_database_url(database_url: str) -> str:
    # Default to psycopg v3 driver if the URL doesn't specify a driver.
    # This avoids psycopg2 build issues on Windows/Python 3.13.
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def get_engine(config: Config) -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(
            _normalize_database_url(config.database_url),
            pool_size=config.database_max_connections,
            pool_pre_ping=True,
            pool_timeout=config.database_timeout_seconds,
            future=True,
        )
    return _ENGINE


def get_session_factory(config: Config) -> sessionmaker:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind=get_engine(config),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SESSION_FACTORY


@contextmanager
def get_session(config: Config) -> Iterator[Session]:
    session = get_session_factory(config)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection(config: Config) -> bool:
    engine = get_engine(config)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
