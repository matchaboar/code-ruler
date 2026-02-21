"""Tests for commit linker algorithm."""

from __future__ import annotations

from datetime import datetime, timezone

from github_extractor.commit_linker import compute_fix_commit_sha
from github_extractor.models import ReviewComment


def test_fix_commit_found_by_original(session, sample_review_comment, sample_commits):
    """When original_commit_id matches a commit, fix is the next one."""
    # sample_review_comment has original_commit_id="aaa111" (ordinal 0)
    # so fix should be "bbb222" (ordinal 1)
    fix = compute_fix_commit_sha(sample_review_comment, sample_commits)
    assert fix == "bbb222"


def test_fix_commit_last_commit(session, sample_pr, sample_commits):
    """When comment is on the last commit, fix is None."""
    now = datetime.now(timezone.utc)
    comment = ReviewComment(
        pr_id=sample_pr.id,
        github_id=99999,
        author="reviewer",
        body="Comment on last commit",
        path="file.py",
        diff_hunk="some diff",
        original_commit_id="ccc333",  # last commit
        commit_id="ccc333",
        created_at=now,
        updated_at=now,
    )
    session.add(comment)
    session.flush()

    fix = compute_fix_commit_sha(comment, sample_commits)
    assert fix is None


def test_fix_commit_not_found_fallback(session, sample_pr, sample_commits):
    """When original_commit_id is not in commits, fallback to time-based."""
    # Use a time before all commits so we can find one after
    early = datetime(2020, 1, 1, tzinfo=timezone.utc)
    comment = ReviewComment(
        pr_id=sample_pr.id,
        github_id=88888,
        author="reviewer",
        body="Comment on force-pushed commit",
        path="file.py",
        diff_hunk="some diff",
        original_commit_id="zzz000",  # not in commit list
        commit_id="ccc333",
        created_at=early,
        updated_at=early,
    )
    session.add(comment)
    session.flush()

    fix = compute_fix_commit_sha(comment, sample_commits)
    # Should find the first commit after early time
    assert fix is not None


def test_fix_commit_empty_commits(session, sample_review_comment):
    """When there are no commits, fix is None."""
    fix = compute_fix_commit_sha(sample_review_comment, [])
    assert fix is None
