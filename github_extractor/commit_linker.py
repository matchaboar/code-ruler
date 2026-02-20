"""Algorithm to compute fix_commit_sha for review comments."""

from __future__ import annotations

from datetime import datetime

from github_extractor.models import PRCommit, ReviewComment


def compute_fix_commit_sha(
    comment: ReviewComment,
    commits: list[PRCommit],
) -> str | None:
    """Compute the fix_commit_sha for a review comment.

    Algorithm:
    1. Get PR commits ordered by ordinal.
    2. Find original_commit_id in the list -> fix = commits[index + 1].
    3. If not found (force-push rewrote history) -> fallback: earliest commit after comment.created_at.
    4. If comment is on the last commit -> fix = None.
    """
    if not commits:
        return None

    sorted_commits = sorted(commits, key=lambda c: c.ordinal)

    # Try to find the original commit in the list
    if comment.original_commit_id:
        for i, commit in enumerate(sorted_commits):
            if commit.sha == comment.original_commit_id:
                if i + 1 < len(sorted_commits):
                    return sorted_commits[i + 1].sha
                # Comment is on the last commit
                return None

    # Fallback: earliest commit after comment.created_at
    comment_time = comment.created_at
    if isinstance(comment_time, datetime):
        for commit in sorted_commits:
            if commit.committed_at > comment_time:
                return commit.sha

    return None
