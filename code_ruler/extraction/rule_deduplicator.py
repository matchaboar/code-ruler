"""LLM-based duplicate detection and merge decisions."""

from __future__ import annotations

from anthropic import AnthropicBedrock

from code_ruler.db.models import Rule
from code_ruler.llm.client import call_llm_json
from code_ruler.llm.prompts import DEDUP_SYSTEM, DEDUP_USER
from code_ruler.llm.schemas import CandidateRule, MergeDecision


def check_duplicate(
    client: AnthropicBedrock,
    candidate: CandidateRule,
    existing_rules: list[Rule],
    model: str,
) -> MergeDecision:
    """Check if a candidate rule is a duplicate of any existing rule."""
    if not existing_rules:
        return MergeDecision(action="keep_both", reasoning="No existing rules to compare against.")

    existing_text = "\n".join(
        f"- {r.slug}: {r.title} ({r.category})" for r in existing_rules
    )

    user_message = DEDUP_USER.format(
        candidate_slug=candidate.slug,
        candidate_title=candidate.title,
        candidate_description=candidate.description,
        candidate_category=candidate.category,
        existing_rules=existing_text,
    )

    result = call_llm_json(client, DEDUP_SYSTEM, user_message, model=model)

    merged_rule = None
    if result.get("merged_rule"):
        try:
            merged_rule = CandidateRule(**result["merged_rule"])
        except Exception:
            pass

    return MergeDecision(
        action=result.get("action", "keep_both"),
        merged_rule=merged_rule,
        reasoning=result.get("reasoning", ""),
    )
