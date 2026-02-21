"""Shared test fixtures."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from code_ruler.db.models import Rule
from github_extractor.models import (
    Base,
    PRCommit,
    PullRequest,
    Repository,
    ReviewComment,
)


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with all tables."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    # Also create code_ruler tables (they share the same Base)

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Create a database session for testing."""
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture
def sample_repo(session: Session) -> Repository:
    """Create a sample repository."""
    repo = Repository(
        owner="testowner",
        name="testrepo",
        full_name="testowner/testrepo",
        url="https://github.com/testowner/testrepo",
    )
    session.add(repo)
    session.flush()
    return repo


@pytest.fixture
def sample_pr(session: Session, sample_repo: Repository) -> PullRequest:
    """Create a sample pull request."""
    now = datetime.now(timezone.utc)
    pr = PullRequest(
        repo_id=sample_repo.id,
        number=1,
        title="Fix bug in parser",
        body="This PR fixes the parser bug.",
        author="developer",
        merged_at=now,
        merge_commit_sha="abc123def456",
        base_branch="main",
        head_branch="fix-parser",
        created_at=now,
        updated_at=now,
    )
    session.add(pr)
    session.flush()
    return pr


@pytest.fixture
def sample_commits(session: Session, sample_pr: PullRequest) -> list[PRCommit]:
    """Create sample commits for a PR."""
    now = datetime.now(timezone.utc)
    commits = [
        PRCommit(
            pr_id=sample_pr.id,
            sha="aaa111",
            message="Initial implementation",
            author="developer",
            committed_at=now,
            ordinal=0,
        ),
        PRCommit(
            pr_id=sample_pr.id,
            sha="bbb222",
            message="Address review feedback",
            author="developer",
            committed_at=now,
            ordinal=1,
        ),
        PRCommit(
            pr_id=sample_pr.id,
            sha="ccc333",
            message="Final cleanup",
            author="developer",
            committed_at=now,
            ordinal=2,
        ),
    ]
    for c in commits:
        session.add(c)
    session.flush()
    return commits


@pytest.fixture
def sample_review_comment(session: Session, sample_pr: PullRequest) -> ReviewComment:
    """Create a sample review comment."""
    now = datetime.now(timezone.utc)
    comment = ReviewComment(
        pr_id=sample_pr.id,
        github_id=12345,
        review_id=100,
        in_reply_to_id=None,
        author="reviewer",
        body="Don't use bare except here, catch a specific exception.",
        path="src/parser.py",
        diff_hunk="@@ -10,5 +10,7 @@\n try:\n     parse(data)\n-except:\n+except Exception:\n     log_error()",
        side="RIGHT",
        line=12,
        original_line=12,
        start_line=None,
        original_commit_id="aaa111",
        commit_id="bbb222",
        fix_commit_sha=None,
        created_at=now,
        updated_at=now,
    )
    session.add(comment)
    session.flush()
    return comment


@pytest.fixture
def sample_rule(session: Session, sample_repo: Repository) -> Rule:
    """Create a sample rule."""
    now = datetime.now(timezone.utc)
    rule = Rule(
        slug="no-bare-except",
        repo_id=sample_repo.id,
        category="lint",
        severity="warning",
        title="Do not use bare except clauses",
        description="Always catch a specific exception type instead of using bare `except:`.",
        positive_example="try:\n    parse(data)\nexcept ValueError:\n    handle_error()",
        negative_example="try:\n    parse(data)\nexcept:\n    handle_error()",
        rationale="Bare except catches SystemExit and KeyboardInterrupt, making it hard to terminate the program.",
        created_at=now,
        updated_at=now,
        version=1,
        is_active=True,
    )
    session.add(rule)
    session.flush()
    return rule
