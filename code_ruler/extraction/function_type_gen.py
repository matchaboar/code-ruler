"""Generates decorator + linter source for function type rules."""

from __future__ import annotations

from anthropic import AnthropicBedrock

from code_ruler.llm.client import call_llm_json
from code_ruler.llm.prompts import FUNCTION_TYPE_SYSTEM, FUNCTION_TYPE_USER
from code_ruler.llm.schemas import CandidateRule, FunctionTypeSpec


def generate_function_type(
    client: AnthropicBedrock,
    rule: CandidateRule,
    model: str,
) -> FunctionTypeSpec | None:
    """Generate decorator and linter source for a function_type rule."""
    user_message = FUNCTION_TYPE_USER.format(
        title=rule.title,
        description=rule.description,
        constraints=rule.rationale,
        positive_example=rule.positive_example or "# No example provided",
        negative_example=rule.negative_example or "# No example provided",
    )

    result = call_llm_json(client, FUNCTION_TYPE_SYSTEM, user_message, model=model)

    spec = FunctionTypeSpec(**result)

    # Validate generated code compiles
    try:
        compile(spec.decorator_source, "<decorator>", "exec")
        compile(spec.linter_source, "<linter>", "exec")
    except SyntaxError as e:
        print(f"  Warning: Generated code has syntax error: {e}")
        return None

    return spec
