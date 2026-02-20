"""Read-only access to the rules database."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from code_ruler.db.models import FunctionTypeRule, Rule


def get_read_session(db_path: str) -> Session:
    """Create a read-only session for the rules database."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    factory = sessionmaker(bind=engine)
    return factory()


def get_active_rules(session: Session) -> list[Rule]:
    """Get all active rules."""
    return session.query(Rule).filter(Rule.is_active.is_(True)).all()


def get_function_type_rules(session: Session) -> list[FunctionTypeRule]:
    """Get all function type rules with their parent rules."""
    return (
        session.query(FunctionTypeRule)
        .join(Rule)
        .filter(Rule.is_active.is_(True))
        .all()
    )
