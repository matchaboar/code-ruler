"""Pydantic models for structured LLM output."""

from __future__ import annotations

from pydantic import BaseModel


class CandidateRule(BaseModel):
    """A candidate rule extracted from PR review data."""

    slug: str
    category: str  # best_practice, lint, function_usage, function_type
    severity: str  # error, warning, info
    title: str
    description: str
    positive_example: str | None = None
    negative_example: str | None = None
    rationale: str


class FunctionTypeSpec(BaseModel):
    """Specification for a function type rule's decorator and linter."""

    decorator_name: str
    constraints: list[str]
    decorator_source: str
    linter_source: str


class MergeDecision(BaseModel):
    """LLM decision on whether a candidate rule is a duplicate."""

    action: str  # merge, discard, keep_both
    merged_rule: CandidateRule | None = None
    reasoning: str
