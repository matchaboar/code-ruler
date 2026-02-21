"""Orchestrator: render rule image then generate video via Minimax."""

from __future__ import annotations

from typing import TYPE_CHECKING

from code_ruler.video.image_renderer import render_rule_image
from code_ruler.video.minimax_client import VideoResult, generate_video_from_image

if TYPE_CHECKING:
    from code_ruler.llm.schemas import CandidateRule

_DEFAULT_PROMPT = (
    "Abstract visualization: the top half dissolves into fractured, glitching red shards "
    "that scatter and fade, while the bottom half radiates calm green energy that expands "
    "outward in smooth, flowing ripples of light — chaos transforming into harmony"
)


def generate_rule_video(
    rule: CandidateRule,
    prompt: str | None = None,
) -> VideoResult:
    """Render a rule as an image and animate it via Minimax I2V.

    Args:
        rule: The candidate rule to visualize.
        prompt: Optional animation prompt. Uses a default cinematic prompt if not provided.

    Returns:
        VideoResult with task_id, status, file_id, download_url, and error fields.
    """
    image_bytes = render_rule_image(rule)
    return generate_video_from_image(image_bytes, prompt or _DEFAULT_PROMPT)
