"""Tests for rule deduplication (schema validation)."""

from __future__ import annotations

from code_ruler.llm.schemas import CandidateRule, FunctionTypeSpec


def test_function_type_spec():
    """Test FunctionTypeSpec schema."""
    spec = FunctionTypeSpec(
        decorator_name="pure_function",
        constraints=["no side effects", "deterministic"],
        decorator_source="def pure_function(f): f.__rule_marker_type__ = 'pure_function'; return f",
        linter_source="def check(node, source): return []",
    )
    assert spec.decorator_name == "pure_function"
    assert len(spec.constraints) == 2


def test_candidate_rule_with_examples():
    """Test CandidateRule with all fields."""
    rule = CandidateRule(
        slug="use-pathlib",
        category="best_practice",
        severity="info",
        title="Use pathlib for file paths",
        description="Prefer pathlib.Path over os.path for file path manipulation.",
        positive_example="from pathlib import Path\nf = Path('data') / 'file.txt'",
        negative_example="import os\nf = os.path.join('data', 'file.txt')",
        rationale="pathlib provides a more Pythonic, object-oriented API for paths.",
    )
    assert rule.category == "best_practice"
    assert rule.positive_example is not None
    assert rule.negative_example is not None
