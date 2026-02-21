"""Tests for the video generation pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from code_ruler.llm.schemas import CandidateRule
from code_ruler.video.image_renderer import render_rule_image
from code_ruler.video.minimax_client import VideoResult


def _make_rule(**overrides) -> CandidateRule:
    defaults = dict(
        slug="test-rule",
        category="best_practice",
        severity="warning",
        title="Use context managers for files",
        description="Always use `with` when opening files.",
        positive_example='with open("f.txt") as f:\n    data = f.read()',
        negative_example='f = open("f.txt")\ndata = f.read()\nf.close()',
        rationale="Prevents resource leaks.",
    )
    defaults.update(overrides)
    return CandidateRule(**defaults)


# ---------------------------------------------------------------------------
# Image Renderer
# ---------------------------------------------------------------------------


class TestImageRenderer:
    def test_returns_png_bytes(self):
        rule = _make_rule()
        result = render_rule_image(rule)
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_custom_dimensions(self):
        from PIL import Image
        import io

        rule = _make_rule()
        result = render_rule_image(rule, width=800, height=600)
        img = Image.open(io.BytesIO(result))
        assert img.size == (800, 600)

    def test_missing_examples(self):
        rule = _make_rule(positive_example=None, negative_example=None)
        result = render_rule_image(rule)
        assert isinstance(result, bytes)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Minimax Client
# ---------------------------------------------------------------------------


class TestMinimaxClient:
    @patch("code_ruler.video.minimax_client.httpx.Client")
    @patch("code_ruler.video.minimax_client.get_api_key", return_value="test-key")
    def test_submit_image_to_video(self, _mock_key, mock_client_cls):
        from code_ruler.video.minimax_client import submit_image_to_video

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"task_id": "task-123"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        task_id = submit_image_to_video(b"fake-png", "animate this")
        assert task_id == "task-123"

    @patch("code_ruler.video.minimax_client.get_video_download_url", return_value="https://example.com/video.mp4")
    @patch("code_ruler.video.minimax_client.httpx.Client")
    @patch("code_ruler.video.minimax_client.get_api_key", return_value="test-key")
    def test_poll_video_status_success(self, _mock_key, mock_client_cls, _mock_dl):
        from code_ruler.video.minimax_client import poll_video_status

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "Success", "file_id": "file-456"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = poll_video_status("task-123", poll_interval=0, max_poll_time=5)
        assert result.status == "Success"
        assert result.file_id == "file-456"
        assert result.download_url == "https://example.com/video.mp4"

    @patch("code_ruler.video.minimax_client.httpx.Client")
    @patch("code_ruler.video.minimax_client.get_api_key", return_value="test-key")
    def test_poll_video_status_fail(self, _mock_key, mock_client_cls):
        from code_ruler.video.minimax_client import poll_video_status

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "Fail", "error": "Bad input"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = poll_video_status("task-123", poll_interval=0, max_poll_time=5)
        assert result.status == "Fail"
        assert result.error == "Bad input"

    @patch("code_ruler.video.minimax_client.httpx.Client")
    @patch("code_ruler.video.minimax_client.get_api_key", return_value="test-key")
    def test_get_video_download_url(self, _mock_key, mock_client_cls):
        from code_ruler.video.minimax_client import get_video_download_url

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "file": {"download_url": "https://cdn.example.com/v.mp4"}
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        url = get_video_download_url("file-456")
        assert url == "https://cdn.example.com/v.mp4"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class TestGenerator:
    @patch("code_ruler.video.generator.generate_video_from_image")
    @patch("code_ruler.video.generator.render_rule_image")
    def test_generate_rule_video(self, mock_render, mock_gen_video):
        from code_ruler.video.generator import generate_rule_video

        mock_render.return_value = b"fake-png"
        mock_gen_video.return_value = VideoResult(
            task_id="t-1", status="Success", file_id="f-1", download_url="https://example.com/v.mp4"
        )

        rule = _make_rule()
        result = generate_rule_video(rule)

        mock_render.assert_called_once_with(rule)
        mock_gen_video.assert_called_once()
        assert result.status == "Success"
        assert result.task_id == "t-1"

    @patch("code_ruler.video.generator.generate_video_from_image")
    @patch("code_ruler.video.generator.render_rule_image")
    def test_custom_prompt(self, mock_render, mock_gen_video):
        from code_ruler.video.generator import generate_rule_video

        mock_render.return_value = b"fake-png"
        mock_gen_video.return_value = VideoResult(task_id="t-2", status="Success")

        rule = _make_rule()
        generate_rule_video(rule, prompt="zoom in slowly")

        call_args = mock_gen_video.call_args
        assert call_args[0][1] == "zoom in slowly"
