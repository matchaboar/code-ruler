"""Event emission and job status helpers for DBOS workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def create_job(
    db_path: str,
    job_id: str,
    job_type: str,
    repo_url: str | None,
    params: dict[str, Any] | None = None,
    workflow_id: str | None = None,
) -> None:
    """Create a PipelineJob row at the start of a workflow."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.db.models import PipelineJob

    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)

    now = datetime.now(timezone.utc)
    with factory() as session:
        existing = session.get(PipelineJob, job_id)
        if existing:
            return
        job = PipelineJob(
            id=job_id,
            workflow_id=workflow_id,
            job_type=job_type,
            status="running",
            repo_url=repo_url,
            params_json=params,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()


def update_job_status(
    db_path: str,
    job_id: str,
    status: str,
    error: str | None = None,
) -> None:
    """Update the status of a PipelineJob row."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.db.models import PipelineJob

    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)

    now = datetime.now(timezone.utc)
    with factory() as session:
        job = session.get(PipelineJob, job_id)
        if not job:
            return
        job.status = status
        job.updated_at = now
        if error:
            job.error_message = error
        if status in ("completed", "failed"):
            job.finished_at = now
        session.commit()


def emit_event(
    db_path: str,
    job_id: str,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Write a single event row for a pipeline job."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.db.models import PipelineEvent

    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)

    now = datetime.now(timezone.utc)
    with factory() as session:
        event = PipelineEvent(
            job_id=job_id,
            event_type=event_type,
            event_data_json=data,
            created_at=now,
        )
        session.add(event)
        session.commit()
