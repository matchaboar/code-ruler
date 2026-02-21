#!/usr/bin/env python3
"""Generate an animated video from a code rule via Minimax I2V.

Renders the rule as a styled PNG, submits it to Minimax, polls until done,
and downloads the result.

Usage:
    uv run scripts/generate_video.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from code_ruler.llm.schemas import CandidateRule
from code_ruler.video.generator import generate_rule_video
from code_ruler.video.image_renderer import render_rule_image

load_dotenv()

OUT_DIR = Path("output")

rule = CandidateRule(
    slug="use-context-managers",
    category="best_practice",
    severity="warning",
    title="Use context managers for file handling",
    description="Always use with-statements when opening files.",
    negative_example='f = open("data.txt")\ndata = f.read()\nf.close()',
    positive_example='with open("data.txt") as f:\n    data = f.read()',
    rationale="Prevents resource leaks if exceptions occur.",
)

OUT_DIR.mkdir(exist_ok=True)

# Save the first-frame image
image_bytes = render_rule_image(rule)
image_path = OUT_DIR / "rule_preview.png"
image_path.write_bytes(image_bytes)
print(f"Image saved to {image_path}")

# Generate video
print("Submitting to Minimax I2V (this may take a few minutes)...")
result = generate_rule_video(rule)

print(f"Status: {result.status}")
if result.error:
    print(f"Error: {result.error}")
    raise SystemExit(1)

# Download the video
if result.download_url:
    import httpx

    video_path = OUT_DIR / "rule_video.mp4"
    with httpx.stream("GET", result.download_url) as resp:
        resp.raise_for_status()
        with open(video_path, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    print(f"Video saved to {video_path}")
