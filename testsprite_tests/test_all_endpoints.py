"""TestSprite-generated comprehensive API endpoint tests.

Covers all 10 test cases (TC001-TC010) for 100% endpoint coverage
of rule_viewer/api/routes.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from code_ruler.db.models import (
    EnforcerScript,
    FunctionTypeRule,
    PipelineEvent,
    PipelineJob,
    Rule,
    RuleProvenance,
    TestSpriteResult,
)
from github_extractor.models import Base, PullRequest, Repository, ReviewComment
from rule_viewer.api.routes import get_db
from rule_viewer.main import app

# Ensure all models are imported before create_all
import code_ruler.db.models  # noqa: F401


@pytest.fixture
def test_db():
    """Create a test database with comprehensive sample data."""
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

    # Repository
    repo = Repository(
        owner="test", name="repo", full_name="test/repo",
        url="https://github.com/test/repo",
    )
    session.add(repo)
    session.flush()

    repo2 = Repository(
        owner="other", name="project", full_name="other/project",
        url="https://github.com/other/project",
    )
    session.add(repo2)
    session.flush()

    # Pull requests
    pr = PullRequest(
        repo_id=repo.id, number=42, title="Fix parser",
        body="PR body", author="dev", merged_at=now,
        merge_commit_sha="abc", base_branch="main",
        head_branch="fix", created_at=now, updated_at=now,
    )
    session.add(pr)
    session.flush()

    # Review comment
    comment = ReviewComment(
        pr_id=pr.id, github_id=1001, author="reviewer",
        body="Use specific exception", path="src/main.py",
        diff_hunk="@@ -1 +1 @@\n-except:\n+except ValueError:",
        created_at=now, updated_at=now,
    )
    session.add(comment)
    session.flush()

    # Rules
    rule1 = Rule(
        slug="no-bare-except", repo_id=repo.id, category="lint", severity="warning",
        title="No bare except", description="Don't use bare except.",
        positive_example="try:\n    x()\nexcept ValueError:\n    pass",
        negative_example="try:\n    x()\nexcept:\n    pass",
        rationale="Catches too broadly.", created_at=now, updated_at=now,
        version=1, is_active=True,
    )
    session.add(rule1)
    session.flush()

    rule2 = Rule(
        slug="use-pathlib", repo_id=repo.id, category="best_practice", severity="info",
        title="Use pathlib", description="Use pathlib instead of os.path.",
        rationale="More Pythonic.", created_at=now, updated_at=now,
        version=1, is_active=False,
    )
    session.add(rule2)
    session.flush()

    rule3 = Rule(
        slug="no-print", repo_id=repo.id, category="lint", severity="error",
        title="No print statements", description="Use logging instead of print.",
        negative_example="print('debug')",
        rationale="Print is not suitable for production.", created_at=now, updated_at=now,
        version=1, is_active=True,
    )
    session.add(rule3)
    session.flush()

    # Provenance
    prov = RuleProvenance(
        rule_id=rule1.id, pull_request_id=pr.id,
        review_comment_id=comment.id,
        extraction_notes="Test extraction",
        created_at=now,
    )
    session.add(prov)

    # FunctionTypeRule
    ftr = FunctionTypeRule(
        rule_id=rule1.id,
        decorator_name="@no_bare_except",
        decorator_source="def no_bare_except(fn): ...",
        linter_source="import ast\n...",
        constraints_json=["no bare except"],
    )
    session.add(ftr)
    session.flush()

    # EnforcerScript
    enforcer = EnforcerScript(
        rule_id=rule1.id,
        enforcer_source="import ast\ndef check(tree): ...",
        check_type="module",
        decorator_source="@enforce_no_bare_except",
        test_code="def test_enforcer(): ...",
        test_result="passed",
        test_output="1 passed",
        attempt_count=1,
        status="passed",
        dd_traces=[{"trace_id": "abc123"}],
        created_at=now,
        updated_at=now,
    )
    session.add(enforcer)
    session.flush()

    # PipelineJob + Event
    pj = PipelineJob(
        id="testjob001",
        job_type="extract-prs",
        status="completed",
        repo_url="https://github.com/test/repo",
        created_at=now,
        updated_at=now,
        finished_at=now,
    )
    session.add(pj)
    session.flush()

    pe = PipelineEvent(
        job_id=pj.id,
        event_type="pr_extracted",
        event_data_json={"pr_number": 42},
        created_at=now,
    )
    session.add(pe)

    # TestSpriteResult
    tsr = TestSpriteResult(
        rule_id=rule1.id,
        repo_url="https://github.com/test/repo",
        status="passed",
        created_at=now,
        updated_at=now,
    )
    session.add(tsr)

    session.commit()

    yield session, factory
    session.close()


@pytest.fixture
def client(test_db):
    """Create a FastAPI test client with DB override."""
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


# ── TC001: GET /api/repos ────────────────────────────────────────────────


class TestTC001GetAllRepositories:
    """Test the GET /api/repos endpoint."""

    def test_returns_repos_with_rule_counts(self, client, test_db):
        response = client.get("/api/repos")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        # Repos sorted by full_name
        assert data[0]["full_name"] == "other/project"
        assert data[1]["full_name"] == "test/repo"
        assert data[1]["total_rules"] >= 1
        for repo in data:
            assert "id" in repo
            assert "url" in repo

    def test_repos_empty_db(self, test_db):
        """Test with no repos."""
        session, factory = test_db
        # Use a clean DB
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        clean_factory = sessionmaker(bind=engine)

        def override():
            s = clean_factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override
        c = TestClient(app)
        response = c.get("/api/repos")
        assert response.status_code == 200
        assert response.json() == []
        app.dependency_overrides.clear()


# ── TC002: GET /api/rules ────────────────────────────────────────────────


class TestTC002ListRules:
    """Test the GET /api/rules endpoint with filters."""

    def test_list_all_rules_for_repo(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules?repo_id={repo.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_filter_by_category(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules?repo_id={repo.id}&category=lint")
        assert response.status_code == 200
        data = response.json()
        assert all(r["category"] == "lint" for r in data)
        assert len(data) == 2

    def test_filter_by_severity(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules?repo_id={repo.id}&severity=warning")
        assert response.status_code == 200
        data = response.json()
        assert all(r["severity"] == "warning" for r in data)

    def test_filter_by_is_active(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules?repo_id={repo.id}&is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert all(r["is_active"] is True for r in data)

        response = client.get(f"/api/rules?repo_id={repo.id}&is_active=false")
        assert response.status_code == 200
        data = response.json()
        assert all(r["is_active"] is False for r in data)
        assert len(data) == 1

    def test_search(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules?repo_id={repo.id}&search=pathlib")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["slug"] == "use-pathlib"

    def test_missing_repo_id_returns_422(self, client):
        response = client.get("/api/rules")
        assert response.status_code == 422

    def test_has_decorator_and_enforcer_flags(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules?repo_id={repo.id}")
        data = response.json()
        bare_except = next(r for r in data if r["slug"] == "no-bare-except")
        assert bare_except["has_decorator"] is True
        assert bare_except["has_enforcer"] is True
        assert bare_except["has_tests"] is True


# ── TC003: GET /api/rules/{slug} ─────────────────────────────────────────


class TestTC003GetRuleDetail:
    """Test the GET /api/rules/{slug} endpoint."""

    def test_get_existing_rule(self, client):
        response = client.get("/api/rules/no-bare-except")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "no-bare-except"
        assert data["category"] == "lint"
        assert data["version"] == 1
        assert data["decorator_name"] == "@no_bare_except"
        assert data["decorator_source"] is not None
        assert data["linter_source"] is not None
        assert data["constraints"] is not None

    def test_get_rule_with_repo_id(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/rules/no-bare-except?repo_id={repo.id}")
        assert response.status_code == 200

    def test_get_nonexistent_rule(self, client):
        response = client.get("/api/rules/nonexistent-slug")
        assert response.status_code == 404
        assert response.json()["detail"] == "Rule not found"

    def test_rule_without_decorator(self, client):
        response = client.get("/api/rules/use-pathlib")
        assert response.status_code == 200
        data = response.json()
        assert data["decorator_name"] is None
        assert data["decorator_source"] is None


# ── TC004: GET /api/rules/{slug}/provenance ──────────────────────────────


class TestTC004GetProvenance:
    """Test the GET /api/rules/{slug}/provenance endpoint."""

    def test_get_provenance(self, client):
        response = client.get("/api/rules/no-bare-except/provenance")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["pr_number"] == 42
        assert item["pr_title"] == "Fix parser"
        assert item["comment_author"] == "reviewer"
        assert item["comment_body"] == "Use specific exception"
        assert item["file_path"] == "src/main.py"
        assert "diff_hunk" in item
        assert item["extraction_notes"] == "Test extraction"

    def test_provenance_nonexistent_rule(self, client):
        response = client.get("/api/rules/nonexistent/provenance")
        assert response.status_code == 404

    def test_provenance_rule_with_no_provenance(self, client):
        response = client.get("/api/rules/use-pathlib/provenance")
        assert response.status_code == 200
        assert response.json() == []


# ── TC005: POST /api/rules/{slug}/generate-enforcer ──────────────────────


class TestTC005GenerateEnforcer:
    """Test the POST /api/rules/{slug}/generate-enforcer endpoint."""

    @patch("rule_viewer.api.routes.start_generate_enforcer_job", return_value="job123")
    def test_success(self, mock_start, client):
        response = client.post("/api/rules/no-print/generate-enforcer")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job123"

    def test_rule_not_found(self, client):
        response = client.post("/api/rules/nonexistent/generate-enforcer")
        assert response.status_code == 404

    def test_rule_without_negative_example(self, client):
        response = client.post("/api/rules/use-pathlib/generate-enforcer")
        assert response.status_code == 400
        assert "negative_example" in response.json()["detail"]

    @patch("rule_viewer.api.pipeline.get_all_jobs")
    def test_conflict_when_already_in_progress(self, mock_jobs, client):
        from rule_viewer.api.pipeline import JobEvent, JobInfo

        mock_jobs.return_value = [
            JobInfo(
                job_id="existing",
                kind="generate-enforcer",
                status="running",
                logs=[],
                events=[JobEvent(type="start", data={"rule_slug": "no-print"})],
                started_at="2026-01-01T00:00:00Z",
            )
        ]
        response = client.post("/api/rules/no-print/generate-enforcer")
        assert response.status_code == 409


# ── TC006: GET /api/enforcers ────────────────────────────────────────────


class TestTC006ListEnforcers:
    """Test the GET /api/enforcers endpoint."""

    def test_list_all_enforcers(self, client):
        response = client.get("/api/enforcers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        item = data[0]
        assert "rule_slug" in item
        assert "status" in item
        assert "check_type" in item

    def test_filter_by_repo_id(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/enforcers?repo_id={repo.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_filter_by_nonexistent_repo(self, client):
        response = client.get("/api/enforcers?repo_id=99999")
        assert response.status_code == 200
        assert response.json() == []


# ── TC007: GET /api/rules/{slug}/enforcer ────────────────────────────────


class TestTC007GetEnforcerDetail:
    """Test the GET /api/rules/{slug}/enforcer endpoint."""

    def test_get_enforcer(self, client):
        response = client.get("/api/rules/no-bare-except/enforcer")
        assert response.status_code == 200
        data = response.json()
        assert data["rule_slug"] == "no-bare-except"
        assert data["status"] == "passed"
        assert data["check_type"] == "module"
        assert data["enforcer_source"] is not None
        assert data["decorator_source"] is not None
        assert data["test_code"] is not None
        assert data["test_result"] == "passed"
        assert data["diff"] is not None
        assert data["dd_traces"] == [{"trace_id": "abc123"}]

    def test_rule_not_found(self, client):
        response = client.get("/api/rules/nonexistent/enforcer")
        assert response.status_code == 404

    def test_rule_without_enforcer(self, client):
        response = client.get("/api/rules/use-pathlib/enforcer")
        assert response.status_code == 404
        assert response.json()["detail"] == "No enforcer script for this rule"


# ── TC008: POST /api/rules/{slug}/generate-video ─────────────────────────


class TestTC008SubmitVideoGeneration:
    """Test the POST /api/rules/{slug}/generate-video endpoint."""

    @patch("code_ruler.video.minimax_client.submit_image_to_video", return_value="task123")
    @patch("code_ruler.video.image_renderer.render_rule_image", return_value=b"fake_image")
    def test_success_with_prompt(self, mock_render, mock_submit, client):
        response = client.post(
            "/api/rules/no-bare-except/generate-video",
            json={"prompt": "Show the rule in action"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task123"
        assert data["status"] == "Processing"

    @patch("code_ruler.video.minimax_client.submit_image_to_video", return_value="task456")
    @patch("code_ruler.video.image_renderer.render_rule_image", return_value=b"fake_image")
    def test_success_without_prompt(self, mock_render, mock_submit, client):
        response = client.post(
            "/api/rules/no-bare-except/generate-video",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task456"

    def test_rule_not_found(self, client):
        response = client.post(
            "/api/rules/nonexistent/generate-video",
            json={"prompt": "test"},
        )
        assert response.status_code == 404


# ── TC009: GET /api/video/{task_id} ──────────────────────────────────────


class TestTC009PollVideoStatus:
    """Test the GET /api/video/{task_id} endpoint."""

    @patch("code_ruler.video.minimax_client.get_api_key", return_value="fake-key")
    def test_processing_status(self, mock_key, client):
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"status": "Queueing"}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            response = client.get("/api/video/task123")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Processing"

    @patch("code_ruler.video.minimax_client.get_api_key", return_value="fake-key")
    @patch("code_ruler.video.minimax_client.get_video_download_url", return_value="https://example.com/video.mp4")
    def test_success_status(self, mock_download, mock_key, client):
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"status": "Success", "file_id": "file123"}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            response = client.get("/api/video/task123")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Success"
            assert data["file_id"] == "file123"
            assert data["download_url"] == "https://example.com/video.mp4"

    @patch("code_ruler.video.minimax_client.get_api_key", return_value="fake-key")
    def test_fail_status(self, mock_key, client):
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"status": "Fail", "error": "Generation error"}
            mock_resp.raise_for_status = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            response = client.get("/api/video/task123")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Fail"
            assert data["error"] == "Generation error"


# ── TC010: GET /api/credentials/status ───────────────────────────────────


class TestTC010CredentialsStatus:
    """Test the GET /api/credentials/status endpoint."""

    @patch.dict("os.environ", {"DD_API_KEY": "", "GITHUB_TOKEN": ""}, clear=False)
    @patch("boto3.client")
    def test_all_services_checked(self, mock_boto, client):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456"}
        mock_boto.return_value = mock_sts

        response = client.get("/api/credentials/status")
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        services = {s["name"]: s for s in data["services"]}
        assert "AWS Bedrock" in services
        assert services["AWS Bedrock"]["ok"] is True
        assert "Datadog" in services
        assert services["Datadog"]["ok"] is False  # no key
        assert "GitHub" in services
        assert services["GitHub"]["ok"] is False  # no token

    @patch.dict("os.environ", {"DD_API_KEY": "", "GITHUB_TOKEN": ""}, clear=False)
    @patch("boto3.client", side_effect=Exception("No AWS credentials"))
    def test_bedrock_failure(self, mock_boto, client):
        response = client.get("/api/credentials/status")
        assert response.status_code == 200
        data = response.json()
        services = {s["name"]: s for s in data["services"]}
        assert services["AWS Bedrock"]["ok"] is False


# ── Additional coverage: stats, pipeline, repo-stats ─────────────────────


class TestStats:
    """Test the GET /api/stats endpoint."""

    def test_get_stats(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_rules"] == 3
        assert "lint" in data["rules_by_category"]
        assert data["total_prs_processed"] == 1

    def test_get_stats_with_repo_id(self, client, test_db):
        session, _ = test_db
        repo = session.query(Repository).filter_by(full_name="test/repo").first()
        response = client.get(f"/api/stats?repo_id={repo.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total_rules"] == 3


class TestPipelineJobs:
    """Test pipeline job endpoints."""

    @patch("rule_viewer.api.routes.start_extract_prs_job", return_value="job001")
    def test_start_extract_prs(self, mock_start, client):
        response = client.post(
            "/api/pipeline/extract-prs",
            json={"repo_url": "https://github.com/test/repo"},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job001"

    @patch("rule_viewer.api.routes.start_extract_rules_job", return_value="job002")
    def test_start_extract_rules(self, mock_start, client):
        response = client.post(
            "/api/pipeline/extract-rules",
            json={"limit": 10},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job002"

    @patch("rule_viewer.api.routes.start_quick_fetch_prs_job", return_value="job003")
    def test_quick_fetch_prs(self, mock_start, client):
        response = client.post(
            "/api/pipeline/quick-fetch-prs",
            json={"repo_url": "https://github.com/test/repo"},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job003"

    @patch("rule_viewer.api.routes.start_quick_extract_rules_job", return_value="job004")
    def test_quick_extract_rules(self, mock_start, client):
        response = client.post(
            "/api/pipeline/quick-extract-rules",
            json={"limit": 5},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job004"

    @patch("rule_viewer.api.routes.start_quick_run_job", return_value="job005")
    def test_quick_run(self, mock_start, client):
        response = client.post(
            "/api/pipeline/quick-run",
            json={"repo_url": "https://github.com/test/repo", "pr_limit": 5},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job005"

    def test_get_job_not_found(self, client):
        response = client.get("/api/pipeline/jobs/nonexistent")
        assert response.status_code == 404

    def test_get_job_steps(self, client):
        response = client.get("/api/pipeline/jobs/testjob001/steps")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["event_type"] == "pr_extracted"

    def test_get_job_steps_not_found(self, client):
        response = client.get("/api/pipeline/jobs/nonexistent/steps")
        assert response.status_code == 404


class TestRepoStats:
    """Test the GET /api/pipeline/repo-stats endpoint."""

    def test_get_repo_stats(self, client):
        response = client.get("/api/pipeline/repo-stats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        item = next(r for r in data if r["full_name"] == "test/repo")
        assert "total_prs" in item
        assert "processed_comments" in item
        assert "unprocessed_comments" in item
