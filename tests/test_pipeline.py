"""Tests for the pipeline background job runner and LLM obs initialization."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from rule_viewer.api.pipeline import (
    JobInfo,
    _LogCollector,
    _run_in_thread,
    configure_db_path,
    get_all_jobs,
    get_db_path,
    get_job,
    _jobs,
)


@pytest.fixture(autouse=True)
def _clear_jobs():
    """Reset the in-memory job store between tests."""
    _jobs.clear()
    yield
    _jobs.clear()


class TestLogCollector:
    """Tests for _LogCollector stdout capture."""

    def test_captures_full_lines(self):
        job = JobInfo(
            job_id="test", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        collector = _LogCollector(job)
        collector.write("hello world\n")
        assert job.logs == ["hello world"]

    def test_buffers_partial_lines(self):
        job = JobInfo(
            job_id="test", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        collector = _LogCollector(job)
        collector.write("partial")
        assert job.logs == []
        collector.write(" line\n")
        assert job.logs == ["partial line"]

    def test_flush_emits_remaining_buffer(self):
        job = JobInfo(
            job_id="test", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        collector = _LogCollector(job)
        collector.write("no newline")
        assert job.logs == []
        collector.flush()
        assert job.logs == ["no newline"]

    def test_multiple_lines_in_one_write(self):
        job = JobInfo(
            job_id="test", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        collector = _LogCollector(job)
        collector.write("line1\nline2\nline3\n")
        assert job.logs == ["line1", "line2", "line3"]


class TestRunInThread:
    """Tests for _run_in_thread job execution wrapper."""

    def test_successful_job(self):
        job = JobInfo(
            job_id="ok", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )

        def task():
            print("step 1")
            print("step 2")

        _run_in_thread(job, task, ())
        assert job.status == "completed"
        assert job.finished_at is not None
        assert job.error is None
        assert "step 1" in job.logs
        assert "step 2" in job.logs

    def test_failed_job(self):
        job = JobInfo(
            job_id="fail", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )

        def task():
            print("starting")
            raise RuntimeError("boom")

        _run_in_thread(job, task, ())
        assert job.status == "failed"
        assert job.finished_at is not None
        assert job.error == "boom"
        assert any("ERROR" in line for line in job.logs)


class TestJobStore:
    """Tests for in-memory job store operations."""

    def test_get_job_returns_none_for_unknown(self):
        assert get_job("nonexistent") is None

    def test_get_job_returns_stored_job(self):
        job = JobInfo(
            job_id="abc", kind="test", status="running",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        _jobs["abc"] = job
        assert get_job("abc") is job

    def test_get_all_jobs_sorted_by_started_at(self):
        j1 = JobInfo(
            job_id="old", kind="test", status="completed",
            logs=[], started_at="2024-01-01T00:00:00Z",
        )
        j2 = JobInfo(
            job_id="new", kind="test", status="running",
            logs=[], started_at="2024-01-02T00:00:00Z",
        )
        _jobs["old"] = j1
        _jobs["new"] = j2
        result = get_all_jobs()
        assert result[0].job_id == "new"
        assert result[1].job_id == "old"


class TestDbPath:
    """Tests for pipeline db_path configuration."""

    def test_configure_and_get(self):
        configure_db_path("/tmp/test.db")
        assert get_db_path() == "/tmp/test.db"

    def test_get_raises_when_not_configured(self):
        # Reset to None
        import rule_viewer.api.pipeline as mod
        original = mod._db_path
        mod._db_path = None
        try:
            with pytest.raises(RuntimeError, match="not configured"):
                get_db_path()
        finally:
            mod._db_path = original


class TestAppStartupInitLlmObs:
    """Verify that app_cli initialises Datadog LLM Observability at startup."""

    @patch("rule_viewer.main.configure_db")
    def test_app_cli_calls_init_llm_obs_before_uvicorn(self, mock_configure_db):
        """init_llm_obs() must be called in app_cli, before uvicorn.run."""
        from rule_viewer.main import app_cli

        call_order: list[str] = []
        mock_configure_db.side_effect = lambda *a, **kw: call_order.append("configure_db")

        mock_uvicorn = MagicMock()
        mock_uvicorn.run.side_effect = lambda *a, **kw: call_order.append("uvicorn.run")

        mock_init = MagicMock(side_effect=lambda: call_order.append("init_llm_obs"))

        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}), \
             patch("code_ruler.llm.client.init_llm_obs", mock_init):
            app_cli(["--db", ":memory:"])

        mock_init.assert_called_once()
        assert call_order.index("init_llm_obs") < call_order.index("uvicorn.run"), \
            "init_llm_obs must be called before uvicorn.run"

    def test_extract_rules_job_does_not_call_init_llm_obs(self):
        """Background thread must NOT call init_llm_obs (it's the app's job)."""
        import rule_viewer.api.pipeline as pipeline_mod

        pipeline_mod._db_path = "/tmp/fake.db"

        with patch("rule_viewer.api.pipeline.get_db_path", return_value="/tmp/fake.db"), \
             patch("code_ruler.db.base.get_engine"), \
             patch("code_ruler.db.base.get_session_factory"), \
             patch("code_ruler.db.base.init_db"), \
             patch("code_ruler.llm.client.get_client"), \
             patch("code_ruler.pipeline.run_pipeline", return_value=[]), \
             patch("code_ruler.llm.client.init_llm_obs") as mock_init:

            from rule_viewer.api.pipeline import start_extract_rules_job
            job_id = start_extract_rules_job(limit=1, dry_run=True)

            # Wait for background thread to finish
            job = get_job(job_id)
            for _ in range(50):
                if job and job.status != "running":
                    break
                time.sleep(0.1)

            mock_init.assert_not_called()
