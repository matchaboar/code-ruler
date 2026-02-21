"""DBOS durable workflows for quick-batch operations."""

from __future__ import annotations

from dbos import DBOS


@DBOS.workflow()
def quick_fetch_prs(db_path: str, job_id: str, repo_url: str, limit: int = 10) -> dict:
    """Quick-fetch: extract a small batch of PRs."""
    from code_ruler.workflows.pr_extraction import extract_prs_workflow

    return extract_prs_workflow(db_path, repo_url, job_id, limit=limit)


@DBOS.workflow()
def quick_extract_rules(
    db_path: str,
    job_id: str,
    limit: int = 10,
    repo_filter: str | None = None,
) -> dict:
    """Quick-extract: extract rules from a small batch of comments."""
    from code_ruler.workflows.rule_extraction import extract_rules_workflow

    return extract_rules_workflow(
        db_path, job_id, limit=limit, dry_run=False, repo_full_name=repo_filter,
    )


@DBOS.workflow()
def quick_run_workflow(
    db_path: str,
    job_id: str,
    repo_url: str,
    pr_limit: int = 10,
) -> dict:
    """Quick-run: fetch PRs then extract rules in one go."""
    from code_ruler.workflows.events import create_job, update_job_status
    from code_ruler.workflows.pr_extraction import list_merged_prs, extract_single_pr_step
    from code_ruler.workflows.rule_extraction import extract_rules_workflow

    workflow_id = DBOS.workflow_id
    create_job(db_path, job_id, "quick-run", repo_url, {"pr_limit": pr_limit}, workflow_id=workflow_id)

    # Step 1: Extract PRs (inline the steps so they checkpoint under this workflow)
    pr_list = list_merged_prs(db_path, repo_url, pr_limit)
    for pr_info in pr_list:
        extract_single_pr_step(db_path, repo_url, pr_info["number"])

    # Step 2: Extract rules from all unprocessed comments
    # Use a child workflow for rule extraction
    from github_extractor.client import parse_repo_url
    owner, name = parse_repo_url(repo_url)
    repo_full_name = f"{owner}/{name}"

    rules_result = extract_rules_workflow(
        db_path, f"{job_id}-rules", limit=None, dry_run=False, repo_full_name=repo_full_name,
    )

    update_job_status(db_path, job_id, "completed")
    return {
        "prs_fetched": len(pr_list),
        "rules_stored": rules_result.get("rules_stored", 0),
    }
