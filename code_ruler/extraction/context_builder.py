"""Assembles PR + comment + diff into LLM prompt context."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from code_ruler.db.models import RuleProvenance
from github_extractor.models import PullRequest, Repository, ReviewComment


@dataclass
class ExtractionContext:
    """Context for a single review comment to send to the LLM."""

    repo_name: str
    pr_number: int
    pr_title: str
    pr_author: str
    comment_author: str
    comment_body: str
    file_path: str
    diff_hunk: str
    pr_id: int
    review_comment_id: int


def build_contexts(
    session: Session,
    limit: int | None = None,
    repo_full_name: str | None = None,
) -> list[ExtractionContext]:
    """Build extraction contexts from review comments that haven't been processed yet.

    Filters out comments that already have a RuleProvenance entry, so re-running
    the pipeline only processes new/unprocessed comments.

    If *repo_full_name* is given, only comments from that repository are returned.
    """
    # Subquery: comment IDs that already have provenance
    processed_ids = (
        session.query(RuleProvenance.review_comment_id)
        .filter(RuleProvenance.review_comment_id.isnot(None))
        .subquery()
    )

    query = (
        session.query(ReviewComment, PullRequest, Repository)
        .join(PullRequest, ReviewComment.pr_id == PullRequest.id)
        .join(Repository, PullRequest.repo_id == Repository.id)
        .filter(ReviewComment.in_reply_to_id.is_(None))  # Only top-level comments
        .filter(~ReviewComment.id.in_(processed_ids))  # Skip already-processed
    )

    if repo_full_name:
        query = query.filter(Repository.full_name == repo_full_name)

    if limit:
        query = query.limit(limit)

    contexts = []
    for comment, pr, repo in query.all():
        contexts.append(
            ExtractionContext(
                repo_name=repo.full_name,
                pr_number=pr.number,
                pr_title=pr.title,
                pr_author=pr.author,
                comment_author=comment.author,
                comment_body=comment.body,
                file_path=comment.path,
                diff_hunk=comment.diff_hunk,
                pr_id=pr.id,
                review_comment_id=comment.id,
            )
        )

    return contexts
