// ---- Types matching backend Pydantic schemas ----

export interface RuleListItem {
  slug: string;
  category: string;
  severity: string;
  title: string;
  is_active: boolean;
  has_decorator: boolean;
  provenance_count: number;
}

export interface RuleDetail {
  slug: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  positive_example: string | null;
  negative_example: string | null;
  rationale: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  decorator_name: string | null;
  decorator_source: string | null;
  linter_source: string | null;
  constraints: string[] | null;
}

export interface ProvenanceItem {
  pr_number: number;
  pr_title: string;
  pr_url: string;
  repo_full_name: string;
  comment_author: string;
  comment_body: string;
  diff_hunk: string;
  file_path: string;
  original_commit_sha: string | null;
  fix_commit_sha: string | null;
  extraction_notes: string | null;
}

export interface Stats {
  total_rules: number;
  rules_by_category: Record<string, number>;
  rules_by_severity: Record<string, number>;
  total_prs_processed: number;
}

// ---- Fetch helpers ----

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface RuleListParams {
  category?: string;
  severity?: string;
  is_active?: boolean;
  search?: string;
}

export function fetchRules(params?: RuleListParams): Promise<RuleListItem[]> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.is_active !== undefined)
    qs.set("is_active", String(params.is_active));
  if (params?.search) qs.set("search", params.search);
  const query = qs.toString();
  return apiFetch<RuleListItem[]>(`/api/rules${query ? `?${query}` : ""}`);
}

export function fetchRule(slug: string): Promise<RuleDetail> {
  return apiFetch<RuleDetail>(`/api/rules/${encodeURIComponent(slug)}`);
}

export function fetchProvenance(slug: string): Promise<ProvenanceItem[]> {
  return apiFetch<ProvenanceItem[]>(
    `/api/rules/${encodeURIComponent(slug)}/provenance`
  );
}

export function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/api/stats");
}

export interface ServiceStatus {
  name: string;
  ok: boolean;
  detail: string;
}

export interface CredentialsStatus {
  services: ServiceStatus[];
}

export function fetchCredentialsStatus(): Promise<CredentialsStatus> {
  return apiFetch<CredentialsStatus>("/api/credentials/status");
}

// ---- Pipeline types and helpers ----

export interface JobStartResponse {
  job_id: string;
}

export interface JobEvent {
  type: string;
  data: Record<string, any>;
}

export interface JobStatus {
  job_id: string;
  kind: string;
  status: "running" | "completed" | "failed";
  logs: string[];
  events: JobEvent[];
  repo_url: string | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface RepoStats {
  full_name: string;
  total_prs: number;
  processed_comments: number;
  unprocessed_comments: number;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function startExtractPRs(
  repoUrl: string,
  limit?: number
): Promise<JobStartResponse> {
  return apiPost<JobStartResponse>("/api/pipeline/extract-prs", {
    repo_url: repoUrl,
    limit: limit ?? null,
  });
}

export function startExtractRules(
  limit?: number,
  dryRun?: boolean,
  repoFullName?: string
): Promise<JobStartResponse> {
  return apiPost<JobStartResponse>("/api/pipeline/extract-rules", {
    limit: limit ?? null,
    dry_run: dryRun ?? false,
    repo_full_name: repoFullName ?? null,
  });
}

export function startQuickRun(
  repoUrl: string,
  prLimit: number = 10
): Promise<JobStartResponse> {
  return apiPost<JobStartResponse>("/api/pipeline/quick-run", {
    repo_url: repoUrl,
    pr_limit: prLimit,
  });
}

export function fetchJobStatus(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/pipeline/jobs/${encodeURIComponent(jobId)}`);
}

export function fetchJobs(): Promise<JobStatus[]> {
  return apiFetch<JobStatus[]>("/api/pipeline/jobs");
}

export function fetchRepoStats(): Promise<RepoStats[]> {
  return apiFetch<RepoStats[]>("/api/pipeline/repo-stats");
}
