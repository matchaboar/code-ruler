"""AnthropicBedrock client wrapper with Datadog LLM Observability."""

from __future__ import annotations

import json
import os

from anthropic import AnthropicBedrock

DEFAULT_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def init_llm_obs() -> None:
    """Initialize Datadog LLM Observability if configured."""
    if os.environ.get("DD_LLMOBS_ENABLED") == "1":
        try:
            from ddtrace.llmobs import LLMObs

            LLMObs.enable(
                ml_app=os.environ.get("DD_LLMOBS_ML_APP", "code-ruler"),
                agentless_enabled=True,
            )
        except ImportError:
            pass


def get_client() -> AnthropicBedrock:
    """Create an AnthropicBedrock client."""
    return AnthropicBedrock(
        aws_region=os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-west-2")),
        aws_access_key=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )


def call_llm(
    client: AnthropicBedrock,
    system: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> str:
    """Call Claude via Bedrock and return the text response."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def call_llm_json(
    client: AnthropicBedrock,
    system: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
) -> dict | list:
    """Call Claude via Bedrock and parse the JSON response."""
    import re

    text = call_llm(client, system, user_message, model, max_tokens)

    # Extract JSON from markdown code blocks first
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        # Try to find raw JSON array or object
        text = text.strip()
        match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)

    return json.loads(text)
