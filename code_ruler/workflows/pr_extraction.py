"""DBOS durable workflow for extracting PRs from GitHub."""

from __future__ import annotations

from dbos import DBOS


@DBOS.workflow()
def extract_prs_workflow(
    db_path: str,
    repo_url: str,
    job_id: str,
    limit: int | None = None,
) -> dict:
    """Durable workflow: extract merged PRs from a GitHub repo.

    Steps:
      1. list_merged_prs — fetch PR numbers from GitHub API
      2. extract_single_pr_step — for each PR, fetch data and store in DB
    """
    from code_ruler.workflows.events import create_job, emit_event, update_job_status

    workflow_id = DBOS.workflow_id
    create_job(db_path, job_id, "extract-prs", repo_url, {"limit": limit}, workflow_id=workflow_id)

    try:
        pr_list = list_merged_prs(db_path, repo_url, limit)

        extracted = 0
        skipped = 0
        for pr_info in pr_list:
            result = extract_single_pr_step(
                db_path, repo_url, pr_info["number"],
            )
            if result["status"] == "extracted":
                extracted += 1
            else:
                skipped += 1
            emit_event(db_path, job_id, f"pr_{result['status']}", {
                "pr_number": pr_info["number"],
                "pr_title": pr_info["title"],
                "author": pr_info["author"],
            })

        update_job_status(db_path, job_id, "completed")
        return {"extracted": extracted, "skipped": skipped, "total": len(pr_list)}
    except Exception as e:
        update_job_status(db_path, job_id, "failed", error=str(e))
        raise


@DBOS.step()
def list_merged_prs(
    db_path: str,
    repo_url: str,
    limit: int | None = None,
) -> list[dict]:
    """Fetch the list of merged PR numbers/titles from GitHub API."""
    from github_extractor.client import check_rate_limit, create_github_client, get_repo, parse_repo_url

    owner, name = parse_repo_url(repo_url)
    client = create_github_client()
    gh_repo = get_repo(client, owner, name)
    pulls = gh_repo.get_pulls(state="closed", sort="updated", direction="desc")

    result: list[dict] = []
    count = 0
    for gh_pr in pulls:
        if limit is not None and count >= limit:
            break
        if not gh_pr.merged:
            continue
        check_rate_limit(client)
        author = gh_pr.user.login if gh_pr.user else "unknown"
        result.append({
            "number": gh_pr.number,
            "title": gh_pr.title,
            "author": author,
        })
        count += 1

    return result


@DBOS.step()
def extract_single_pr_step(
    db_path: str,
    repo_url: str,
    pr_number: int,
) -> dict:
    """Fetch a single PR's data from GitHub and store it in the DB.

    Returns {"status": "extracted"} or {"status": "skipped"}.
    """
    from github_extractor.client import create_github_client, get_repo, parse_repo_url
    from github_extractor.database import get_engine, get_session_factory, init_db
    from github_extractor.extractor import _extract_pr
    from github_extractor.models import PullRequest, Repository

    owner, name = parse_repo_url(repo_url)
    full_name = f"{owner}/{name}"

    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)

    with factory() as session:
        repo = session.query(Repository).filter_by(full_name=full_name).first()
        if not repo:
            repo = Repository(owner=owner, name=name, full_name=full_name, url=repo_url)
            session.add(repo)
            session.flush()

        existing = session.query(PullRequest).filter_by(
            repo_id=repo.id, number=pr_number
        ).first()
        if existing:
            return {"status": "skipped"}

        client = create_github_client()
        gh_repo = get_repo(client, owner, name)
        gh_pr = gh_repo.get_pull(pr_number)

        _extract_pr(session, repo.id, gh_pr)
        session.commit()

    return {"status": "extracted"}
