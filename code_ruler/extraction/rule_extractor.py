"""Calls Claude API to extract coding rules from review contexts."""

from __future__ import annotations

from anthropic import AnthropicBedrock

from code_ruler.extraction.context_builder import ExtractionContext
from code_ruler.llm.client import call_llm_json
from code_ruler.llm.prompts import RULE_EXTRACTION_SYSTEM, RULE_EXTRACTION_USER
from code_ruler.llm.schemas import CandidateRule


def extract_rules_from_context(
    client: AnthropicBedrock,
    context: ExtractionContext,
    model: str,
) -> list[CandidateRule]:
    """Extract candidate rules from a single review context."""
    user_message = RULE_EXTRACTION_USER.format(
        pr_number=context.pr_number,
        pr_title=context.pr_title,
        repo_name=context.repo_name,
        pr_author=context.pr_author,
        comment_author=context.comment_author,
        file_path=context.file_path,
        comment_body=context.comment_body,
        diff_hunk=context.diff_hunk,
    )

    result = call_llm_json(client, RULE_EXTRACTION_SYSTEM, user_message, model=model)

    rules = []
    items = result if isinstance(result, list) else result.get("rules", [])
    for item in items:
        try:
            rules.append(CandidateRule(**item))
        except Exception as e:
            print(f"  Warning: Failed to parse candidate rule: {e}")

    return rules
