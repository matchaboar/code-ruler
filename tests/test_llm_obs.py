"""Tests for Datadog LLM Observability initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from code_ruler.llm.client import init_llm_obs


class TestInitLlmObs:
    """Tests for init_llm_obs()."""

    @patch.dict("os.environ", {"DD_LLMOBS_ENABLED": "1", "DD_LLMOBS_ML_APP": "test-app"})
    @patch("ddtrace.llmobs.LLMObs")
    def test_enables_agentless_mode(self, mock_llmobs: MagicMock) -> None:
        """LLMObs.enable must be called with agentless_enabled=True."""
        init_llm_obs()
        mock_llmobs.enable.assert_called_once_with(
            ml_app="test-app",
            agentless_enabled=True,
        )

    @patch.dict("os.environ", {"DD_LLMOBS_ENABLED": "1"}, clear=False)
    @patch("ddtrace.llmobs.LLMObs")
    def test_default_ml_app_name(self, mock_llmobs: MagicMock) -> None:
        """Falls back to 'code-ruler' when DD_LLMOBS_ML_APP is not set."""
        import os

        os.environ.pop("DD_LLMOBS_ML_APP", None)
        init_llm_obs()
        mock_llmobs.enable.assert_called_once_with(
            ml_app="code-ruler",
            agentless_enabled=True,
        )

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
