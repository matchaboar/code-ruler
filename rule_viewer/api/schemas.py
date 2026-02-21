"""Pydantic response models for the rule viewer API."""

from __future__ import annotations

from pydantic import BaseModel


class RepoItem(BaseModel):
    id: int
    full_name: str
    url: str
    total_rules: int


class RuleListItem(BaseModel):
    slug: str
    repo_id: int
    category: str
    severity: str
    title: str
    is_active: bool
    has_decorator: bool
    has_enforcer: bool
    has_tests: bool
    provenance_count: int


class RuleDetail(BaseModel):
    slug: str
    repo_id: int
    category: str
    severity: str
    title: str
    description: str
    positive_example: str | None
    negative_example: str | None
    rationale: str
    is_active: bool
    version: int
    created_at: str
    updated_at: str
    decorator_name: str | None = None
    decorator_source: str | None = None
    linter_source: str | None = None
    constraints: list[str] | None = None


class ProvenanceItem(BaseModel):
    pr_number: int
    pr_title: str
    pr_url: str
    repo_full_name: str
    comment_author: str
    comment_body: str
    diff_hunk: str
    file_path: str
    original_commit_sha: str | None
    fix_commit_sha: str | None
    extraction_notes: str | None


class StatsResponse(BaseModel):
    total_rules: int
    rules_by_category: dict[str, int]
    rules_by_severity: dict[str, int]
    total_prs_processed: int


class ServiceStatus(BaseModel):
    name: str
    ok: bool
    detail: str


class CredentialsStatusResponse(BaseModel):
    services: list[ServiceStatus]


class ExtractPRsRequest(BaseModel):
    repo_url: str
    limit: int | None = None


class ExtractRulesRequest(BaseModel):
    limit: int | None = None
    dry_run: bool = False
    repo_full_name: str | None = None


class QuickRunRequest(BaseModel):
    repo_url: str
    pr_limit: int = 10


class QuickFetchRequest(BaseModel):
    repo_url: str
    limit: int = 10


class QuickExtractRequest(BaseModel):
    limit: int = 10
    repo_filter: str | None = None


class JobStartResponse(BaseModel):
    job_id: str


class JobEventResponse(BaseModel):
    type: str
    data: dict = {}


class JobStatusResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    logs: list[str]
    events: list[JobEventResponse] = []
    repo_url: str | None = None
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    workflow_id: str | None = None


class GenerateVideoRequest(BaseModel):
    prompt: str | None = None


class VideoResponse(BaseModel):
    task_id: str
    status: str
    slug: str | None = None
    file_id: str | None = None
    download_url: str | None = None
    error: str | None = None


class VideoListItem(BaseModel):
    id: int
    rule_slug: str
    rule_title: str
    task_id: str
    status: str
    download_url: str | None = None
    error: str | None = None
    created_at: str


class EnforcerListItem(BaseModel):
    rule_slug: str
    rule_title: str
    category: str
    severity: str
    status: str
    check_type: str
    has_decorator: bool
    attempt_count: int
    created_at: str


class EnforcerDetail(BaseModel):
    rule_slug: str
    rule_title: str
    category: str
    severity: str
    status: str
    check_type: str
    has_decorator: bool
    attempt_count: int
    enforcer_source: str
    decorator_source: str | None
    test_code: str | None
    test_result: str
    test_output: str | None
    diff: str | None
    dd_traces: list[dict] | None
    created_at: str
    updated_at: str


class TestSpriteListItem(BaseModel):
    id: int
    rule_slug: str
    rule_title: str
    repo_url: str
    status: str
    created_at: str


class TestSpriteDetail(BaseModel):
    id: int
    rule_slug: str
    rule_title: str
    repo_url: str
    status: str
    test_plan: dict | list | None
    generated_tests: str | None
    test_results: dict | list | None
    diff: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class RepoStatsResponse(BaseModel):
    full_name: str
    total_prs: int
    processed_comments: int
    unprocessed_comments: int
