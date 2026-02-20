"""Pydantic response models for the rule viewer API."""

from __future__ import annotations

from pydantic import BaseModel


class RuleListItem(BaseModel):
    slug: str
    category: str
    severity: str
    title: str
    is_active: bool
    has_decorator: bool
    provenance_count: int


class RuleDetail(BaseModel):
    slug: str
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


class RepoStatsResponse(BaseModel):
    full_name: str
    total_prs: int
    processed_comments: int
    unprocessed_comments: int
