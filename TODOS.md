# TODO: Refactor Pipelines to Resumable DBOS Workflows

## Background

Currently, pipeline jobs (PR extraction, rule extraction, quick-run) execute in background
threads with in-memory job tracking (`_jobs` dict in `rule_viewer/api/pipeline.py`). This means:

- Jobs are lost on server restart — no persistence or resumability
- No way to recover a partially-completed extraction if the process crashes mid-run
- Each review comment re-processes from scratch if the pipeline is re-triggered
- Job history disappears when the server restarts

DBOS provides lightweight durable execution by checkpointing workflow/step state to a database,
enabling automatic resume-from-last-completed-step on failure or restart.

---

## Phase 1: Add DBOS + Postgres Infrastructure

- [ ] Add `dbos` to project dependencies via `uv add dbos`
- [ ] Add a Postgres database for DBOS system tables (can be separate from the existing
      SQLite app database, or we migrate the app DB to Postgres too — decide below)
- [ ] Initialize DBOS in `rule_viewer/main.py` with FastAPI integration:
  ```python
  from dbos import DBOS, DBOSConfig
  config: DBOSConfig = {
      "name": "code-ruler",
      "system_database_url": os.environ.get("DBOS_SYSTEM_DATABASE_URL"),
  }
  DBOS(config=config)
  DBOS.launch()
  ```
- [ ] Decide: keep SQLite for app data + Postgres for DBOS, or migrate everything to Postgres
  - Recommendation: keep SQLite for now, use a separate Postgres for DBOS system tables.
    Migrate app data later if needed.

## Phase 2: Refactor PR Extraction as a DBOS Workflow

**Current flow** (`github_extractor/extractor.py` called from `rule_viewer/api/pipeline.py`):
Thread spawned → fetch PRs from GitHub API → store each PR + comments in DB → done

**Target:**

- [ ] Create `code_ruler/workflows/pr_extraction.py`
- [ ] Define the top-level workflow:
  ```python
  @DBOS.workflow()
  def extract_prs_workflow(repo_url: str, limit: int | None = None) -> ExtractPRsResult:
      repo = fetch_repo_metadata(repo_url)       # step
      pr_numbers = list_mergeable_prs(repo)       # step
      for pr_num in pr_numbers[:limit]:
          extract_single_pr(repo, pr_num)          # step (one per PR)
      return ExtractPRsResult(...)
  ```
- [ ] Each `@DBOS.step()` is individually checkpointed — if the server crashes after
      extracting 50 of 100 PRs, it resumes at PR 51
- [ ] Replace the thread-based `_start_extract_prs_job()` with `DBOS.start_workflow()`
- [ ] Use `SetWorkflowID` with a deterministic ID (e.g. `extract-prs-{repo}-{timestamp}`) for
      idempotency

## Phase 3: Refactor Rule Extraction as a DBOS Workflow

**Current flow** (`code_ruler/pipeline.py`):
Build contexts → for each context: extract rules via LLM → dedup → store. Events emitted
via `on_review` callback.

### CRITICAL: Resumable Progress Across the PR Backlog

This is the most important property of the new design. The rule extraction workflow must
track **per-comment processed state** durably, so that progress is never lost:

- Example: 200 PRs extracted, 0 comments processed. User kicks off rule extraction.
  The runner crashes after processing 10 comments. On restart/resume, DBOS picks up at
  comment 11 — the 10 already-processed comments are checkpointed and never re-run.
- This must work whether the user explicitly resumes or the server simply restarts.
- The `build_extraction_contexts` step already filters out comments that have a
  `RuleProvenance` entry. Combined with DBOS step checkpointing, this gives us two layers
  of protection: the app-level "already has provenance" filter AND the DBOS "step already
  completed" checkpoint.

**Target:**

- [ ] Create `code_ruler/workflows/rule_extraction.py`
- [ ] Define the top-level workflow:
  ```python
  @DBOS.workflow()
  def extract_rules_workflow(
      limit: int | None = None,
      dry_run: bool = False,
      repo_filter: str | None = None,
  ) -> ExtractRulesResult:
      contexts = build_extraction_contexts(limit, repo_filter)  # step
      results = []
      for ctx in contexts:
          result = process_single_review(ctx, dry_run)           # step (one per comment)
          results.append(result)
      return ExtractRulesResult(results=results)
  ```
- [ ] `process_single_review` is itself a step (or a child workflow) containing:
  - Call LLM to extract candidate rules
  - For each candidate: dedup check → store/merge/discard
  - Generate function type code if applicable
- [ ] **Each LLM call MUST be a separate `@DBOS.step()`** so that expensive LLM calls
      are never re-executed after completion — this is the single biggest win for resumability.
      A crash mid-dedup should not re-run the extraction LLM call.
- [ ] Preserve the `on_review` event callback pattern by writing events to a DB table
      (replacing the in-memory list) so the UI can query them

## Phase 4: Quick-Batch Buttons ("Do Next N" Pattern)

The UI should support a simple incremental workflow: press a button, process the next batch,
press it again for the next batch. No need to specify ranges or manage workflow state manually.

### Quick PR Fetch (next N)

- [ ] `POST /pipeline/quick-fetch-prs` with `{ repo_url, limit: 10 }`
  - Fetches the next 10 un-fetched PRs from the repo
  - Each press of the button grabs the next 10 — idempotent, no overlap
  - Runs as a DBOS workflow; if it crashes mid-batch, resumes where it left off
  ```python
  @DBOS.workflow()
  def quick_fetch_prs(repo_url: str, limit: int = 10) -> QuickFetchResult:
      unfetched = get_next_unfetched_prs(repo_url, limit)  # step
      for pr in unfetched:
          extract_single_pr(repo_url, pr)                    # step
      return QuickFetchResult(fetched=len(unfetched))
  ```

### Quick Rule Extract (next N PRs worth of comments)

- [ ] `POST /pipeline/quick-extract-rules` with `{ limit: 10, repo_filter? }`
  - Processes unprocessed comments from the next 10 PRs on the backlog
  - Each press chews through another 10 PRs worth of review comments
  - Durable: crash after 6 PRs → resume picks up at PR 7
  ```python
  @DBOS.workflow()
  def quick_extract_rules(limit: int = 10, repo_filter: str | None = None) -> QuickExtractResult:
      contexts = build_extraction_contexts(limit, repo_filter)  # step
      for ctx in contexts:
          process_single_review(ctx)                             # step
      return QuickExtractResult(processed=len(contexts))
  ```

### Quick-Run (fetch N + extract N, composed)

- [ ] Keep the existing quick-run concept as a composed workflow:
  ```python
  @DBOS.workflow()
  def quick_run_workflow(repo_url: str, limit: int = 10) -> QuickRunResult:
      pr_result = quick_fetch_prs(repo_url, limit)
      rule_result = quick_extract_rules(limit, repo_filter=repo_url)
      return QuickRunResult(pr_result=pr_result, rule_result=rule_result)
  ```

### UI for Quick-Batch

- [ ] Add prominent "Fetch Next 10 PRs" and "Extract Next 10 PRs" buttons to the
      pipeline page (not buried in a form)
- [ ] Show the current backlog size next to each button:
  - "Fetch Next 10 PRs (142 remaining)"
  - "Extract Next 10 PRs (87 unprocessed)"
- [ ] Buttons are disabled while a workflow for the same action is already running
- [ ] On completion, auto-refresh the backlog counts so the user sees progress
- [ ] Optionally let the user change the batch size (default 10) via a small dropdown

## Phase 5: Persist Job Events + Replace In-Memory Job Store

Currently `_jobs` dict holds job info, logs, and events in memory.

- [ ] Create a `pipeline_jobs` table:
  ```
  id (UUID PK), workflow_id (FK to DBOS), job_type, status, created_at, updated_at,
  params_json, error_message
  ```
- [ ] Create a `pipeline_events` table:
  ```
  id (auto PK), job_id (FK), event_type, event_data_json, created_at
  ```
- [ ] Migrate event emission from in-memory callbacks to DB inserts
  - Each `on_review` / `on_pr` callback writes a row to `pipeline_events`
  - Include Datadog trace info in `event_data_json`
- [ ] Update API endpoints to query these tables instead of `_jobs` dict
- [ ] Job logs: either store in the events table or capture via DBOS's built-in logging

## Phase 6: Update Backend API for Workflow Management

- [ ] `POST /pipeline/extract-prs` → calls `DBOS.start_workflow(extract_prs_workflow, ...)`
      and returns the workflow_id as the job ID
- [ ] `POST /pipeline/extract-rules` → same pattern
- [ ] `POST /pipeline/quick-run` → same pattern
- [ ] `GET /pipeline/jobs` → query `pipeline_jobs` table + DBOS workflow status
- [ ] `GET /pipeline/jobs/{job_id}` → join `pipeline_jobs` + `pipeline_events` + DBOS status
- [ ] Add new endpoints:
  - [ ] `POST /pipeline/jobs/{job_id}/resume` — calls `DBOS.resume_workflow(workflow_id)`
  - [ ] `POST /pipeline/jobs/{job_id}/cancel` — calls `DBOS.cancel_workflow(workflow_id)`
  - [ ] `GET /pipeline/jobs/{job_id}/steps` — calls `DBOS.list_workflow_steps(workflow_id)`
        to show granular progress (which steps completed, which is running)
- [ ] Remove thread-based job runner code from `rule_viewer/api/pipeline.py`

## Phase 7: Refactor Frontend — Pipeline List View

- [ ] Update job list to show DBOS workflow status (pending, running, completed, cancelled,
      failed, retrying)
- [ ] Add resume/cancel action buttons per job
- [ ] Show step-level progress: "Processed 47/120 review comments" derived from
      completed step count
- [ ] Add a progress bar based on completed steps / total steps
- [ ] Show time elapsed and estimated time remaining (based on avg step duration)
- [ ] Persist and display job history across server restarts

## Phase 8: Refactor Frontend — Pipeline Detail View

- [ ] Replace polling-based updates with either:
  - SSE (Server-Sent Events) endpoint for real-time step completion streaming, or
  - Continue polling but from persisted DB state (simpler, and fine for this use case)
- [ ] Show a step-level timeline/graph:
  - Each review comment as a row
  - Status: pending → extracting → deduplicating → stored/discarded/merged
  - Expandable to show LLM call details + Datadog trace links
- [ ] Add "Resume from here" button that appears on failed/cancelled workflows
- [ ] Add "Fork from step" capability for re-running from a specific failed step
- [ ] Improve error display: show which specific step failed and why, not just a generic
      error message
- [ ] Add a "Retry failed steps" action that resumes the workflow

## Phase 9: Refactor Frontend — New Pipeline Form & Repo Stats

- [ ] Update the "New Pipeline" form:
  - Show warning if a workflow for the same repo is already running
  - Option to resume an interrupted workflow instead of starting fresh
- [ ] Update repo stats section:
  - Show active workflows per repo
  - Show last workflow status and when it ran
  - "Resume" button should resume the actual DBOS workflow (not start a new job)

---

## Migration Strategy

1. Implement phases 1–3 behind a feature flag so the old thread-based runner still works
2. Run both systems in parallel during testing
3. Once validated, remove the old thread-based code
4. Frontend changes (phases 7–9) can be done incrementally since the API shape is similar

## Open Questions

- **Postgres requirement**: DBOS needs Postgres for its system database. Do we want to add
  this as a hard dependency, or make it optional (fallback to the current thread-based
  approach when Postgres isn't configured)?
- **SQLite vs Postgres for app data**: Keep SQLite for the app database (rules, PRs, comments)
  or migrate everything to Postgres? SQLite is simpler for local dev; Postgres is better for
  concurrent access from workflows.
- **Event streaming**: SSE for real-time UI updates, or keep polling? Polling is simpler and
  the current 2-second interval is fine for most use cases.
- **Queue-based concurrency**: Should we use DBOS queues to process multiple review comments
  concurrently (e.g. 3 at a time) instead of sequentially? This would speed up extraction
  but increases Bedrock API cost/rate-limit pressure.
