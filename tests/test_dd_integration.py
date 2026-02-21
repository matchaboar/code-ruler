"""Integration test: verify Datadog LLM Observability traces are sent with content.

Requires real credentials (DD_API_KEY, AWS keys). Skipped in CI when not configured.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

requires_dd = pytest.mark.skipif(
    not (os.environ.get("DD_LLMOBS_ENABLED") == "1" and os.environ.get("DD_API_KEY")),
    reason="DD_LLMOBS_ENABLED=1 and DD_API_KEY required",
)

requires_bedrock = pytest.mark.skipif(
    not os.environ.get("AWS_ACCESS_KEY_ID"),
    reason="AWS credentials required",
)


@requires_dd
@requires_bedrock
def test_llm_call_produces_trace_with_content() -> None:
    """A real LLM call must produce a trace with a non-empty trace_id."""
    from code_ruler.llm.client import (
        TraceCollector,
        call_llm,
        get_client,
        init_llm_obs,
        set_trace_collector,
    )

    init_llm_obs()

    collector = TraceCollector()
    set_trace_collector(collector)

    try:
        client = get_client()
        result = call_llm(
            client,
            "You are a test assistant.",
            "Reply with exactly: TEST_OK",
            max_tokens=16,
        )
    finally:
        set_trace_collector(None)

    # LLM responded
    assert "TEST_OK" in result

    # Trace was captured with a real trace_id
    assert len(collector.traces) == 1
    trace = collector.traces[0]
    assert trace.ok is True
    assert trace.trace_id is not None
    assert len(trace.trace_id) > 0
    assert trace.span_id is not None

    # Flush traces to Datadog
    from ddtrace.llmobs import LLMObs

    LLMObs.flush()


@requires_dd
@requires_bedrock
def test_pipeline_single_review_produces_dd_traces() -> None:
    """Running the pipeline on 1 review comment must emit dd_traces in the callback."""
    from code_ruler.db.base import get_engine, get_session_factory, init_db
    from code_ruler.llm.client import get_client, init_llm_obs
    from code_ruler.llm.client import DEFAULT_MODEL
    from code_ruler.pipeline import run_pipeline

    init_llm_obs()

    db_path = "code_ruler.db"
    engine = get_engine(db_path)
    init_db(engine)
    factory = get_session_factory(engine)

    captured_events: list[dict] = []

    def on_review(event_type: str, **data) -> None:
        captured_events.append({"type": event_type, **data})

    client = get_client()
    with factory() as session:
        run_pipeline(
            client, session, DEFAULT_MODEL,
            limit=1, dry_run=True, on_review=on_review,
        )

    # Should have at least review_start + review_done
    done_events = [e for e in captured_events if e["type"] == "review_done"]
    assert len(done_events) >= 1, f"Expected review_done event, got: {captured_events}"

    # The review_done event must include dd_traces with real trace_ids
    dd_traces = done_events[0].get("dd_traces", [])
    assert len(dd_traces) >= 1, f"Expected at least 1 DD trace, got: {dd_traces}"
    assert dd_traces[0]["ok"] is True
    assert dd_traces[0]["trace_id"] is not None, "trace_id is None — DD tracing not working"
    assert len(dd_traces[0]["trace_id"]) > 0

    # Flush
    from ddtrace.llmobs import LLMObs
    LLMObs.flush()
