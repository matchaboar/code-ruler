"""Core orchestration: fetch PRs, comments, and commits from GitHub into SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from github import Github
from github.PullRequest import PullRequest as GHPullRequest
from sqlalchemy.orm import Session

from github_extractor.client import check_rate_limit, get_repo, parse_repo_url
from github_extractor.commit_linker import compute_fix_commit_sha
from github_extractor.models import (
    IssueComment,
    PRCommit,
    PullRequest,
    Repository,
    ReviewComment,
)


def extract_repo(
    client: Github,
    repo_url: str,
    session: Session,
    limit: int | None = None,
    on_pr: Callable[[int, str, str, str], None] | None = None,
) -> None:
    """Extract merged PRs with comments and commits from a GitHub repo.

    Args:
        on_pr: Optional callback(pr_number, pr_title, author, status).
               status is "extracted" or "skipped".
    """
    owner, name = parse_repo_url(repo_url)
    full_name = f"{owner}/{name}"

    # Get or create repository record
    repo = session.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        repo = Repository(
            owner=owner,
            name=name,
            full_name=full_name,
            url=repo_url,
        )
        session.add(repo)
        session.flush()

    gh_repo = get_repo(client, owner, name)

    # Fetch merged PRs
    pulls = gh_repo.get_pulls(state="closed", sort="updated", direction="desc")

    count = 0
    for gh_pr in pulls:
        if limit is not None and count >= limit:
            break

        if not gh_pr.merged:
            continue

        # Check rate limit before processing each PR
        check_rate_limit(client)

        # Skip already-extracted PRs
        existing = (
            session.query(PullRequest)
            .filter_by(repo_id=repo.id, number=gh_pr.number)
            .first()
        )
        if existing:
            if on_pr:
                author = gh_pr.user.login if gh_pr.user else "unknown"
                on_pr(gh_pr.number, gh_pr.title, author, "skipped")
            count += 1
            continue

        print(f"  Extracting PR #{gh_pr.number}: {gh_pr.title}")
        _extract_pr(session, repo.id, gh_pr)
        session.commit()
        author = gh_pr.user.login if gh_pr.user else "unknown"
        if on_pr:
            on_pr(gh_pr.number, gh_pr.title, author, "extracted")
        count += 1

    # Update extracted_at
    repo.extracted_at = datetime.now(timezone.utc)
    session.commit()
    print(f"Done. Extracted {count} merged PRs from {full_name}.")


def _extract_pr(session: Session, repo_id: int, gh_pr: GHPullRequest) -> None:
    """Extract a single PR with its commits and comments."""
    pr = PullRequest(
        repo_id=repo_id,
        number=gh_pr.number,
        title=gh_pr.title,
        body=gh_pr.body,
        author=gh_pr.user.login if gh_pr.user else "unknown",
        merged_at=gh_pr.merged_at,
        merge_commit_sha=gh_pr.merge_commit_sha,
        base_branch=gh_pr.base.ref,
        head_branch=gh_pr.head.ref,
        created_at=gh_pr.created_at,
        updated_at=gh_pr.updated_at,
    )
    session.add(pr)
    session.flush()

    # Extract commits
    commits = _extract_commits(session, pr.id, gh_pr)

    # Extract review comments with fix_commit_sha
    _extract_review_comments(session, pr.id, gh_pr, commits)

    # Extract issue comments
    _extract_issue_comments(session, pr.id, gh_pr)


def _extract_commits(
    session: Session, pr_id: int, gh_pr: GHPullRequest
) -> list[PRCommit]:
    """Extract commits for a PR."""
    commits = []
    for i, gh_commit in enumerate(gh_pr.get_commits()):
        commit = PRCommit(
            pr_id=pr_id,
            sha=gh_commit.sha,
            message=gh_commit.commit.message,
            author=gh_commit.commit.author.name if gh_commit.commit.author else "unknown",
            committed_at=gh_commit.commit.committer.date if gh_commit.commit.committer else gh_commit.commit.author.date,
            ordinal=i,
        )
        session.add(commit)
        commits.append(commit)
    session.flush()
    return commits


def _extract_review_comments(
    session: Session,
    pr_id: int,
    gh_pr: GHPullRequest,
    commits: list[PRCommit],
) -> None:
    """Extract review comments for a PR and compute fix_commit_sha."""
    for gh_comment in gh_pr.get_review_comments():
        comment = ReviewComment(
            pr_id=pr_id,
            github_id=gh_comment.id,
            review_id=gh_comment.pull_request_review_id,
            in_reply_to_id=gh_comment.in_reply_to_id,
            author=gh_comment.user.login if gh_comment.user else "unknown",
            body=gh_comment.body,
            path=gh_comment.path,
            diff_hunk=gh_comment.diff_hunk,
            side=gh_comment.side if hasattr(gh_comment, "side") else None,
            line=getattr(gh_comment, "line", None),
            original_line=getattr(gh_comment, "original_line", None),
            start_line=gh_comment.start_line if hasattr(gh_comment, "start_line") else None,
            original_commit_id=gh_comment.original_commit_id,
            commit_id=gh_comment.commit_id,
            created_at=gh_comment.created_at,
            updated_at=gh_comment.updated_at,
        )
        session.add(comment)
        session.flush()

        # Compute fix_commit_sha
        comment.fix_commit_sha = compute_fix_commit_sha(comment, commits)

    session.flush()


def _extract_issue_comments(
    session: Session, pr_id: int, gh_pr: GHPullRequest
) -> None:
    """Extract issue-level comments for a PR."""
    for gh_comment in gh_pr.get_issue_comments():
        comment = IssueComment(
            pr_id=pr_id,
            github_id=gh_comment.id,
            author=gh_comment.user.login if gh_comment.user else "unknown",
            body=gh_comment.body,
            created_at=gh_comment.created_at,
            updated_at=gh_comment.updated_at,
        )
        session.add(comment)
    session.flush()
