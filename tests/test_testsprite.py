"""Tests for the TestSprite integration feature."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from code_ruler.db.models import Rule, TestSpriteResult
from code_ruler.db.repository import (
    create_testsprite_result,
    get_all_testsprite_results,
    get_testsprite_result,
    get_testsprite_results_by_rule_id,
    update_testsprite_result,
)
from github_extractor.models import Base, Repository

# Ensure all models are imported before create_all
import code_ruler.db.models  # noqa: F401


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
    """Create a sample rule."""
    now = datetime.now(timezone.utc)
    rule = Rule(
        slug="no-bare-except",
        repo_id=sample_repo.id,
        category="lint",
        severity="warning",
        title="No bare except",
        description="Don't use bare except.",
        positive_example="try:\n    parse(data)\nexcept ValueError:\n    handle_error()",
        negative_example="try:\n    parse(data)\nexcept:\n    handle_error()",
        rationale="Catches too broadly.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


@pytest.fixture
def second_rule(db_session, sample_repo):
    """Create a second rule for multi-rule tests."""
    now = datetime.now(timezone.utc)
    rule = Rule(
        slug="use-pathlib",
        repo_id=sample_repo.id,
        category="best_practice",
        severity="info",
        title="Use pathlib",
        description="Prefer pathlib.Path over os.path.",
        rationale="Pathlib is more readable.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    db_session.add(rule)
    db_session.flush()
    return rule


# ---- CRUD tests ----

def test_create_testsprite_result(db_session, sample_rule):
    """Test creating a TestSprite result record."""
    result = create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="pending",
    )
    assert result.id is not None
    assert result.rule_id == sample_rule.id
    assert result.repo_url == "https://github.com/test/repo"
    assert result.status == "pending"
    assert result.created_at is not None
    assert result.updated_at is not None


def test_get_testsprite_result_by_id(db_session, sample_rule):
    """Test fetching a TestSprite result by ID."""
    result = create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
    )
    fetched = get_testsprite_result(db_session, result.id)
    assert fetched is not None
    assert fetched.id == result.id
    assert fetched.rule_id == sample_rule.id


def test_get_testsprite_result_not_found(db_session):
    """Test fetching a nonexistent TestSprite result returns None."""
    fetched = get_testsprite_result(db_session, 999)
    assert fetched is None


def test_get_testsprite_results_by_rule_id(db_session, sample_rule):
    """Test listing TestSprite results for a specific rule."""
    create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="completed",
    )
    create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="failed",
    )
    results = get_testsprite_results_by_rule_id(db_session, sample_rule.id)
    assert len(results) == 2
    # Most recent first
    assert results[0].status == "failed"
    assert results[1].status == "completed"


def test_get_testsprite_results_by_rule_id_empty(db_session, sample_rule):
    """Test that listing results for a rule with none returns empty list."""
    results = get_testsprite_results_by_rule_id(db_session, sample_rule.id)
    assert results == []


def test_update_testsprite_result(db_session, sample_rule):
    """Test updating a TestSprite result."""
    result = create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="pending",
    )
    original_updated = result.updated_at

    updated = update_testsprite_result(
        db_session,
        result,
        status="completed",
        generated_tests="def test_foo(): pass",
        diff="--- /dev/null\n+++ b/test.py\n+def test_foo(): pass",
        test_results_json={"passed": 1, "failed": 0},
    )
    assert updated.status == "completed"
    assert updated.generated_tests == "def test_foo(): pass"
    assert updated.diff is not None
    assert updated.test_results_json == {"passed": 1, "failed": 0}
    assert updated.updated_at >= original_updated


def test_get_all_testsprite_results(db_session, sample_rule, second_rule):
    """Test listing all TestSprite results across rules."""
    create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="completed",
    )
    create_testsprite_result(
        db_session,
        rule_id=second_rule.id,
        repo_url="https://github.com/test/repo",
        status="pending",
    )
    all_results = get_all_testsprite_results(db_session)
    assert len(all_results) == 2


def test_get_all_testsprite_results_filtered_by_repo(db_session, sample_rule, sample_repo):
    """Test filtering TestSprite results by repo_id."""
    create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="completed",
    )
    results = get_all_testsprite_results(db_session, repo_id=sample_repo.id)
    assert len(results) == 1

    results_other = get_all_testsprite_results(db_session, repo_id=999)
    assert len(results_other) == 0


def test_multiple_results_per_rule(db_session, sample_rule):
    """Test that multiple TestSprite results can be created for the same rule."""
    for i in range(3):
        create_testsprite_result(
            db_session,
            rule_id=sample_rule.id,
            repo_url="https://github.com/test/repo",
            status="completed" if i < 2 else "failed",
        )
    results = get_testsprite_results_by_rule_id(db_session, sample_rule.id)
    assert len(results) == 3


def test_testsprite_result_relationship(db_session, sample_rule):
    """Test that the Rule.testsprite_results relationship works."""
    create_testsprite_result(
        db_session,
        rule_id=sample_rule.id,
        repo_url="https://github.com/test/repo",
        status="completed",
    )
    db_session.refresh(sample_rule)
    assert len(sample_rule.testsprite_results) == 1
    assert sample_rule.testsprite_results[0].status == "completed"


# ---- TestSprite client tests ----

@patch("code_ruler.testsprite.client._clone_repo")
@patch("code_ruler.testsprite.client._api_post")
def test_generate_tests_success(mock_api_post, mock_clone, db_session, sample_rule):
    """Test the full generate_tests flow with mocked API calls."""
    from code_ruler.testsprite.client import generate_tests

    mock_clone.return_value = None
    mock_api_post.side_effect = [
        # code summary response
        {"summary": "A Python project with error handling patterns."},
        # test plan response
        {"test_plan": {"tests": [{"name": "test_bare_except", "type": "unit"}]}},
        # generate and execute response
        {
            "generated_files": [],
            "test_results": {"passed": 1, "failed": 0},
            "generated_tests": "def test_bare_except():\n    assert True\n",
        },
    ]

    result = generate_tests(db_session, sample_rule, "https://github.com/test/repo")
    assert result.status == "completed"
    assert result.generated_tests == "def test_bare_except():\n    assert True\n"
    assert result.test_results_json == {"passed": 1, "failed": 0}
    assert result.test_plan_json == {"tests": [{"name": "test_bare_except", "type": "unit"}]}
    assert result.diff is not None
    assert "+def test_bare_except" in result.diff
    assert mock_api_post.call_count == 3


@patch("code_ruler.testsprite.client._clone_repo")
@patch("code_ruler.testsprite.client._api_post")
def test_generate_tests_clone_failure(mock_api_post, mock_clone, db_session, sample_rule):
    """Test that clone failure sets status to 'failed'."""
    from code_ruler.testsprite.client import generate_tests

    mock_clone.side_effect = Exception("git clone failed: repository not found")

    with pytest.raises(Exception, match="git clone failed"):
        generate_tests(db_session, sample_rule, "https://github.com/test/nonexistent")

    # The record should be persisted with failed status
    results = get_testsprite_results_by_rule_id(db_session, sample_rule.id)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "git clone failed" in results[0].error_message


@patch("code_ruler.testsprite.client._clone_repo")
@patch("code_ruler.testsprite.client._api_post")
def test_generate_tests_api_failure(mock_api_post, mock_clone, db_session, sample_rule):
    """Test that API failure during generation sets status to 'failed'."""
    from code_ruler.testsprite.client import generate_tests

    mock_clone.return_value = None
    mock_api_post.side_effect = [
        {"summary": "A Python project."},
        Exception("TestSprite API error: 500 Internal Server Error"),
    ]

    with pytest.raises(Exception, match="TestSprite API error"):
        generate_tests(db_session, sample_rule, "https://github.com/test/repo")

    results = get_testsprite_results_by_rule_id(db_session, sample_rule.id)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "TestSprite API error" in results[0].error_message


@patch("code_ruler.testsprite.client._clone_repo")
@patch("code_ruler.testsprite.client._api_post")
def test_generate_tests_status_transitions(mock_api_post, mock_clone, db_session, sample_rule):
    """Test that status transitions happen in correct order."""
    from code_ruler.testsprite.client import generate_tests

    observed_statuses = []

    original_update = update_testsprite_result.__wrapped__ if hasattr(update_testsprite_result, '__wrapped__') else None

    def track_status(session, result, **kwargs):
        if "status" in kwargs:
            observed_statuses.append(kwargs["status"])
        for key, value in kwargs.items():
            if hasattr(result, key):
                setattr(result, key, value)
        result.updated_at = datetime.now(timezone.utc)
        session.flush()
        return result

    mock_clone.return_value = None
    mock_api_post.side_effect = [
        {"summary": "Summary"},
        {"test_plan": {"tests": []}},
        {"generated_files": [], "test_results": {}, "generated_tests": ""},
    ]

    with patch("code_ruler.testsprite.client.update_testsprite_result", side_effect=track_status):
        generate_tests(db_session, sample_rule, "https://github.com/test/repo")

    # Should see: generating, (test_plan update has no status), running, completed
    assert "generating" in observed_statuses
    assert "running" in observed_statuses
    assert "completed" in observed_statuses
    # generating should come before running
    assert observed_statuses.index("generating") < observed_statuses.index("running")
    assert observed_statuses.index("running") < observed_statuses.index("completed")


# ---- Diff generation tests ----

def test_generate_diff():
    """Test unified diff generation from generated test content."""
    from code_ruler.testsprite.client import _generate_diff
    import tempfile, os

    tmpdir = tempfile.mkdtemp()
    test_file = os.path.join(tmpdir, "tests", "test_example.py")
    os.makedirs(os.path.dirname(test_file))
    with open(test_file, "w") as f:
        f.write("def test_foo():\n    assert True\n")

    diff = _generate_diff(tmpdir, [test_file])
    assert "--- /dev/null" in diff
    assert "+++ b/tests/test_example.py" in diff
    assert "+def test_foo():" in diff
    assert "+    assert True" in diff

    import shutil
    shutil.rmtree(tmpdir)


# ---- API endpoint tests ----

@pytest.fixture
def api_client():
    """Create a FastAPI test client with TestSprite data."""
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

    rule2 = Rule(
        slug="use-pathlib",
        repo_id=repo.id,
        category="best_practice",
        severity="info",
        title="Use pathlib",
        description="Prefer pathlib.",
        rationale="More readable.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    session.add(rule2)
    session.flush()

    ts_result = TestSpriteResult(
        rule_id=rule.id,
        repo_url="https://github.com/test/repo",
        status="completed",
        test_plan_json={"tests": [{"name": "test_no_bare_except"}]},
        generated_tests="def test_no_bare_except():\n    assert True\n",
        test_results_json={"passed": 1, "failed": 0},
        diff="--- /dev/null\n+++ b/tests/test_no_bare_except.py\n+def test_no_bare_except():\n+    assert True",
        created_at=now,
        updated_at=now,
    )
    session.add(ts_result)

    ts_result_failed = TestSpriteResult(
        rule_id=rule.id,
        repo_url="https://github.com/test/repo",
        status="failed",
        error_message="Clone failed",
        created_at=now,
        updated_at=now,
    )
    session.add(ts_result_failed)
    session.commit()

    def override_get_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), repo, rule, rule2, ts_result, ts_result_failed
    app.dependency_overrides.clear()
    session.close()


def test_list_testsprite_results(api_client):
    """Test GET /api/testsprite returns all results."""
    client, repo, *_ = api_client
    response = client.get("/api/testsprite")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_testsprite_results_filtered_by_repo(api_client):
    """Test GET /api/testsprite?repo_id=X filters by repo."""
    client, repo, *_ = api_client
    response = client.get(f"/api/testsprite?repo_id={repo.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    for item in data:
        assert item["rule_slug"] == "no-bare-except"

    response = client.get("/api/testsprite?repo_id=999")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_list_testsprite_results_schema(api_client):
    """Test that list items have the expected schema fields."""
    client, *_ = api_client
    response = client.get("/api/testsprite")
    data = response.json()
    item = data[0]
    assert "id" in item
    assert "rule_slug" in item
    assert "rule_title" in item
    assert "repo_url" in item
    assert "status" in item
    assert "created_at" in item


def test_list_rule_testsprite_results(api_client):
    """Test GET /api/rules/{slug}/testsprite returns results for a rule."""
    client, *_ = api_client
    response = client.get("/api/rules/no-bare-except/testsprite")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["rule_slug"] == "no-bare-except" for item in data)


def test_list_rule_testsprite_results_empty(api_client):
    """Test GET /api/rules/{slug}/testsprite returns empty for rule with no results."""
    client, *_ = api_client
    response = client.get("/api/rules/use-pathlib/testsprite")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_list_rule_testsprite_results_not_found(api_client):
    """Test 404 for nonexistent rule slug."""
    client, *_ = api_client
    response = client.get("/api/rules/nonexistent/testsprite")
    assert response.status_code == 404


def test_get_testsprite_detail(api_client):
    """Test GET /api/testsprite/{result_id} returns full detail."""
    client, _, _, _, ts_result, _ = api_client
    response = client.get(f"/api/testsprite/{ts_result.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ts_result.id
    assert data["rule_slug"] == "no-bare-except"
    assert data["rule_title"] == "No bare except"
    assert data["status"] == "completed"
    assert data["generated_tests"] == "def test_no_bare_except():\n    assert True\n"
    assert data["test_results"] == {"passed": 1, "failed": 0}
    assert data["test_plan"] == {"tests": [{"name": "test_no_bare_except"}]}
    assert data["diff"] is not None
    assert "+def test_no_bare_except" in data["diff"]
    assert data["error_message"] is None
    assert "created_at" in data
    assert "updated_at" in data


def test_get_testsprite_detail_failed(api_client):
    """Test GET /api/testsprite/{result_id} for a failed result includes error."""
    client, _, _, _, _, ts_failed = api_client
    response = client.get(f"/api/testsprite/{ts_failed.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "Clone failed"
    assert data["generated_tests"] is None


def test_get_testsprite_detail_not_found(api_client):
    """Test 404 for nonexistent TestSprite result."""
    client, *_ = api_client
    response = client.get("/api/testsprite/999")
    assert response.status_code == 404


def test_generate_testsprite_endpoint(api_client):
    """Test POST /api/rules/{slug}/generate-testsprite starts a job."""
    client, *_ = api_client
    with patch("rule_viewer.api.routes.start_generate_testsprite_job", return_value="abc123") as mock_start:
        response = client.post("/api/rules/no-bare-except/generate-testsprite")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "abc123"
    mock_start.assert_called_once_with("no-bare-except", "https://github.com/test/repo")


def test_generate_testsprite_rule_not_found(api_client):
    """Test 404 when generating TestSprite for nonexistent rule."""
    client, *_ = api_client
    response = client.post("/api/rules/nonexistent/generate-testsprite")
    assert response.status_code == 404


def test_generate_testsprite_conflict(api_client):
    """Test 409 when TestSprite generation is already in progress for same rule."""
    client, *_ = api_client
    from rule_viewer.api.pipeline import JobEvent, JobInfo

    mock_job = JobInfo(
        job_id="running123",
        kind="generate-testsprite",
        status="running",
        logs=[],
        events=[JobEvent(type="testsprite_start", data={"rule_slug": "no-bare-except"})],
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    with patch("rule_viewer.api.pipeline.get_all_jobs", return_value=[mock_job]):
        response = client.post("/api/rules/no-bare-except/generate-testsprite")
    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"]


def test_rules_list_includes_has_tests(api_client):
    """Test that rules list includes has_tests field."""
    client, repo, *_ = api_client
    response = client.get(f"/api/rules?repo_id={repo.id}")
    assert response.status_code == 200
    data = response.json()
    by_slug = {r["slug"]: r for r in data}
    # no-bare-except has TestSprite results
    assert by_slug["no-bare-except"]["has_tests"] is True
    # use-pathlib does not
    assert by_slug["use-pathlib"]["has_tests"] is False


def test_credentials_includes_testsprite(api_client):
    """Test that /api/credentials/status includes TestSprite service."""
    client, *_ = api_client
    with patch.dict("os.environ", {"TESTSPRITE_API_KEY": ""}, clear=False):
        response = client.get("/api/credentials/status")
    assert response.status_code == 200
    data = response.json()
    ts_services = [s for s in data["services"] if s["name"] == "TestSprite"]
    assert len(ts_services) == 1


def test_credentials_testsprite_configured(api_client):
    """Test that TestSprite shows as configured when API key is set."""
    client, *_ = api_client
    with patch.dict("os.environ", {"TESTSPRITE_API_KEY": "test-key-123"}, clear=False):
        response = client.get("/api/credentials/status")
    data = response.json()
    ts_services = [s for s in data["services"] if s["name"] == "TestSprite"]
    assert len(ts_services) == 1
    assert ts_services[0]["ok"] is True
    assert "configured" in ts_services[0]["detail"].lower()


def test_credentials_testsprite_not_configured(api_client):
    """Test that TestSprite shows as not configured when API key is missing."""
    client, *_ = api_client
    with patch.dict("os.environ", {"TESTSPRITE_API_KEY": ""}, clear=False):
        response = client.get("/api/credentials/status")
    data = response.json()
    ts_services = [s for s in data["services"] if s["name"] == "TestSprite"]
    assert len(ts_services) == 1
    assert ts_services[0]["ok"] is False
