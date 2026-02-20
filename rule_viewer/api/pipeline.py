"""Background job runner for pipeline extraction steps."""

from __future__ import annotations

import io
import threading
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class JobEvent(BaseModel):
    type: str  # "pr_extracted" | "pr_skipped" | "review_start" | "review_done" | "review_error" | "rule_candidate"
    data: dict[str, Any] = {}


class JobInfo(BaseModel):
    job_id: str
    kind: str  # "extract-prs" | "extract-rules" | "quick-run"
    status: str  # "running" | "completed" | "failed"
    logs: list[str]
    events: list[JobEvent] = []
    repo_url: str | None = None
    started_at: str
    finished_at: str | None = None
    error: str | None = None


_jobs: dict[str, JobInfo] = {}
_db_path: str | None = None


def configure_db_path(db_path: str) -> None:
    """Store the database path for use by background threads."""
    global _db_path
    _db_path = db_path


def get_db_path() -> str:
    if _db_path is None:
        raise RuntimeError("Pipeline db_path not configured")
    return _db_path


def get_job(job_id: str) -> JobInfo | None:
    return _jobs.get(job_id)


def get_all_jobs() -> list[JobInfo]:
    return sorted(_jobs.values(), key=lambda j: j.started_at, reverse=True)


class _LogCollector(io.TextIOBase):
    """Captures print output line-by-line into a job's log list."""

    def __init__(self, job: JobInfo) -> None:
        self._job = job
        self._buffer = ""

    def write(self, s: str) -> int:
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self._job.logs.append(line)
        return len(s)

    def flush(self) -> None:
        if self._buffer:
            self._job.logs.append(self._buffer)
            self._buffer = ""


def _run_in_thread(job: JobInfo, target: callable, args: tuple) -> None:
    """Execute target in a thread, capturing stdout into job logs."""
    collector = _LogCollector(job)
    try:
        with redirect_stdout(collector):
            target(*args)
        collector.flush()
        job.status = "completed"
    except Exception as e:
        collector.flush()
        job.error = str(e)
        job.status = "failed"
        job.logs.append(f"ERROR: {e}")
    finally:
        job.finished_at = datetime.now(timezone.utc).isoformat()


def start_extract_prs_job(repo_url: str, limit: int | None = None) -> str:
    """Start a background job to extract PRs from a GitHub repo."""
    from github_extractor.client import create_github_client
    from github_extractor.database import get_engine, get_session_factory, init_db
    from github_extractor.extractor import extract_repo

    job_id = uuid.uuid4().hex[:12]
    job = JobInfo(
        job_id=job_id,
        kind="extract-prs",
        status="running",
        logs=[],
        events=[],
        repo_url=repo_url,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _jobs[job_id] = job

    db_path = get_db_path()

    def _on_pr(pr_number: int, pr_title: str, author: str, status: str) -> None:
        job.events.append(JobEvent(
            type=f"pr_{status}",
            data={"pr_number": pr_number, "pr_title": pr_title, "author": author},
        ))

    def _do_extract() -> None:
        engine = get_engine(db_path)
        init_db(engine)
        factory = get_session_factory(engine)
        client = create_github_client()
        print(f"Extracting PRs from {repo_url}...")
        with factory() as session:
            extract_repo(client, repo_url, session, limit=limit, on_pr=_on_pr)
        print("PR extraction complete.")

    t = threading.Thread(target=_run_in_thread, args=(job, _do_extract, ()), daemon=True)
    t.start()
    return job_id


def start_extract_rules_job(
    limit: int | None = None,
    dry_run: bool = False,
    repo_url: str | None = None,
    repo_full_name: str | None = None,
) -> str:
    """Start a background job to extract rules from PR data."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.llm.client import DEFAULT_MODEL, get_client
    from code_ruler.pipeline import run_pipeline

    job_id = uuid.uuid4().hex[:12]
    job = JobInfo(
        job_id=job_id,
        kind="extract-rules",
        status="running",
        logs=[],
        events=[],
        repo_url=repo_url or (f"https://github.com/{repo_full_name}" if repo_full_name else None),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _jobs[job_id] = job

    db_path = get_db_path()

    def _on_review(event_type: str, **data: Any) -> None:
        job.events.append(JobEvent(type=event_type, data=data))

    def _do_extract() -> None:
        engine = get_engine(db_path)
        init_db(engine)
        factory = get_session_factory(engine)
        client = get_client()
        scope = f" for {repo_full_name}" if repo_full_name else ""
        print(f"Starting rule extraction{scope} (limit={limit}, dry_run={dry_run})...")
        with factory() as session:
            candidates = run_pipeline(
                client, session, DEFAULT_MODEL,
                limit=limit, dry_run=dry_run, on_review=_on_review,
                repo_full_name=repo_full_name,
            )
        if dry_run:
            print(f"Dry run complete. {len(candidates)} candidate rules found.")
            for c in candidates:
                print(f"  [{c.severity}] {c.slug}: {c.title}")
        else:
            print(f"Done. {len(candidates)} rules processed.")

    t = threading.Thread(target=_run_in_thread, args=(job, _do_extract, ()), daemon=True)
    t.start()
    return job_id


def start_quick_run_job(repo_url: str, pr_limit: int = 10) -> str:
    """Start a quick run: extract PRs then extract rules in one go."""
    from github_extractor.client import create_github_client
    from github_extractor.database import get_engine as gh_get_engine
    from github_extractor.database import get_session_factory as gh_get_session_factory
    from github_extractor.database import init_db as gh_init_db
    from github_extractor.extractor import extract_repo

    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.llm.client import DEFAULT_MODEL, get_client
    from code_ruler.pipeline import run_pipeline

    job_id = uuid.uuid4().hex[:12]
    job = JobInfo(
        job_id=job_id,
        kind="quick-run",
        status="running",
        logs=[],
        events=[],
        repo_url=repo_url,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _jobs[job_id] = job

    db_path = get_db_path()

    def _on_pr(pr_number: int, pr_title: str, author: str, status: str) -> None:
        job.events.append(JobEvent(
            type=f"pr_{status}",
            data={"pr_number": pr_number, "pr_title": pr_title, "author": author},
        ))

    def _on_review(event_type: str, **data: Any) -> None:
        job.events.append(JobEvent(type=event_type, data=data))

    def _do_quick_run() -> None:
        # Step 1: Extract PRs
        print(f"[Quick Run] Step 1: Extracting up to {pr_limit} PRs from {repo_url}...")
        engine = get_engine(db_path)
        init_db(engine)

        gh_engine = gh_get_engine(db_path)
        gh_init_db(gh_engine)
        gh_factory = gh_get_session_factory(gh_engine)

        client = create_github_client()
        with gh_factory() as session:
            extract_repo(client, repo_url, session, limit=pr_limit, on_pr=_on_pr)
        print("[Quick Run] PR extraction complete.")

        # Step 2: Extract rules from those PRs
        print("[Quick Run] Step 2: Extracting rules...")
        factory = get_session_factory(engine)
        llm_client = get_client()
        with factory() as session:
            candidates = run_pipeline(
                llm_client, session, DEFAULT_MODEL,
                limit=None, dry_run=False, on_review=_on_review,
            )
        print(f"[Quick Run] Done. {len(candidates)} rules processed.")

    t = threading.Thread(target=_run_in_thread, args=(job, _do_quick_run, ()), daemon=True)
    t.start()
    return job_id
