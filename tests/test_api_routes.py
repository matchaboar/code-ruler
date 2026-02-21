"""Tests for rule_viewer FastAPI endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from code_ruler.db.models import Rule, RuleProvenance
from github_extractor.models import Base, PullRequest, Repository, ReviewComment
from rule_viewer.api.routes import get_db
from rule_viewer.main import app

# Ensure all models are imported before create_all
import code_ruler.db.models  # noqa: F401


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    from sqlalchemy.pool import StaticPool

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

    pr = PullRequest(
        repo_id=repo.id, number=42, title="Fix parser",
        body="PR body", author="dev", merged_at=now,
        merge_commit_sha="abc", base_branch="main",
        head_branch="fix", created_at=now, updated_at=now,
    )
    session.add(pr)
    session.flush()

    comment = ReviewComment(
        pr_id=pr.id, github_id=1001, author="reviewer",
        body="Use specific exception", path="src/main.py",
        diff_hunk="@@ -1 +1 @@\n-except:\n+except ValueError:",
        created_at=now, updated_at=now,
    )
    session.add(comment)
    session.flush()

    rule = Rule(
        slug="no-bare-except", category="lint", severity="warning",
        title="No bare except", description="Don't use bare except.",
        rationale="Catches too broadly.", created_at=now, updated_at=now,
        version=1, is_active=True,
    )
    session.add(rule)
    session.flush()

    prov = RuleProvenance(
        rule_id=rule.id, pull_request_id=pr.id,
        review_comment_id=comment.id,
        extraction_notes="Test extraction",
        created_at=now,
    )
    session.add(prov)
    session.commit()

    yield session, factory
    session.close()


@pytest.fixture
def client(test_db):
    """Create a FastAPI test client."""
    session, factory = test_db

    def override_get_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_rules(client):
    """Test GET /api/rules returns rules."""
    response = client.get("/api/rules")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["slug"] == "no-bare-except"


def test_list_rules_filter_category(client):
    """Test filtering rules by category."""
    response = client.get("/api/rules?category=lint")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/api/rules?category=best_practice")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_rule_detail(client):
    """Test GET /api/rules/{slug}."""
    response = client.get("/api/rules/no-bare-except")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "no-bare-except"
    assert data["category"] == "lint"
    assert data["version"] == 1


def test_get_rule_not_found(client):
    """Test 404 for nonexistent rule."""
    response = client.get("/api/rules/nonexistent")
    assert response.status_code == 404


def test_get_provenance(client):
    """Test GET /api/rules/{slug}/provenance."""
    response = client.get("/api/rules/no-bare-except/provenance")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["pr_number"] == 42
    assert data[0]["comment_author"] == "reviewer"


def test_get_stats(client):
    """Test GET /api/stats."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_rules"] == 1
    assert data["rules_by_category"]["lint"] == 1
