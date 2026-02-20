"""Shared database base, engine, and session factory."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from github_extractor.models import Base


def get_engine(db_path: str) -> Engine:
    """Create a SQLAlchemy engine for the given SQLite database path."""
    return create_engine(f"sqlite:///{db_path}", echo=False)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    return sessionmaker(bind=engine)


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist.

    Imports rule models to ensure they're registered with Base.metadata.
    """
    import code_ruler.db.models  # noqa: F401

    Base.metadata.create_all(engine)
