"""AnthropicBedrock client wrapper with Datadog LLM Observability."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from anthropic import AnthropicBedrock

DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

_llmobs_enabled = False


@dataclass
class TraceInfo:
    """Metadata about a Datadog trace for a single LLM call."""

    trace_id: str | None = None
    span_id: str | None = None
    ok: bool = True
    error: str | None = None


@dataclass
class TraceCollector:
    """Collects TraceInfo entries across multiple LLM calls in a pipeline step."""

    traces: list[TraceInfo] = field(default_factory=list)

    def to_dicts(self) -> list[dict]:
        return [
            {"trace_id": t.trace_id, "span_id": t.span_id, "ok": t.ok, "error": t.error}
            for t in self.traces
        ]


# Thread-local current collector – set by pipeline code for the duration of a step.
_current_collector: TraceCollector | None = None


def set_trace_collector(collector: TraceCollector | None) -> None:
    global _current_collector
    _current_collector = collector


def get_trace_collector() -> TraceCollector | None:
    return _current_collector


def init_llm_obs() -> None:
    """Initialize Datadog LLM Observability if configured."""
    global _llmobs_enabled
    if os.environ.get("DD_LLMOBS_ENABLED") == "1":
        try:
            from ddtrace.llmobs import LLMObs

            LLMObs.enable(
                ml_app=os.environ.get("DD_LLMOBS_ML_APP", "code-ruler"),
                agentless_enabled=True,
                api_key=os.environ.get("DD_API_KEY"),
                site=os.environ.get("DD_SITE", "datadoghq.com"),
            )
            _llmobs_enabled = True
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
    """Call Claude via Bedrock and return the text response.

    When DD_TRACE_ENABLED=1, ddtrace auto-instruments ``client.messages.create``
    and produces an ``anthropic.request`` LLM span with full input/output
    content.  We open a lightweight ``tracer.trace()`` parent so we can capture
    the ``trace_id`` for the UI without creating a duplicate LLM span in the
    Datadog LLMObs console.
    """
    trace = TraceInfo()
    span_ctx = None

    if _llmobs_enabled:
        try:
            from ddtrace import tracer

            span_ctx = tracer.trace("code_ruler.call_llm", service="code-ruler")
            span = span_ctx.__enter__()
            trace.trace_id = str(span.trace_id)
            trace.span_id = str(span.span_id)
        except Exception:
            span_ctx = None

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        trace.ok = False
        trace.error = str(e)
        raise
    finally:
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception:
                pass
        if _current_collector is not None:
            _current_collector.traces.append(trace)


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
