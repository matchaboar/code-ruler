"""Tests for database models."""

from __future__ import annotations

from datetime import datetime, timezone

from github_extractor.models import IssueComment, PRCommit, PullRequest, Repository, ReviewComment
from code_ruler.db.models import FunctionTypeRule, Rule, RuleProvenance
from code_ruler.db.repository import create_rule


def test_repository_creation(session, sample_repo):
    """Test repository creation and retrieval."""
    repo = session.query(Repository).filter_by(full_name="testowner/testrepo").first()
    assert repo is not None
    assert repo.owner == "testowner"
    assert repo.name == "testrepo"


def test_pull_request_relationship(session, sample_pr, sample_repo):
    """Test PR belongs to repository."""
    pr = session.query(PullRequest).first()
    assert pr.repo_id == sample_repo.id
    assert pr.number == 1
    assert pr.title == "Fix bug in parser"


def test_pr_commits(session, sample_pr, sample_commits):
    """Test PR commits are ordered by ordinal."""
    commits = (
        session.query(PRCommit)
        .filter_by(pr_id=sample_pr.id)
        .order_by(PRCommit.ordinal)
        .all()
    )
    assert len(commits) == 3
    assert commits[0].sha == "aaa111"
    assert commits[1].sha == "bbb222"
    assert commits[2].sha == "ccc333"


def test_review_comment(session, sample_review_comment):
    """Test review comment creation."""
    comment = session.query(ReviewComment).first()
    assert comment.github_id == 12345
    assert comment.author == "reviewer"
    assert "bare except" in comment.body


def test_rule_creation(session, sample_rule):
    """Test rule creation."""
    rule = session.query(Rule).filter_by(slug="no-bare-except").first()
    assert rule is not None
    assert rule.category == "lint"
    assert rule.severity == "warning"
    assert rule.is_active is True


def test_function_type_rule(session, sample_rule):
    """Test function type rule linked to rule."""
    ftr = FunctionTypeRule(
        rule_id=sample_rule.id,
        decorator_name="pure_function",
        decorator_source="def pure_function(f): f.__rule_marker_type__ = 'pure_function'; return f",
        linter_source="def check(node, source): return []",
        constraints_json=["no side effects"],
    )
    session.add(ftr)
    session.flush()

    loaded = session.query(FunctionTypeRule).filter_by(rule_id=sample_rule.id).first()
    assert loaded.decorator_name == "pure_function"


def test_rule_provenance(session, sample_rule, sample_pr, sample_review_comment):
    """Test provenance linking rule to PR."""
    prov = RuleProvenance(
        rule_id=sample_rule.id,
        pull_request_id=sample_pr.id,
        review_comment_id=sample_review_comment.id,
        extraction_notes="Extracted from review comment about bare except.",
        created_at=datetime.now(timezone.utc),
    )
    session.add(prov)
    session.flush()

    loaded = session.query(RuleProvenance).first()
    assert loaded.rule_id == sample_rule.id
    assert loaded.pull_request_id == sample_pr.id


def test_create_rule_inserts_new(session):
    """create_rule inserts a new rule when the slug doesn't exist."""
    rule = create_rule(
        session,
        slug="new-rule",
        category="lint",
        severity="warning",
        title="New rule",
        description="desc",
        positive_example=None,
        negative_example=None,
        rationale="reason",
    )
    assert rule.id is not None
    assert rule.version == 1
    assert session.query(Rule).filter_by(slug="new-rule").count() == 1


def test_create_rule_upserts_on_duplicate_slug(session):
    """create_rule updates the existing rule instead of raising IntegrityError."""
    rule1 = create_rule(
        session,
        slug="duplicate-slug",
        category="lint",
        severity="warning",
        title="Original title",
        description="original desc",
        positive_example=None,
        negative_example=None,
        rationale="original reason",
    )
    original_id = rule1.id
    assert rule1.version == 1

    # Same slug, different content — must NOT raise IntegrityError
    rule2 = create_rule(
        session,
        slug="duplicate-slug",
        category="best_practice",
        severity="error",
        title="Updated title",
        description="updated desc",
        positive_example="good code",
        negative_example="bad code",
        rationale="updated reason",
    )

    # Should return the same row, updated in place
    assert rule2.id == original_id
    assert rule2.version == 2
    assert rule2.category == "best_practice"
    assert rule2.severity == "error"
    assert rule2.title == "Updated title"
    assert rule2.description == "updated desc"
    assert rule2.positive_example == "good code"
    assert rule2.negative_example == "bad code"
    assert rule2.rationale == "updated reason"

    # Only one row in the table with this slug
    assert session.query(Rule).filter_by(slug="duplicate-slug").count() == 1
