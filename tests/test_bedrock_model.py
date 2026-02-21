"""Integration test that verifies the default Bedrock model is callable."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_ACCESS_KEY_ID"),
    reason="AWS credentials not configured",
)


def test_default_model_responds():
    """Send a minimal request to Bedrock and verify we get a text response."""
    from code_ruler.llm.client import DEFAULT_MODEL, call_llm, get_client

    client = get_client()
    result = call_llm(
        client,
        system="You are a helpful assistant.",
        user_message="Reply with exactly: ok",
        model=DEFAULT_MODEL,
        max_tokens=16,
    )
    assert isinstance(result, str)
    assert len(result) > 0
