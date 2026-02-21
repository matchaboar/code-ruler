"""Tests for DBOS durable workflow refactor (phases 1-6).

These tests exercise the new DB models, event helpers, workflow step functions,
and API endpoints without requiring a running Postgres or DBOS runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import code_ruler.db.models  # noqa: F401 — register all models
from code_ruler.db.models import PipelineEvent, PipelineJob, Rule, RuleProvenance
from github_extractor.models import Base, PullRequest, Repository, ReviewComment
from rule_viewer.api.routes import get_db
from rule_viewer.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all tables."""
    engine = create_engine(
        "sqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    factory = sessionmaker(bind=db_engine)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture
def db_factory(db_engine):
    return sessionmaker(bind=db_engine)


@pytest.fixture
def client(db_engine):
    """FastAPI test client wired to the in-memory DB."""
    factory = sessionmaker(bind=db_engine)

    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_dbos_flag():
    """Ensure _dbos_launched is reset between tests."""
    import rule_viewer.api.pipeline as mod
    original = mod._dbos_launched
    yield
    mod._dbos_launched = original


# ---------------------------------------------------------------------------
# Phase 1: _dbos_enabled flag
# ---------------------------------------------------------------------------

class TestDbosEnabledFlag:
    def test_disabled_by_default(self):
        from rule_viewer.api.pipeline import _dbos_enabled
        import rule_viewer.api.pipeline as mod
        mod._dbos_launched = False
        assert _dbos_enabled() is False

    def test_enabled_after_mark(self):
        from rule_viewer.api.pipeline import _dbos_enabled, mark_dbos_launched
        import rule_viewer.api.pipeline as mod
        mod._dbos_launched = False
        mark_dbos_launched()
        assert _dbos_enabled() is True


# ---------------------------------------------------------------------------
# Phase 5: PipelineJob / PipelineEvent models
# ---------------------------------------------------------------------------

class TestPipelineJobModel:
    def test_create_pipeline_job(self, db_session: Session):
        now = datetime.now(timezone.utc)
        job = PipelineJob(
            id="test-123", workflow_id="wf-123", job_type="extract-prs",
            status="running", repo_url="https://github.com/o/r",
            params_json={"limit": 10}, created_at=now, updated_at=now,
        )
        db_session.add(job)
        db_session.commit()

        loaded = db_session.get(PipelineJob, "test-123")
        assert loaded is not None
        assert loaded.job_type == "extract-prs"
        assert loaded.workflow_id == "wf-123"
        assert loaded.params_json == {"limit": 10}

    def test_create_pipeline_event(self, db_session: Session):
        now = datetime.now(timezone.utc)
        job = PipelineJob(
            id="j1", job_type="extract-rules", status="running",
            created_at=now, updated_at=now,
        )
        db_session.add(job)
        db_session.flush()

        event = PipelineEvent(
            job_id="j1", event_type="review_start",
            event_data_json={"pr_number": 42}, created_at=now,
        )
        db_session.add(event)
        db_session.commit()

        events = db_session.query(PipelineEvent).filter_by(job_id="j1").all()
        assert len(events) == 1
        assert events[0].event_type == "review_start"
        assert events[0].event_data_json["pr_number"] == 42

    def test_job_events_relationship(self, db_session: Session):
        now = datetime.now(timezone.utc)
        job = PipelineJob(
            id="j2", job_type="quick-run", status="running",
            created_at=now, updated_at=now,
        )
        db_session.add(job)
        db_session.flush()
        for i in range(3):
            db_session.add(PipelineEvent(
                job_id="j2", event_type=f"step_{i}",
                event_data_json={}, created_at=now,
            ))
        db_session.commit()

        db_session.refresh(job)
        assert len(job.events) == 3


# ---------------------------------------------------------------------------
# Phase 5: Event helpers (create_job, update_job_status, emit_event)
# ---------------------------------------------------------------------------

class TestEventHelpers:
    """Test events.py helpers using a temp SQLite DB file."""

    @pytest.fixture
    def tmp_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        return db_path, engine

    def _get_session(self, db_path):
        from code_ruler.db.base import get_engine, get_session_factory, init_db
        engine = get_engine(db_path)
        init_db(engine)
        return get_session_factory(engine)

    def test_create_job(self, tmp_db):
        db_path, _ = tmp_db
        from code_ruler.workflows.events import create_job

        create_job(db_path, "j1", "extract-prs", "https://github.com/o/r",
                   {"limit": 5}, workflow_id="wf-1")

        factory = self._get_session(db_path)
        with factory() as session:
            job = session.get(PipelineJob, "j1")
            assert job is not None
            assert job.status == "running"
            assert job.workflow_id == "wf-1"

    def test_create_job_idempotent(self, tmp_db):
        db_path, _ = tmp_db
        from code_ruler.workflows.events import create_job

        create_job(db_path, "j1", "extract-prs", None)
        create_job(db_path, "j1", "extract-prs", None)  # should not raise

        factory = self._get_session(db_path)
        with factory() as session:
            count = session.query(PipelineJob).filter_by(id="j1").count()
            assert count == 1

    def test_update_job_status(self, tmp_db):
        db_path, _ = tmp_db
        from code_ruler.workflows.events import create_job, update_job_status

        create_job(db_path, "j1", "extract-rules", None)
        update_job_status(db_path, "j1", "completed")

        factory = self._get_session(db_path)
        with factory() as session:
            job = session.get(PipelineJob, "j1")
            assert job.status == "completed"
            assert job.finished_at is not None

    def test_update_job_status_failed(self, tmp_db):
        db_path, _ = tmp_db
        from code_ruler.workflows.events import create_job, update_job_status

        create_job(db_path, "j1", "extract-rules", None)
        update_job_status(db_path, "j1", "failed", error="LLM timeout")

        factory = self._get_session(db_path)
        with factory() as session:
            job = session.get(PipelineJob, "j1")
            assert job.status == "failed"
            assert job.error_message == "LLM timeout"

    def test_emit_event(self, tmp_db):
        db_path, _ = tmp_db
        from code_ruler.workflows.events import create_job, emit_event

        create_job(db_path, "j1", "extract-rules", None)
        emit_event(db_path, "j1", "review_start", {"pr_number": 42})
        emit_event(db_path, "j1", "review_done", {"pr_number": 42, "candidates": []})

        factory = self._get_session(db_path)
        with factory() as session:
            events = session.query(PipelineEvent).filter_by(job_id="j1").all()
            assert len(events) == 2
            assert events[0].event_type == "review_start"
            assert events[1].event_type == "review_done"


# ---------------------------------------------------------------------------
# Phase 3: Workflow step functions (unit tests, no DBOS runtime)
# ---------------------------------------------------------------------------

class TestWorkflowSteps:
    """Test individual step functions outside of the DBOS runtime."""

    def test_build_contexts_step(self, tmp_path):
        """build_contexts_step queries unprocessed comments and returns dicts."""
        db_path = str(tmp_path / "test.db")
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)

        now = datetime.now(timezone.utc)
        with factory() as session:
            repo = Repository(
                owner="o", name="r", full_name="o/r",
                url="https://github.com/o/r",
            )
            session.add(repo)
            session.flush()
            pr = PullRequest(
                repo_id=repo.id, number=1, title="Fix", body="",
                author="dev", merged_at=now, merge_commit_sha="abc",
                base_branch="main", head_branch="fix",
                created_at=now, updated_at=now,
            )
            session.add(pr)
            session.flush()
            comment = ReviewComment(
                pr_id=pr.id, github_id=999, author="rev",
                body="Use typing", path="src/a.py",
                diff_hunk="@@ hunk @@", created_at=now, updated_at=now,
            )
            session.add(comment)
            session.commit()

        # Call the step function directly (outside DBOS)
        from code_ruler.workflows.rule_extraction import build_contexts_step
        contexts = build_contexts_step.__wrapped__(db_path, None, None)

        assert len(contexts) == 1
        assert contexts[0]["pr_number"] == 1
        assert contexts[0]["file_path"] == "src/a.py"
        assert contexts[0]["comment_author"] == "rev"

    def test_extract_rules_step_returns_candidates(self):
        """extract_rules_step calls LLM and returns serialized candidates."""
        from code_ruler.llm.schemas import CandidateRule
        from code_ruler.workflows.rule_extraction import extract_rules_step

        mock_candidate = CandidateRule(
            slug="no-bare-except", category="lint", severity="warning",
            title="No bare except", description="desc", rationale="reason",
        )

        ctx = {
            "repo_name": "o/r", "pr_number": 1, "pr_title": "Fix",
            "pr_author": "dev", "comment_author": "rev",
            "comment_body": "Use typing", "file_path": "a.py",
            "diff_hunk": "@@ hunk @@", "pr_id": 1, "review_comment_id": 1, "repo_id": 1,
        }

        with patch("code_ruler.llm.client.get_client") as mock_gc, \
             patch("code_ruler.extraction.rule_extractor.extract_rules_from_context",
                   return_value=[mock_candidate]):
            mock_gc.return_value = MagicMock()
            result = extract_rules_step.__wrapped__(ctx)

        assert len(result) == 1
        assert result[0]["slug"] == "no-bare-except"
        assert result[0]["category"] == "lint"

    def test_dedup_step_keep_both(self, tmp_path):
        """dedup_step returns keep_both when no existing rules."""
        db_path = str(tmp_path / "test.db")
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)

        from code_ruler.llm.schemas import MergeDecision
        from code_ruler.workflows.rule_extraction import dedup_step

        candidate = {
            "slug": "new-rule", "category": "lint", "severity": "info",
            "title": "New rule", "description": "desc", "rationale": "reason",
        }
        mock_decision = MergeDecision(
            action="keep_both", reasoning="No existing rules."
        )

        with patch("code_ruler.llm.client.get_client") as mock_gc, \
             patch("code_ruler.extraction.rule_deduplicator.check_duplicate",
                   return_value=mock_decision):
            mock_gc.return_value = MagicMock()
            result = dedup_step.__wrapped__(db_path, candidate)

        assert result["action"] == "keep_both"

    def test_store_rule_step(self, tmp_path):
        """store_rule_step creates a rule and provenance in DB."""
        db_path = str(tmp_path / "test.db")
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)

        # Create repo + PR for provenance FK
        now = datetime.now(timezone.utc)
        with factory() as session:
            repo = Repository(
                owner="o", name="r", full_name="o/r",
                url="https://github.com/o/r",
            )
            session.add(repo)
            session.flush()
            pr = PullRequest(
                repo_id=repo.id, number=1, title="Fix", body="",
                author="dev", merged_at=now, merge_commit_sha="abc",
                base_branch="main", head_branch="fix",
                created_at=now, updated_at=now,
            )
            session.add(pr)
            session.flush()
            comment = ReviewComment(
                pr_id=pr.id, github_id=999, author="rev",
                body="Use typing", path="src/a.py",
                diff_hunk="@@ hunk @@", created_at=now, updated_at=now,
            )
            session.add(comment)
            session.commit()
            repo_id = repo.id
            pr_id = pr.id
            comment_id = comment.id

        from code_ruler.workflows.rule_extraction import store_rule_step

        candidate = {
            "slug": "test-rule", "category": "best_practice", "severity": "info",
            "title": "Test Rule", "description": "desc",
            "rationale": "reason",
        }
        ctx = {"pr_id": pr_id, "review_comment_id": comment_id, "repo_id": repo_id}

        result = store_rule_step.__wrapped__(db_path, candidate, ctx)
        assert result["slug"] == "test-rule"

        with factory() as session:
            rule = session.query(Rule).filter_by(slug="test-rule").first()
            assert rule is not None
            prov = session.query(RuleProvenance).filter_by(rule_id=rule.id).first()
            assert prov is not None
            assert prov.review_comment_id == comment_id


# ---------------------------------------------------------------------------
# Phase 5 & 6: API endpoints (DBOS-enabled, using PipelineJob table)
# ---------------------------------------------------------------------------

class TestDbosApiEndpoints:
    """Test the new/updated API endpoints when DBOS is 'enabled'."""

    @pytest.fixture(autouse=True)
    def _enable_dbos(self):
        import rule_viewer.api.pipeline as mod
        mod._dbos_launched = True
        yield
        mod._dbos_launched = False

    @pytest.fixture
    def seeded_client(self, db_engine, client):
        """Client with a PipelineJob + events pre-seeded."""
        factory = sessionmaker(bind=db_engine)
        now = datetime.now(timezone.utc)
        with factory() as session:
            job = PipelineJob(
                id="j-abc", workflow_id="wf-abc", job_type="extract-prs",
                status="running", repo_url="https://github.com/o/r",
                params_json={"limit": 10}, created_at=now, updated_at=now,
            )
            session.add(job)
            session.flush()
            for i, etype in enumerate(["pr_extracted", "pr_skipped", "pr_extracted"]):
                session.add(PipelineEvent(
                    job_id="j-abc", event_type=etype,
                    event_data_json={"pr_number": i + 1}, created_at=now,
                ))
            session.commit()
        return client

    def test_list_jobs_from_db(self, seeded_client):
        resp = seeded_client.get("/api/pipeline/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["job_id"] == "j-abc"
        assert data[0]["kind"] == "extract-prs"
        assert data[0]["workflow_id"] == "wf-abc"

    def test_get_job_status_from_db(self, seeded_client):
        resp = seeded_client.get("/api/pipeline/jobs/j-abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "j-abc"
        assert data["status"] == "running"
        assert len(data["events"]) == 3
        assert data["events"][0]["type"] == "pr_extracted"

    def test_get_job_not_found(self, seeded_client):
        resp = seeded_client.get("/api/pipeline/jobs/nonexistent")
        assert resp.status_code == 404

    def test_get_job_steps(self, seeded_client):
        resp = seeded_client.get("/api/pipeline/jobs/j-abc/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["event_type"] == "pr_extracted"
        assert "pr_number" in data[0]["data"]

    def test_get_job_steps_not_found(self, client):
        resp = client.get("/api/pipeline/jobs/nonexistent/steps")
        assert resp.status_code == 404

    def test_cancel_job(self, seeded_client):
        with patch("dbos.DBOS.cancel_workflow") as mock_cancel:
            resp = seeded_client.post("/api/pipeline/jobs/j-abc/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        mock_cancel.assert_called_once_with("wf-abc")

        # Verify DB status updated
        resp2 = seeded_client.get("/api/pipeline/jobs/j-abc")
        assert resp2.json()["status"] == "cancelled"

    def test_cancel_job_not_found(self, client):
        resp = client.post("/api/pipeline/jobs/nonexistent/cancel")
        assert resp.status_code == 404

    def test_resume_requires_dbos(self, client):
        """Resume endpoint requires DBOS to be enabled."""
        import rule_viewer.api.pipeline as mod
        mod._dbos_launched = False
        resp = client.post("/api/pipeline/jobs/j-abc/resume")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Phase 4: Quick-batch endpoint schemas
# ---------------------------------------------------------------------------

class TestQuickBatchSchemas:
    def test_quick_fetch_request_defaults(self):
        from rule_viewer.api.schemas import QuickFetchRequest
        req = QuickFetchRequest(repo_url="https://github.com/o/r")
        assert req.limit == 10

    def test_quick_extract_request_defaults(self):
        from rule_viewer.api.schemas import QuickExtractRequest
        req = QuickExtractRequest()
        assert req.limit == 10
        assert req.repo_filter is None

    def test_job_status_response_has_workflow_id(self):
        from rule_viewer.api.schemas import JobStatusResponse
        resp = JobStatusResponse(
            job_id="x", kind="extract-prs", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
            workflow_id="wf-x",
        )
        assert resp.workflow_id == "wf-x"

    def test_job_status_response_workflow_id_optional(self):
        from rule_viewer.api.schemas import JobStatusResponse
        resp = JobStatusResponse(
            job_id="x", kind="extract-prs", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        assert resp.workflow_id is None


# ---------------------------------------------------------------------------
# Legacy path: ensure thread-based runner still works when DBOS is off
# ---------------------------------------------------------------------------

class TestLegacyPathStillWorks:
    """Verify that the legacy thread-based runner is used when DBOS is disabled."""

    @pytest.fixture(autouse=True)
    def _disable_dbos(self):
        import rule_viewer.api.pipeline as mod
        mod._dbos_launched = False

    def test_start_extract_prs_job_uses_thread(self):
        import rule_viewer.api.pipeline as mod
        mod._db_path = "/tmp/fake.db"

        with patch("github_extractor.client.create_github_client"), \
             patch("github_extractor.database.get_engine"), \
             patch("github_extractor.database.get_session_factory") as mock_sf, \
             patch("github_extractor.database.init_db"), \
             patch("github_extractor.extractor.extract_repo"):

            mock_session = MagicMock()
            mock_sf.return_value = MagicMock(return_value=mock_session)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)

            from rule_viewer.api.pipeline import _jobs, start_extract_prs_job
            job_id = start_extract_prs_job("https://github.com/o/r", limit=5)

            assert job_id in _jobs
            assert _jobs[job_id].kind == "extract-prs"

    def test_list_jobs_uses_memory(self, client):
        """When DBOS is off, /pipeline/jobs reads from in-memory store."""
        from rule_viewer.api.pipeline import JobInfo, _jobs
        _jobs["mem-1"] = JobInfo(
            job_id="mem-1", kind="extract-prs", status="completed",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        try:
            resp = client.get("/api/pipeline/jobs")
            assert resp.status_code == 200
            data = resp.json()
            assert any(j["job_id"] == "mem-1" for j in data)
        finally:
            _jobs.pop("mem-1", None)
