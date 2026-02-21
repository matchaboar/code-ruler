"""Tests for Datadog LLM Observability initialization and trace capture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import code_ruler.llm.client as client_mod
from code_ruler.llm.client import (
    TraceCollector,
    TraceInfo,
    call_llm,
    init_llm_obs,
    set_trace_collector,
)


class TestInitLlmObs:
    """Tests for init_llm_obs()."""

    @patch.dict("os.environ", {"DD_LLMOBS_ENABLED": "1", "DD_LLMOBS_ML_APP": "test-app", "DD_API_KEY": "fake-key", "DD_SITE": "us5.datadoghq.com"})
    @patch("ddtrace.llmobs.LLMObs")
    def test_enables_agentless_mode(self, mock_llmobs: MagicMock) -> None:
        """LLMObs.enable must be called with agentless_enabled=True and explicit api_key/site."""
        init_llm_obs()
        mock_llmobs.enable.assert_called_once_with(
            ml_app="test-app",
            agentless_enabled=True,
            api_key="fake-key",
            site="us5.datadoghq.com",
        )

    @patch.dict("os.environ", {"DD_LLMOBS_ENABLED": "1"}, clear=False)
    @patch("ddtrace.llmobs.LLMObs")
    def test_default_ml_app_name(self, mock_llmobs: MagicMock) -> None:
        """Falls back to 'code-ruler' when DD_LLMOBS_ML_APP is not set."""
        import os

        os.environ.pop("DD_LLMOBS_ML_APP", None)
        init_llm_obs()
        call_kwargs = mock_llmobs.enable.call_args[1]
        assert call_kwargs["ml_app"] == "code-ruler"
        assert call_kwargs["agentless_enabled"] is True

    @patch.dict("os.environ", {"DD_LLMOBS_ENABLED": "0"})
    @patch("ddtrace.llmobs.LLMObs")
    def test_disabled_when_env_is_zero(self, mock_llmobs: MagicMock) -> None:
        """LLMObs.enable is NOT called when DD_LLMOBS_ENABLED=0."""
        init_llm_obs()
        mock_llmobs.enable.assert_not_called()

    @patch.dict("os.environ", {}, clear=True)
    @patch("ddtrace.llmobs.LLMObs")
    def test_disabled_when_env_missing(self, mock_llmobs: MagicMock) -> None:
        """LLMObs.enable is NOT called when DD_LLMOBS_ENABLED is unset."""
        init_llm_obs()
        mock_llmobs.enable.assert_not_called()

    @patch.dict("os.environ", {"DD_LLMOBS_ENABLED": "1"})
    def test_graceful_when_ddtrace_not_installed(self) -> None:
        """Does not raise when ddtrace is not importable."""
        with patch.dict("sys.modules", {"ddtrace": None, "ddtrace.llmobs": None}):
            # Should not raise
            init_llm_obs()


class TestCallLlmTraceCapture:
    """Tests that call_llm creates LLMObs spans and populates TraceCollector."""

    def _make_mock_client(self, response_text: str = "hello") -> MagicMock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_text)]
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def test_trace_id_populated_when_llmobs_enabled(self) -> None:
        """call_llm must use tracer.trace() to capture a trace_id."""
        mock_span = MagicMock()
        mock_span.trace_id = 123456789
        mock_span.span_id = 987654321

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_span)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_tracer = MagicMock()
        mock_tracer.trace.return_value = mock_ctx

        collector = TraceCollector()
        set_trace_collector(collector)
        old_enabled = client_mod._llmobs_enabled
        client_mod._llmobs_enabled = True

        try:
            with patch.dict("sys.modules", {"ddtrace": MagicMock(tracer=mock_tracer)}):
                result = call_llm(self._make_mock_client(), "sys", "msg")
        finally:
            client_mod._llmobs_enabled = old_enabled
            set_trace_collector(None)

        assert result == "hello"
        assert len(collector.traces) == 1
        assert collector.traces[0].trace_id == "123456789"
        assert collector.traces[0].span_id == "987654321"
        assert collector.traces[0].ok is True
        assert collector.traces[0].error is None

    def test_no_trace_id_when_llmobs_disabled(self) -> None:
        """call_llm must NOT attempt LLMObs spans when disabled."""
        collector = TraceCollector()
        set_trace_collector(collector)
        old_enabled = client_mod._llmobs_enabled
        client_mod._llmobs_enabled = False

        try:
            result = call_llm(self._make_mock_client("world"), "sys", "msg")
        finally:
            client_mod._llmobs_enabled = old_enabled
            set_trace_collector(None)

        assert result == "world"
        assert len(collector.traces) == 1
        assert collector.traces[0].trace_id is None
        assert collector.traces[0].ok is True

    def test_error_captured_in_trace(self) -> None:
        """When the LLM call fails, the trace must record ok=False and the error."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("bedrock timeout")

        collector = TraceCollector()
        set_trace_collector(collector)
        old_enabled = client_mod._llmobs_enabled
        client_mod._llmobs_enabled = False

        try:
            try:
                call_llm(mock_client, "sys", "msg")
            except RuntimeError:
                pass
        finally:
            client_mod._llmobs_enabled = old_enabled
            set_trace_collector(None)

        assert len(collector.traces) == 1
        assert collector.traces[0].ok is False
        assert collector.traces[0].error == "bedrock timeout"

    def test_span_closed_even_on_error(self) -> None:
        """The tracer span context must be exited even when the LLM call raises."""
        mock_span = MagicMock()
        mock_span.trace_id = 111
        mock_span.span_id = 222

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_span)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_tracer = MagicMock()
        mock_tracer.trace.return_value = mock_ctx

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("fail")

        collector = TraceCollector()
        set_trace_collector(collector)
        old_enabled = client_mod._llmobs_enabled
        client_mod._llmobs_enabled = True

        try:
            with patch.dict("sys.modules", {"ddtrace": MagicMock(tracer=mock_tracer)}):
                try:
                    call_llm(mock_client, "sys", "msg")
                except RuntimeError:
                    pass
        finally:
            client_mod._llmobs_enabled = old_enabled
            set_trace_collector(None)

        # Span must be closed
        mock_ctx.__exit__.assert_called_once_with(None, None, None)
        assert collector.traces[0].ok is False
        assert collector.traces[0].trace_id == "111"

    def test_no_collector_does_not_crash(self) -> None:
        """call_llm works fine when no TraceCollector is set."""
        set_trace_collector(None)
        old_enabled = client_mod._llmobs_enabled
        client_mod._llmobs_enabled = False

        try:
            result = call_llm(self._make_mock_client("ok"), "sys", "msg")
        finally:
            client_mod._llmobs_enabled = old_enabled

        assert result == "ok"


class TestTraceCollector:
    """Tests for TraceCollector.to_dicts()."""

    def test_to_dicts_format(self) -> None:
        collector = TraceCollector()
        collector.traces.append(TraceInfo(trace_id="abc", span_id="def", ok=True))
        collector.traces.append(TraceInfo(trace_id=None, span_id=None, ok=False, error="boom"))

        dicts = collector.to_dicts()
        assert dicts == [
            {"trace_id": "abc", "span_id": "def", "ok": True, "error": None},
            {"trace_id": None, "span_id": None, "ok": False, "error": "boom"},
        ]

    def test_empty_collector(self) -> None:
        assert TraceCollector().to_dicts() == []
