"""CRUD operations for rules."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from code_ruler.db.models import FunctionTypeRule, Rule, RuleProvenance


def get_all_rules(session: Session, active_only: bool = False) -> list[Rule]:
    """Get all rules, optionally filtered to active only."""
    query = session.query(Rule)
    if active_only:
        query = query.filter(Rule.is_active.is_(True))
    return query.all()


def get_rule_by_slug(session: Session, slug: str) -> Rule | None:
    """Get a rule by slug."""
    return session.query(Rule).filter_by(slug=slug).first()


def create_rule(
    session: Session,
    *,
    slug: str,
    category: str,
    severity: str,
    title: str,
    description: str,
    positive_example: str | None,
    negative_example: str | None,
    rationale: str,
) -> Rule:
    """Create a new rule, or update the existing one if the slug already exists."""
    now = datetime.now(timezone.utc)
    existing = session.query(Rule).filter_by(slug=slug).first()
    if existing:
        existing.category = category
        existing.severity = severity
        existing.title = title
        existing.description = description
        existing.positive_example = positive_example
        existing.negative_example = negative_example
        existing.rationale = rationale
        existing.updated_at = now
        existing.version += 1
        session.flush()
        return existing
    rule = Rule(
        slug=slug,
        category=category,
        severity=severity,
        title=title,
        description=description,
        positive_example=positive_example,
        negative_example=negative_example,
        rationale=rationale,
        created_at=now,
        updated_at=now,
    )
    session.add(rule)
    session.flush()
    return rule


def create_function_type_rule(
    session: Session,
    *,
    rule_id: int,
    decorator_name: str,
    decorator_source: str,
    linter_source: str,
    constraints_json: list[str] | None = None,
) -> FunctionTypeRule:
    """Create a function type rule linked to an existing rule."""
    ftr = FunctionTypeRule(
        rule_id=rule_id,
        decorator_name=decorator_name,
        decorator_source=decorator_source,
        linter_source=linter_source,
        constraints_json=constraints_json,
    )
    session.add(ftr)
    session.flush()
    return ftr


def create_provenance(
    session: Session,
    *,
    rule_id: int,
    pull_request_id: int,
    review_comment_id: int | None = None,
    extraction_notes: str | None = None,
) -> RuleProvenance:
    """Create a provenance record linking a rule to a PR/comment."""
    prov = RuleProvenance(
        rule_id=rule_id,
        pull_request_id=pull_request_id,
        review_comment_id=review_comment_id,
        extraction_notes=extraction_notes,
        created_at=datetime.now(timezone.utc),
    )
    session.add(prov)
    session.flush()
    return prov


def update_rule(session: Session, rule: Rule, **kwargs: object) -> Rule:
    """Update a rule's fields."""
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = datetime.now(timezone.utc)
    rule.version += 1
    session.flush()
    return rule
