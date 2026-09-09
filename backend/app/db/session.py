"""Database engine and session handling — optional by design.

Persistence is a Phase 6 addition to an app that has shipped without it, and
the production deployment does not have a database yet. So `DATABASE_URL`
being unset is a supported configuration, not an error: `is_enabled()` is
False, every persistence-backed route answers 503 with a reason, and the
stateless routes carry on exactly as before. Importing this module never
opens a connection.

The one transformation applied to the URL is `postgres://` ->
`postgresql+psycopg://`. Render (and Heroku before it) hands out the former,
SQLAlchemy 2.0 dropped support for it, and the failure mode is an import-time
crash on deploy with a message about a missing dialect.
"""

import logging
import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def is_enabled() -> bool:
    """True when a database is configured. Cheap; safe to call per request."""
    return bool(database_url())


def normalise_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def get_engine() -> Engine:
    """The process-wide engine, created on first use."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    url = database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Persistence-backed features (snapshots, "
            "alerts, paper trading) are disabled until it is."
        )

    with _lock:
        if _engine is None:
            kwargs = {"future": True, "pool_pre_ping": True}
            if url.startswith("sqlite"):
                # SQLite's default thread check rejects the connection reuse a
                # thread pool does; the app is read-mostly and this is only
                # ever a dev/test backend.
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                # Render's free Postgres allows few connections, and a
                # scheduler thread plus request workers exhaust a large pool
                # for no benefit at this scale.
                kwargs.update(pool_size=5, max_overflow=5, pool_recycle=1800)
            _engine = create_engine(normalise_url(url), **kwargs)
            _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
            logger.info("Database engine created (%s)", _engine.dialect.name)
    return _engine


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on any exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Routes using it must guard on `is_enabled()` first."""
    with session_scope() as session:
        yield session


def create_all() -> None:
    """Create tables directly, bypassing Alembic.

    For local development and tests only. Production schema changes go through
    Alembic so that a column added to a model cannot silently diverge from the
    deployed database.
    """
    Base.metadata.create_all(bind=get_engine())
    logger.info("Schema created for %d tables", len(Base.metadata.tables))


def reset_engine() -> None:
    """Drop the cached engine. Used by tests that swap DATABASE_URL."""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None
