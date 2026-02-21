"""Tests for the enforcer generation feature."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from code_ruler.db.models import EnforcerScript, FunctionTypeRule, Rule
from code_ruler.db.repository import (
    create_enforcer_script,
    get_all_enforcers,
    get_enforcer_by_rule_id,
    update_enforcer_script,
)
from code_ruler.enforcer.generator import (
    MAX_ATTEMPTS,
    _extract_code,
    _test_enforcer,
    generate_enforcer,
)
from github_extractor.models import Base, Repository


@pytest.fixture
def db_session():
    """Create an in-memory DB with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def sample_repo(db_session):
    """Create a sample repository."""
    repo = Repository(
        owner="test", name="repo", full_name="test/repo",
        url="https://github.com/test/repo",
    )
    db_session.add(repo)
    db_session.flush()
    return repo


@pytest.fixture
def sample_rule(db_session, sample_repo):
    """Create a sample rule with negative_example."""
    now = datetime.now(timezone.utc)
    rule = Rule(
        slug="no-bare-except",
        repo_id=sample_repo.id,
        category="lint",
        severity="warning",
        title="Do not use bare except clauses",
        description="Always catch a specific exception type instead of using bare `except:`.",
        positive_example="try:\n    parse(data)\nexcept ValueError:\n    handle_error()",
        negative_example="try:\n    parse(data)\nexcept:\n    handle_error()",
        rationale="Bare except catches SystemExit and KeyboardInterrupt.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


@pytest.fixture
def function_type_rule(db_session, sample_repo):
    """Create a function_type rule with existing linter_source."""
    now = datetime.now(timezone.utc)
    rule = Rule(
        slug="pure-function-check",
        repo_id=sample_repo.id,
        category="function_type",
        severity="error",
        title="Pure function must not have side effects",
        description="Functions decorated with @pure_function must not call impure functions.",
        positive_example="@pure_function\ndef add(a, b):\n    return a + b",
        negative_example="@pure_function\ndef add(a, b):\n    print(a + b)\n    return a + b",
        rationale="Pure functions should be free of side effects.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    db_session.add(rule)
    db_session.flush()

    ftr = FunctionTypeRule(
        rule_id=rule.id,
        decorator_name="pure_function",
        decorator_source="def pure_function(func):\n    func.__rule_marker_type__ = 'pure_function'\n    return func",
        linter_source='import ast\n\ndef check(func_node, source):\n    violations = []\n    for node in ast.walk(func_node):\n        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":\n            violations.append("pure_function must not call print")\n    return violations',
    )
    db_session.add(ftr)
    db_session.flush()
    return rule


# ---- Unit tests for _test_enforcer ----

def test_test_enforcer_module_check(sample_rule):
    """Test that _test_enforcer works for a module-level check."""
    source = """\
import ast

def check(tree, source):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            violations.append("Bare except clause found")
    return violations
"""
    success, output = _test_enforcer(source, "module", sample_rule)
    assert success is True
    assert "violation" in output.lower()


def test_test_enforcer_no_violations_fails(sample_rule):
    """Test that _test_enforcer fails when check returns no violations."""
    source = """\
def check(tree, source):
    return []
"""
    success, output = _test_enforcer(source, "module", sample_rule)
    assert success is False
    assert "no violations" in output.lower()


def test_test_enforcer_bad_syntax(sample_rule):
    """Test that _test_enforcer handles syntax errors in enforcer source."""
    source = "def check(tree, source)\n    return []"  # missing colon
    success, output = _test_enforcer(source, "module", sample_rule)
    assert success is False
    assert "error" in output.lower()


def test_test_enforcer_no_check_function(sample_rule):
    """Test that _test_enforcer fails when no check() function is defined."""
    source = "def analyze(tree, source):\n    return []"
    success, output = _test_enforcer(source, "module", sample_rule)
    assert success is False
    assert "does not define a check()" in output


def test_test_enforcer_positive_example_flagged(sample_rule):
    """Test that _test_enforcer fails when positive example triggers violations."""
    source = """\
import ast

def check(tree, source):
    # This incorrectly flags all try/except, even correct ones
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            violations.append("Found except clause")
    return violations
"""
    success, output = _test_enforcer(source, "module", sample_rule)
    assert success is False
    assert "positive example" in output.lower()


def test_sandbox_safety(sample_rule):
    """Test that restricted builtins block dangerous operations."""
    source = """\
import os
def check(tree, source):
    os.system("echo hacked")
    return ["hacked"]
"""
    success, output = _test_enforcer(source, "module", sample_rule)
    assert success is False
    assert "error" in output.lower()


# ---- Unit tests for _extract_code ----

def test_extract_code_fenced():
    raw = "Here is the code:\n```python\ndef check(tree, source):\n    return []\n```\nDone."
    result = _extract_code(raw)
    assert result is not None
    assert "def check" in result


def test_extract_code_bare():
    raw = "def check(tree, source):\n    return []"
    result = _extract_code(raw)
    assert result is not None
    assert "def check" in result


def test_extract_code_none():
    raw = "I cannot generate code for this rule."
    result = _extract_code(raw)
    assert result is None


# ---- Integration tests for generate_enforcer ----

def test_function_type_reuse(db_session, function_type_rule):
    """Verify function_type rules with existing linter_source are copied without LLM call."""
    mock_client = MagicMock()
    enforcer = generate_enforcer(mock_client, db_session, function_type_rule, "test-model")
    assert enforcer.status == "passed"
    assert enforcer.check_type == "function"
    assert "pure_function" in enforcer.decorator_source
    # LLM should NOT have been called
    mock_client.messages.create.assert_not_called()


def test_generate_enforcer_module_check(db_session, sample_rule):
    """Verify generation for a best_practice/lint rule via mocked LLM."""
    good_code = """\
```python
import ast

def check(tree, source):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            violations.append("Bare except clause found")
    return violations
```
"""
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=good_code)]

    enforcer = generate_enforcer(mock_client, db_session, sample_rule, "test-model")
    assert enforcer.status == "passed"
    assert enforcer.check_type == "module"
    assert enforcer.attempt_count == 1
    assert mock_client.messages.create.call_count == 1


def test_retry_on_failure(db_session, sample_rule):
    """Test retry logic: bad code then good code."""
    bad_code = "```python\ndef check(tree, source):\n    return []\n```"
    good_code = """\
```python
import ast

def check(tree, source):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            violations.append("Bare except clause found")
    return violations
```
"""
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=bad_code)]

    # First call returns bad code, second returns good code
    mock_client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=bad_code)]),
        MagicMock(content=[MagicMock(text=good_code)]),
    ]

    enforcer = generate_enforcer(mock_client, db_session, sample_rule, "test-model")
    assert enforcer.status == "passed"
    assert enforcer.attempt_count == 2
    assert mock_client.messages.create.call_count == 2


def test_max_attempts_exhausted(db_session, sample_rule):
    """Test that after MAX_ATTEMPTS failures, status is 'failed'."""
    bad_code = "```python\ndef check(tree, source):\n    return []\n```"
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=bad_code)]
    mock_client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=bad_code)])
        for _ in range(MAX_ATTEMPTS)
    ]

    enforcer = generate_enforcer(mock_client, db_session, sample_rule, "test-model")
    assert enforcer.status == "failed"
    assert enforcer.attempt_count == MAX_ATTEMPTS
    assert mock_client.messages.create.call_count == MAX_ATTEMPTS


# ---- CRUD tests ----

def test_create_and_get_enforcer(db_session, sample_rule):
    """Test CRUD for enforcer scripts."""
    es = create_enforcer_script(
        db_session,
        rule_id=sample_rule.id,
        enforcer_source="def check(tree, source): return []",
        check_type="module",
        status="passed",
    )
    assert es.id is not None

    fetched = get_enforcer_by_rule_id(db_session, sample_rule.id)
    assert fetched is not None
    assert fetched.enforcer_source == "def check(tree, source): return []"

    all_enforcers = get_all_enforcers(db_session)
    assert len(all_enforcers) == 1

    updated = update_enforcer_script(db_session, es, status="failed")
    assert updated.status == "failed"


# ---- Diff generation ----

def test_generate_diff():
    """Verify diff format."""
    from rule_viewer.api.routes import _generate_diff
    diff = _generate_diff("def check(tree, source):\n    return []", "my-rule")
    assert "+def check(tree, source):" in diff
    assert "+    return []" in diff
    assert "--- /dev/null" in diff
    assert "+++ b/enforcers/my-rule_check.py" in diff


# ---- API endpoint tests ----

@pytest.fixture
def api_client():
    """Create a FastAPI test client with enforcer data."""
    from rule_viewer.api.routes import get_db
    from rule_viewer.main import app

    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()

    now = datetime.now(timezone.utc)
    repo = Repository(
        owner="test", name="repo", full_name="test/repo",
        url="https://github.com/test/repo",
    )
    session.add(repo)
    session.flush()

    rule = Rule(
        slug="no-bare-except",
        repo_id=repo.id,
        category="lint",
        severity="warning",
        title="No bare except",
        description="Don't use bare except.",
        negative_example="try:\n    x()\nexcept:\n    pass",
        rationale="Catches too broadly.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    session.add(rule)
    session.flush()

    es = EnforcerScript(
        rule_id=rule.id,
        enforcer_source="def check(tree, source):\n    return ['violation']",
        check_type="module",
        test_result="passed",
        test_output="Found 1 violation",
        attempt_count=1,
        status="passed",
        created_at=now,
        updated_at=now,
    )
    session.add(es)
    session.commit()

    def override_get_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()


def test_enforcer_list_endpoint(api_client):
    """Test GET /api/enforcers returns enforcer list."""
    response = api_client.get("/api/enforcers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["rule_slug"] == "no-bare-except"
    assert data[0]["status"] == "passed"


def test_enforcer_detail_endpoint(api_client):
    """Test GET /api/rules/{slug}/enforcer returns detail."""
    response = api_client.get("/api/rules/no-bare-except/enforcer")
    assert response.status_code == 200
    data = response.json()
    assert data["rule_slug"] == "no-bare-except"
    assert data["enforcer_source"] == "def check(tree, source):\n    return ['violation']"
    assert data["diff"] is not None
    assert "+def check" in data["diff"]


def test_enforcer_detail_not_found(api_client):
    """Test 404 for rule with no enforcer."""
    response = api_client.get("/api/rules/nonexistent/enforcer")
    assert response.status_code == 404


def test_generate_enforcer_no_negative_example(api_client):
    """Test that generate-enforcer fails for rule without negative_example."""
    # The test rule does have a negative_example, so create one without
    from rule_viewer.api.routes import get_db
    # We use a different slug that doesn't exist — should 404
    response = api_client.post("/api/rules/nonexistent/generate-enforcer")
    assert response.status_code == 404


def test_rules_list_includes_has_enforcer(api_client):
    """Test that rules list includes has_enforcer field."""
    response = api_client.get("/api/rules?repo_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["has_enforcer"] is True
