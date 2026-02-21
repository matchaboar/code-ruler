"""API endpoints for rules, provenance, and PR data."""

from __future__ import annotations

import json
import os
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from code_ruler.db.models import EnforcerScript, FunctionTypeRule, Rule, RuleProvenance, TestSpriteResult
from github_extractor.models import PullRequest, Repository, ReviewComment
from rule_viewer.api.pipeline import (
    get_all_jobs,
    get_job,
    start_extract_prs_job,
    start_extract_rules_job,
    start_generate_enforcer_job,
    start_generate_testsprite_job,
    start_quick_extract_rules_job,
    start_quick_fetch_prs_job,
    start_quick_run_job,
)
from rule_viewer.api.schemas import (
    CredentialsStatusResponse,
    EnforcerDetail,
    EnforcerListItem,
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
    RepoItem,
    RepoStatsResponse,
    RuleDetail,
    RuleListItem,
    ServiceStatus,
    StatsResponse,
    TestSpriteDetail,
    TestSpriteListItem,
    VideoResponse,
)

router = APIRouter(prefix="/api")


def get_db() -> Session:
    """Dependency that provides a database session.

    This is overridden at app startup with the actual session factory.
    """
    raise NotImplementedError("Database session not configured")


@router.get("/repos", response_model=list[RepoItem])
def list_repos(db: Session = Depends(get_db)) -> list[RepoItem]:
    """List all repositories with rule counts."""
    repos = db.query(Repository).order_by(Repository.full_name).all()
    items = []
    for repo in repos:
        total_rules = db.query(Rule).filter(Rule.repo_id == repo.id).count()
        items.append(
            RepoItem(
                id=repo.id,
                full_name=repo.full_name,
                url=f"https://github.com/{repo.full_name}",
                total_rules=total_rules,
            )
        )
    return items


@router.get("/rules", response_model=list[RuleListItem])
def list_rules(
    repo_id: int = Query(..., description="Filter rules by repository ID"),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[RuleListItem]:
    """List rules with optional filters, scoped to a repository."""
    query = db.query(Rule).filter(Rule.repo_id == repo_id)

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
        has_enforcer = (
            db.query(EnforcerScript).filter_by(rule_id=rule.id).first() is not None
        )
        has_tests = (
            db.query(TestSpriteResult).filter_by(rule_id=rule.id).first() is not None
        )
        items.append(
            RuleListItem(
                slug=rule.slug,
                repo_id=rule.repo_id,
                category=rule.category,
                severity=rule.severity,
                title=rule.title,
                is_active=rule.is_active,
                has_decorator=has_decorator,
                has_enforcer=has_enforcer,
                has_tests=has_tests,
                provenance_count=provenance_count,
            )
        )

    return items


@router.get("/rules/{slug}", response_model=RuleDetail)
def get_rule(
    slug: str,
    repo_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> RuleDetail:
    """Get a single rule with full detail."""
    query = db.query(Rule).filter_by(slug=slug)
    if repo_id is not None:
        query = query.filter(Rule.repo_id == repo_id)
    rule = query.first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    ftr = db.query(FunctionTypeRule).filter_by(rule_id=rule.id).first()

    return RuleDetail(
        slug=rule.slug,
        repo_id=rule.repo_id,
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


@router.post("/rules/{slug}/generate-enforcer", response_model=JobStartResponse)
def generate_enforcer(slug: str, db: Session = Depends(get_db)) -> JobStartResponse:
    """Trigger enforcer generation for a rule."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if not rule.negative_example:
        raise HTTPException(status_code=400, detail="Rule has no negative_example; cannot generate enforcer")

    # Check for in-progress generation
    from rule_viewer.api.pipeline import get_all_jobs as _get_all_jobs
    for job in _get_all_jobs():
        if job.kind == "generate-enforcer" and job.status == "running":
            for ev in job.events:
                if ev.data.get("rule_slug") == slug:
                    raise HTTPException(status_code=409, detail="Enforcer generation already in progress")

    job_id = start_generate_enforcer_job(slug)
    return JobStartResponse(job_id=job_id)


@router.get("/enforcers", response_model=list[EnforcerListItem])
def list_enforcers(
    repo_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> list[EnforcerListItem]:
    """List all rules with enforcer scripts, optionally scoped to a repo."""
    query = db.query(EnforcerScript)
    if repo_id is not None:
        query = query.join(Rule, EnforcerScript.rule_id == Rule.id).filter(Rule.repo_id == repo_id)
    enforcers = query.all()
    items = []
    for es in enforcers:
        rule = db.get(Rule, es.rule_id)
        if not rule:
            continue
        items.append(
            EnforcerListItem(
                rule_slug=rule.slug,
                rule_title=rule.title,
                category=rule.category,
                severity=rule.severity,
                status=es.status,
                check_type=es.check_type,
                has_decorator=es.decorator_source is not None,
                attempt_count=es.attempt_count,
                created_at=es.created_at.isoformat(),
            )
        )
    return items


def _generate_diff(enforcer_source: str, rule_slug: str) -> str:
    """Generate a unified diff showing the enforcer script as a new file."""
    lines = enforcer_source.splitlines()
    diff_lines = [
        f"--- /dev/null",
        f"+++ b/enforcers/{rule_slug}_check.py",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    for line in lines:
        diff_lines.append(f"+{line}")
    return "\n".join(diff_lines)


@router.get("/rules/{slug}/enforcer", response_model=EnforcerDetail)
def get_enforcer(slug: str, db: Session = Depends(get_db)) -> EnforcerDetail:
    """Get enforcer detail for a rule."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    es = db.query(EnforcerScript).filter_by(rule_id=rule.id).first()
    if not es:
        raise HTTPException(status_code=404, detail="No enforcer script for this rule")
    return EnforcerDetail(
        rule_slug=rule.slug,
        rule_title=rule.title,
        category=rule.category,
        severity=rule.severity,
        status=es.status,
        check_type=es.check_type,
        has_decorator=es.decorator_source is not None,
        attempt_count=es.attempt_count,
        enforcer_source=es.enforcer_source,
        decorator_source=es.decorator_source,
        test_code=es.test_code,
        test_result=es.test_result,
        test_output=es.test_output,
        diff=_generate_diff(es.enforcer_source, rule.slug) if es.enforcer_source else None,
        dd_traces=es.dd_traces if isinstance(es.dd_traces, list) else None,
        created_at=es.created_at.isoformat(),
        updated_at=es.updated_at.isoformat(),
    )


@router.post("/rules/{slug}/generate-testsprite", response_model=JobStartResponse)
def generate_testsprite(slug: str, db: Session = Depends(get_db)) -> JobStartResponse:
    """Trigger TestSprite test generation for a rule."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Check for in-progress generation
    from rule_viewer.api.pipeline import get_all_jobs as _get_all_jobs
    for job in _get_all_jobs():
        if job.kind == "generate-testsprite" and job.status == "running":
            for ev in job.events:
                if ev.data.get("rule_slug") == slug:
                    raise HTTPException(status_code=409, detail="TestSprite generation already in progress")

    # Resolve repo_url from provenance if not directly available
    repo = db.get(Repository, rule.repo_id)
    if not repo:
        raise HTTPException(status_code=400, detail="Rule has no associated repository")
    repo_url = f"https://github.com/{repo.full_name}"

    job_id = start_generate_testsprite_job(slug, repo_url)
    return JobStartResponse(job_id=job_id)


@router.get("/testsprite", response_model=list[TestSpriteListItem])
def list_testsprite_results(
    repo_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> list[TestSpriteListItem]:
    """List all TestSprite results, optionally scoped to a repo."""
    query = db.query(TestSpriteResult)
    if repo_id is not None:
        query = query.join(Rule, TestSpriteResult.rule_id == Rule.id).filter(Rule.repo_id == repo_id)
    results = query.order_by(TestSpriteResult.created_at.desc()).all()
    items = []
    for r in results:
        rule = db.get(Rule, r.rule_id)
        if not rule:
            continue
        items.append(
            TestSpriteListItem(
                id=r.id,
                rule_slug=rule.slug,
                rule_title=rule.title,
                repo_url=r.repo_url,
                status=r.status,
                created_at=r.created_at.isoformat(),
            )
        )
    return items


@router.get("/rules/{slug}/testsprite", response_model=list[TestSpriteListItem])
def list_rule_testsprite_results(slug: str, db: Session = Depends(get_db)) -> list[TestSpriteListItem]:
    """List TestSprite results for a specific rule."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    results = db.query(TestSpriteResult).filter_by(rule_id=rule.id).order_by(TestSpriteResult.created_at.desc()).all()
    return [
        TestSpriteListItem(
            id=r.id,
            rule_slug=rule.slug,
            rule_title=rule.title,
            repo_url=r.repo_url,
            status=r.status,
            created_at=r.created_at.isoformat(),
        )
        for r in results
    ]


@router.get("/testsprite/{result_id}", response_model=TestSpriteDetail)
def get_testsprite_detail(result_id: int, db: Session = Depends(get_db)) -> TestSpriteDetail:
    """Get detailed TestSprite result including diff and test output."""
    r = db.get(TestSpriteResult, result_id)
    if not r:
        raise HTTPException(status_code=404, detail="TestSprite result not found")
    rule = db.get(Rule, r.rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Associated rule not found")
    return TestSpriteDetail(
        id=r.id,
        rule_slug=rule.slug,
        rule_title=rule.title,
        repo_url=r.repo_url,
        status=r.status,
        test_plan=r.test_plan_json,
        generated_tests=r.generated_tests,
        test_results=r.test_results_json,
        diff=r.diff,
        error_message=r.error_message,
        created_at=r.created_at.isoformat(),
        updated_at=r.updated_at.isoformat(),
    )


@router.post("/rules/{slug}/generate-video", response_model=VideoResponse)
def generate_video(
    slug: str,
    req: GenerateVideoRequest,
    db: Session = Depends(get_db),
) -> VideoResponse:
    """Submit a video generation task for a rule. Returns immediately with a task_id."""
    rule = db.query(Rule).filter_by(slug=slug).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from code_ruler.llm.schemas import CandidateRule
    from code_ruler.video.generator import _DEFAULT_PROMPT
    from code_ruler.video.image_renderer import render_rule_image
    from code_ruler.video.minimax_client import submit_image_to_video

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

    image_bytes = render_rule_image(candidate)
    task_id = submit_image_to_video(image_bytes, req.prompt or _DEFAULT_PROMPT)

    return VideoResponse(task_id=task_id, status="Processing")


@router.get("/video/{task_id}", response_model=VideoResponse)
def get_video_status(task_id: str) -> VideoResponse:
    """Poll Minimax for the status of a video generation task."""
    from code_ruler.video.minimax_client import get_api_key, get_video_download_url

    import httpx

    api_key = get_api_key()
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://api.minimax.io/v1/query/video_generation",
            params={"task_id": task_id},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    status = data.get("status", "")
    if status == "Success":
        file_id = data.get("file_id", "")
        download_url = get_video_download_url(file_id) if file_id else None
        return VideoResponse(
            task_id=task_id, status="Success", file_id=file_id, download_url=download_url
        )
    elif status == "Fail":
        return VideoResponse(
            task_id=task_id, status="Fail", error=data.get("error", "Unknown error")
        )

    return VideoResponse(task_id=task_id, status="Processing")


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    repo_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> StatsResponse:
    """Get summary statistics, optionally scoped to a repo."""
    rule_query = db.query(Rule)
    if repo_id is not None:
        rule_query = rule_query.filter(Rule.repo_id == repo_id)

    total_rules = rule_query.count()

    category_counts = dict(
        rule_query.with_entities(Rule.category, func.count()).group_by(Rule.category).all()
    )
    severity_counts = dict(
        rule_query.with_entities(Rule.severity, func.count()).group_by(Rule.severity).all()
    )

    pr_query = db.query(PullRequest)
    if repo_id is not None:
        pr_query = pr_query.filter(PullRequest.repo_id == repo_id)
    total_prs = pr_query.count()

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

    # Check TestSprite
    ts_key = os.environ.get("TESTSPRITE_API_KEY", "")
    if not ts_key:
        services.append(ServiceStatus(name="TestSprite", ok=False, detail="TESTSPRITE_API_KEY not set"))
    else:
        services.append(ServiceStatus(name="TestSprite", ok=True, detail="API key configured"))

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
