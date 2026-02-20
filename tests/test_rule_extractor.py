"""Tests for rule extraction (unit tests without LLM calls)."""

from __future__ import annotations

from code_ruler.llm.schemas import CandidateRule, MergeDecision


def test_candidate_rule_schema():
    """Test CandidateRule Pydantic model."""
    rule = CandidateRule(
        slug="no-bare-except",
        category="lint",
        severity="warning",
        title="No bare except",
        description="Don't use bare except clauses.",
        rationale="Catches too broadly.",
    )
    assert rule.slug == "no-bare-except"
    assert rule.positive_example is None


def test_merge_decision_keep_both():
    """Test MergeDecision for keep_both action."""
    decision = MergeDecision(
        action="keep_both",
        reasoning="Rules are distinct.",
    )
    assert decision.action == "keep_both"
    assert decision.merged_rule is None


def test_merge_decision_merge():
    """Test MergeDecision with merged rule."""
    merged = CandidateRule(
        slug="combined-rule",
        category="lint",
        severity="error",
        title="Combined rule",
        description="Merged description.",
        rationale="Combined rationale.",
    )
    decision = MergeDecision(
        action="merge",
        merged_rule=merged,
        reasoning="Rules overlap significantly.",
    )
    assert decision.action == "merge"
    assert decision.merged_rule.slug == "combined-rule"
