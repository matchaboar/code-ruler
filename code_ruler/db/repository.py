"""CRUD operations for rules."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from code_ruler.db.models import EnforcerScript, FunctionTypeRule, Rule, RuleProvenance, TestSpriteResult


def get_all_rules(session: Session, repo_id: int | None = None, active_only: bool = False) -> list[Rule]:
    """Get all rules, optionally filtered by repo and/or active only."""
    query = session.query(Rule)
    if repo_id is not None:
        query = query.filter(Rule.repo_id == repo_id)
    if active_only:
        query = query.filter(Rule.is_active.is_(True))
    return query.all()


def get_rule_by_slug(session: Session, slug: str, repo_id: int | None = None) -> Rule | None:
    """Get a rule by slug, optionally scoped to a repo."""
    query = session.query(Rule).filter_by(slug=slug)
    if repo_id is not None:
        query = query.filter(Rule.repo_id == repo_id)
    return query.first()


def create_rule(
    session: Session,
    *,
    slug: str,
    repo_id: int,
    category: str,
    severity: str,
    title: str,
    description: str,
    positive_example: str | None,
    negative_example: str | None,
    rationale: str,
) -> Rule:
    """Create a new rule, or update the existing one if the slug+repo_id already exists."""
    now = datetime.now(timezone.utc)
    existing = session.query(Rule).filter_by(slug=slug, repo_id=repo_id).first()
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
        repo_id=repo_id,
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


def create_enforcer_script(
    session: Session,
    *,
    rule_id: int,
    enforcer_source: str,
    check_type: str,
    decorator_source: str | None = None,
    test_code: str | None = None,
    test_result: str = "pending",
    test_output: str | None = None,
    attempt_count: int = 0,
    status: str = "pending",
    dd_traces: dict | None = None,
) -> EnforcerScript:
    """Create or replace an enforcer script for a rule."""
    now = datetime.now(timezone.utc)
    existing = session.query(EnforcerScript).filter_by(rule_id=rule_id).first()
    if existing:
        existing.enforcer_source = enforcer_source
        existing.check_type = check_type
        existing.decorator_source = decorator_source
        existing.test_code = test_code
        existing.test_result = test_result
        existing.test_output = test_output
        existing.attempt_count = attempt_count
        existing.status = status
        existing.dd_traces = dd_traces
        existing.updated_at = now
        session.flush()
        return existing
    es = EnforcerScript(
        rule_id=rule_id,
        enforcer_source=enforcer_source,
        check_type=check_type,
        decorator_source=decorator_source,
        test_code=test_code,
        test_result=test_result,
        test_output=test_output,
        attempt_count=attempt_count,
        status=status,
        dd_traces=dd_traces,
        created_at=now,
        updated_at=now,
    )
    session.add(es)
    session.flush()
    return es


def get_enforcer_by_rule_id(session: Session, rule_id: int) -> EnforcerScript | None:
    """Get an enforcer script by rule ID."""
    return session.query(EnforcerScript).filter_by(rule_id=rule_id).first()


def get_all_enforcers(session: Session, repo_id: int | None = None) -> list[EnforcerScript]:
    """Get all enforcer scripts, optionally filtered by repo."""
    query = session.query(EnforcerScript)
    if repo_id is not None:
        query = query.join(Rule, EnforcerScript.rule_id == Rule.id).filter(Rule.repo_id == repo_id)
    return query.all()


def update_enforcer_script(session: Session, enforcer: EnforcerScript, **kwargs: object) -> EnforcerScript:
    """Update an enforcer script's fields."""
    for key, value in kwargs.items():
        if hasattr(enforcer, key):
            setattr(enforcer, key, value)
    enforcer.updated_at = datetime.now(timezone.utc)
    session.flush()
    return enforcer


def update_rule(session: Session, rule: Rule, **kwargs: object) -> Rule:
    """Update a rule's fields."""
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = datetime.now(timezone.utc)
    rule.version += 1
    session.flush()
    return rule


# ---- TestSpriteResult CRUD ----

def create_testsprite_result(
    session: Session,
    *,
    rule_id: int,
    repo_url: str,
    status: str = "pending",
    test_plan_json: dict | None = None,
    generated_tests: str | None = None,
    test_results_json: dict | None = None,
    diff: str | None = None,
    error_message: str | None = None,
) -> TestSpriteResult:
    """Create a new TestSprite result record."""
    now = datetime.now(timezone.utc)
    result = TestSpriteResult(
        rule_id=rule_id,
        repo_url=repo_url,
        status=status,
        test_plan_json=test_plan_json,
        generated_tests=generated_tests,
        test_results_json=test_results_json,
        diff=diff,
        error_message=error_message,
        created_at=now,
        updated_at=now,
    )
    session.add(result)
    session.flush()
    return result


def get_testsprite_results_by_rule_id(session: Session, rule_id: int) -> list[TestSpriteResult]:
    """Get all TestSprite results for a rule."""
    return session.query(TestSpriteResult).filter_by(rule_id=rule_id).order_by(TestSpriteResult.created_at.desc()).all()


def get_testsprite_result(session: Session, result_id: int) -> TestSpriteResult | None:
    """Get a single TestSprite result by ID."""
    return session.get(TestSpriteResult, result_id)


def update_testsprite_result(session: Session, result: TestSpriteResult, **kwargs: object) -> TestSpriteResult:
    """Update a TestSprite result's fields."""
    for key, value in kwargs.items():
        if hasattr(result, key):
            setattr(result, key, value)
    result.updated_at = datetime.now(timezone.utc)
    session.flush()
    return result


def get_all_testsprite_results(session: Session, repo_id: int | None = None) -> list[TestSpriteResult]:
    """Get all TestSprite results, optionally filtered by repo."""
    query = session.query(TestSpriteResult)
    if repo_id is not None:
        query = query.join(Rule, TestSpriteResult.rule_id == Rule.id).filter(Rule.repo_id == repo_id)
    return query.order_by(TestSpriteResult.created_at.desc()).all()
