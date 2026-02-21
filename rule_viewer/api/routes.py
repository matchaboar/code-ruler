"""API endpoints for rules, provenance, and PR data."""

from __future__ import annotations

import json
import os
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from code_ruler.db.models import EnforcerScript, FunctionTypeRule, Rule, RuleProvenance
from github_extractor.models import PullRequest, Repository, ReviewComment
from rule_viewer.api.pipeline import (
    get_all_jobs,
    get_job,
    start_extract_prs_job,
    start_extract_rules_job,
    start_generate_enforcer_job,
    start_quick_extract_rules_job,
    start_quick_fetch_prs_job,
    start_quick_run_job,
)
from rule_viewer.api.schemas import (
    CredentialsStatusResponse,
    ExtractPRsRequest,
    ExtractRulesRequest,
    GenerateVideoRequest,
    JobEventResponse,
    JobStartResponse,
    JobStatusResponse,
    ProvenanceItem,
    QuickExtractRequest,
    QuickFetchRequest,
    QuickRunRequest,
    RepoStatsResponse,
    RuleDetail,
    RuleListItem,
    ServiceStatus,
    StatsResponse,
    VideoResponse,
)

router = APIRouter(prefix="/api")


def get_db() -> Session:
    """Dependency that provides a database session.

    This is overridden at app startup with the actual session factory.
    """
    raise NotImplementedError("Database session not configured")


@router.get("/rules", response_model=list[RuleListItem])
def list_rules(
    category: str | None = Query(None),
    severity: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[RuleListItem]:
    """List rules with optional filters."""
    query = db.query(Rule)

    if category:
        query = query.filter(Rule.category == category)
    if severity:
        query = query.filter(Rule.severity == severity)
    if is_active is not None:
        query = query.filter(Rule.is_active.is_(is_active))
    if search:
        query = query.filter(
            Rule.title.ilike(f"%{search}%") | Rule.slug.ilike(f"%{search}%")
        )

    rules = query.order_by(Rule.slug).all()

    items = []
    for rule in rules:
        provenance_count = db.query(RuleProvenance).filter_by(rule_id=rule.id).count()
        has_decorator = (
            db.query(FunctionTypeRule).filter_by(rule_id=rule.id).first() is not None
        )
        items.append(
            RuleListItem(
                slug=rule.slug,
                category=rule.category,
                severity=rule.severity,
                title=rule.title,
                is_active=rule.is_active,
                has_decorator=has_decorator,
                provenance_count=provenance_count,
            )
        )

    return items


@router.get("/rules/{slug}", response_model=RuleDetail)
def get_rule(slug: str, db: Session = Depends(get_db)) -> RuleDetail:
    """Get a single rule with full detail."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    ftr = db.query(FunctionTypeRule).filter_by(rule_id=rule.id).first()

    return RuleDetail(
        slug=rule.slug,
        category=rule.category,
        severity=rule.severity,
        title=rule.title,
        description=rule.description,
        positive_example=rule.positive_example,
        negative_example=rule.negative_example,
        rationale=rule.rationale,
        is_active=rule.is_active,
        version=rule.version,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
        decorator_name=ftr.decorator_name if ftr else None,
        decorator_source=ftr.decorator_source if ftr else None,
        linter_source=ftr.linter_source if ftr else None,
        constraints=ftr.constraints_json if ftr else None,
    )


@router.get("/rules/{slug}/provenance", response_model=list[ProvenanceItem])
def get_provenance(slug: str, db: Session = Depends(get_db)) -> list[ProvenanceItem]:
    """Get provenance for a rule — PR references that generated it."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    provenance_records = db.query(RuleProvenance).filter_by(rule_id=rule.id).all()

    items = []
    for prov in provenance_records:
        pr = db.get(PullRequest, prov.pull_request_id)
        if not pr:
            continue

        repo = db.get(Repository, pr.repo_id)
        comment = (
            db.get(ReviewComment, prov.review_comment_id)
            if prov.review_comment_id
            else None
        )

        items.append(
            ProvenanceItem(
                pr_number=pr.number,
                pr_title=pr.title,
                pr_url=f"https://github.com/{repo.full_name}/pull/{pr.number}" if repo else "",
                repo_full_name=repo.full_name if repo else "",
                comment_author=comment.author if comment else "",
                comment_body=comment.body if comment else "",
                diff_hunk=comment.diff_hunk if comment else "",
                file_path=comment.path if comment else "",
                original_commit_sha=comment.original_commit_id if comment else None,
                fix_commit_sha=comment.fix_commit_sha if comment else None,
                extraction_notes=prov.extraction_notes,
            )
        )

    return items


@router.post("/rules/{slug}/generate-video", response_model=VideoResponse)
def generate_video(
    slug: str,
    req: GenerateVideoRequest,
    db: Session = Depends(get_db),
) -> VideoResponse:
    """Generate an animated video from a rule's code examples via Minimax I2V."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from code_ruler.llm.schemas import CandidateRule
    from code_ruler.video.generator import generate_rule_video

    candidate = CandidateRule(
        slug=rule.slug,
        category=rule.category,
        severity=rule.severity,
        title=rule.title,
        description=rule.description,
        positive_example=rule.positive_example,
        negative_example=rule.negative_example,
        rationale=rule.rationale,
    )

    result = generate_rule_video(candidate, prompt=req.prompt)

    return VideoResponse(
        task_id=result.task_id,
        status=result.status,
        file_id=result.file_id,
        download_url=result.download_url,
        error=result.error,
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    """Get summary statistics."""
    total_rules = db.query(Rule).count()

    category_counts = dict(
        db.query(Rule.category, func.count()).group_by(Rule.category).all()
    )
    severity_counts = dict(
        db.query(Rule.severity, func.count()).group_by(Rule.severity).all()
    )
    total_prs = db.query(PullRequest).count()

    return StatsResponse(
        total_rules=total_rules,
        rules_by_category=category_counts,
        rules_by_severity=severity_counts,
        total_prs_processed=total_prs,
    )


@router.get("/credentials/status", response_model=CredentialsStatusResponse)
def check_credentials() -> CredentialsStatusResponse:
    """Check connectivity to external services (Bedrock, Datadog, GitHub)."""
    services: list[ServiceStatus] = []

    # Check AWS Bedrock — verify credentials via STS to avoid noisy LLMObs traces
    try:
        import boto3

        from code_ruler.llm.client import DEFAULT_MODEL

        sts = boto3.client("sts", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))
        identity = sts.get_caller_identity()
        services.append(ServiceStatus(
            name="AWS Bedrock",
            ok=True,
            detail=f"Model: {DEFAULT_MODEL} | Account: {identity['Account']}",
        ))
    except Exception as e:
        services.append(ServiceStatus(name="AWS Bedrock", ok=False, detail=str(e)[:200]))

    # Check Datadog
    dd_key = os.environ.get("DD_API_KEY", "")
    if not dd_key:
        services.append(ServiceStatus(name="Datadog", ok=False, detail="DD_API_KEY not set"))
    else:
        try:
            dd_site = os.environ.get("DD_SITE", "datadoghq.com")
            req = urllib.request.Request(
                f"https://api.{dd_site}/api/v1/validate",
                headers={"DD-API-KEY": dd_key},
            )
            resp_dd = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp_dd.read())
            if data.get("valid"):
                services.append(ServiceStatus(name="Datadog", ok=True, detail=f"Site: {dd_site}"))
            else:
                services.append(ServiceStatus(name="Datadog", ok=False, detail="API key invalid"))
        except Exception as e:
            services.append(ServiceStatus(name="Datadog", ok=False, detail=str(e)[:200]))

    # Check GitHub
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if not gh_token:
        services.append(ServiceStatus(name="GitHub", ok=False, detail="GITHUB_TOKEN not set"))
    else:
        try:
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github+json"},
            )
            resp_gh = urllib.request.urlopen(req, timeout=10)
            user_data = json.loads(resp_gh.read())
            services.append(
                ServiceStatus(name="GitHub", ok=True, detail=f"User: {user_data.get('login', '?')}")
            )
        except Exception as e:
            services.append(ServiceStatus(name="GitHub", ok=False, detail=str(e)[:200]))

    return CredentialsStatusResponse(services=services)


@router.post("/pipeline/extract-prs", response_model=JobStartResponse)
def start_extract_prs(req: ExtractPRsRequest) -> JobStartResponse:
    """Start a background job to extract PRs from a GitHub repo."""
    job_id = start_extract_prs_job(req.repo_url, limit=req.limit)
    return JobStartResponse(job_id=job_id)


@router.post("/pipeline/extract-rules", response_model=JobStartResponse)
def start_extract_rules(req: ExtractRulesRequest) -> JobStartResponse:
    """Start a background job to extract rules from PR data."""
    job_id = start_extract_rules_job(limit=req.limit, dry_run=req.dry_run, repo_full_name=req.repo_full_name)
    return JobStartResponse(job_id=job_id)


@router.get("/pipeline/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    """Get the status and logs of a pipeline job."""
    from rule_viewer.api.pipeline import _dbos_enabled

    if _dbos_enabled():
        from code_ruler.db.models import PipelineEvent, PipelineJob

        pj = db.get(PipelineJob, job_id)
        if not pj:
            raise HTTPException(status_code=404, detail="Job not found")
        events = db.query(PipelineEvent).filter_by(job_id=job_id).order_by(PipelineEvent.created_at).all()
        return JobStatusResponse(
            job_id=pj.id,
            kind=pj.job_type,
            status=pj.status,
            logs=[],
            events=[
                JobEventResponse(type=e.event_type, data=e.event_data_json or {})
                for e in events
            ],
            repo_url=pj.repo_url,
            started_at=pj.created_at.isoformat(),
            finished_at=pj.finished_at.isoformat() if pj.finished_at else None,
            error=pj.error_message,
            workflow_id=pj.workflow_id,
        )

    # Legacy in-memory path
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job.model_dump())


@router.get("/pipeline/jobs", response_model=list[JobStatusResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[JobStatusResponse]:
    """List all pipeline jobs."""
    from rule_viewer.api.pipeline import _dbos_enabled

    if _dbos_enabled():
        from code_ruler.db.models import PipelineJob

        jobs = db.query(PipelineJob).order_by(PipelineJob.created_at.desc()).all()
        return [
            JobStatusResponse(
                job_id=pj.id,
                kind=pj.job_type,
                status=pj.status,
                logs=[],
                events=[],
                repo_url=pj.repo_url,
                started_at=pj.created_at.isoformat(),
                finished_at=pj.finished_at.isoformat() if pj.finished_at else None,
                error=pj.error_message,
                workflow_id=pj.workflow_id,
            )
            for pj in jobs
        ]

    return [JobStatusResponse(**j.model_dump()) for j in get_all_jobs()]


@router.post("/pipeline/quick-fetch-prs", response_model=JobStartResponse)
def start_quick_fetch_prs(req: QuickFetchRequest) -> JobStartResponse:
    """Start a quick-fetch job: extract a small batch of PRs."""
    job_id = start_quick_fetch_prs_job(req.repo_url, limit=req.limit)
    return JobStartResponse(job_id=job_id)


@router.post("/pipeline/quick-extract-rules", response_model=JobStartResponse)
def start_quick_extract_rules(req: QuickExtractRequest) -> JobStartResponse:
    """Start a quick-extract job: extract rules from a small batch of comments."""
    job_id = start_quick_extract_rules_job(limit=req.limit, repo_filter=req.repo_filter)
    return JobStartResponse(job_id=job_id)


@router.post("/pipeline/quick-run", response_model=JobStartResponse)
def start_quick_run(req: QuickRunRequest) -> JobStartResponse:
    """Start a quick run: extract PRs then extract rules in one go."""
    job_id = start_quick_run_job(req.repo_url, pr_limit=req.pr_limit)
    return JobStartResponse(job_id=job_id)


@router.post("/pipeline/jobs/{job_id}/resume", response_model=JobStartResponse)
def resume_job(job_id: str, db: Session = Depends(get_db)) -> JobStartResponse:
    """Resume a failed or interrupted DBOS workflow."""
    from rule_viewer.api.pipeline import _dbos_enabled

    if not _dbos_enabled():
        raise HTTPException(status_code=400, detail="DBOS not enabled; cannot resume jobs")

    from dbos import DBOS

    from code_ruler.db.models import PipelineJob

    pj = db.get(PipelineJob, job_id)
    if not pj:
        raise HTTPException(status_code=404, detail="Job not found")
    if not pj.workflow_id:
        raise HTTPException(status_code=400, detail="Job has no associated workflow")

    handle = DBOS.retrieve_workflow(pj.workflow_id)
    handle.get_result()
    return JobStartResponse(job_id=job_id)


@router.post("/pipeline/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    """Cancel a running DBOS workflow.

    Sets the workflow status to CANCELLED in DBOS, which preempts execution
    at the beginning of the next step. Also updates the PipelineJob row.
    """
    from rule_viewer.api.pipeline import _dbos_enabled

    from code_ruler.db.models import PipelineJob

    pj = db.get(PipelineJob, job_id)
    if not pj:
        raise HTTPException(status_code=404, detail="Job not found")

    if _dbos_enabled() and pj.workflow_id:
        from dbos import DBOS
        DBOS.cancel_workflow(pj.workflow_id)

    from datetime import datetime, timezone
    pj.status = "cancelled"
    pj.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "cancelled", "job_id": job_id}


@router.get("/pipeline/jobs/{job_id}/steps")
def get_job_steps(job_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """Get step-level progress for a pipeline job."""
    from code_ruler.db.models import PipelineEvent

    events = (
        db.query(PipelineEvent)
        .filter_by(job_id=job_id)
        .order_by(PipelineEvent.created_at)
        .all()
    )
    if not events:
        raise HTTPException(status_code=404, detail="No steps found for this job")
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "data": e.event_data_json or {},
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/pipeline/repo-stats", response_model=list[RepoStatsResponse])
def get_repo_stats(db: Session = Depends(get_db)) -> list[RepoStatsResponse]:
    """Get processed/unprocessed comment counts per repo."""
    repos = db.query(Repository).all()
    results = []
    for repo in repos:
        total_prs = db.query(PullRequest).filter_by(repo_id=repo.id).count()

        # Top-level review comments for this repo
        top_comments = (
            db.query(ReviewComment.id)
            .join(PullRequest, ReviewComment.pr_id == PullRequest.id)
            .filter(PullRequest.repo_id == repo.id)
            .filter(ReviewComment.in_reply_to_id.is_(None))
            .subquery()
        )
        total_comments = db.query(func.count()).select_from(top_comments).scalar() or 0

        processed = (
            db.query(func.count(func.distinct(RuleProvenance.review_comment_id)))
            .join(PullRequest, RuleProvenance.pull_request_id == PullRequest.id)
            .filter(PullRequest.repo_id == repo.id)
            .filter(RuleProvenance.review_comment_id.isnot(None))
            .scalar() or 0
        )

        results.append(RepoStatsResponse(
            full_name=repo.full_name,
            total_prs=total_prs,
            processed_comments=processed,
            unprocessed_comments=total_comments - processed,
        ))
    return results
