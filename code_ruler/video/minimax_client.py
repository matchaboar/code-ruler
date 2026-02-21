"""Minimax Image-to-Video API client."""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass

import httpx

_BASE_URL = "https://api.minimax.io"


@dataclass
class VideoResult:
    """Result of a video generation request."""

    task_id: str
    status: str  # "Success", "Fail", "Processing", "Queueing"
    file_id: str | None = None
    download_url: str | None = None
    error: str | None = None


def get_api_key() -> str:
    """Read the Minimax API key from the environment."""
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise RuntimeError("MINIMAX_API_KEY environment variable is not set")
    return key


def submit_image_to_video(
    image_bytes: bytes,
    prompt: str,
    model: str = "I2V-01",
) -> str:
    """Submit an image-to-video generation task.

    Returns the task_id for polling.
    """
    api_key = get_api_key()
    b64_image = base64.b64encode(image_bytes).decode("ascii")

    payload = {
        "model": model,
        "first_frame_image": f"data:image/png;base64,{b64_image}",
        "prompt": prompt,
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{_BASE_URL}/v1/video_generation",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    task_id = data.get("task_id", "")
    if not task_id:
        raise RuntimeError(f"No task_id in Minimax response: {data}")
    return task_id


def poll_video_status(
    task_id: str,
    poll_interval: int = 10,
    max_poll_time: int = 300,
) -> VideoResult:
    """Poll until the video task completes or times out."""
    api_key = get_api_key()
    start = time.monotonic()

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= max_poll_time:
            return VideoResult(task_id=task_id, status="Fail", error="Polling timed out")

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{_BASE_URL}/v1/query/video_generation",
                params={"task_id": task_id},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "")
        if status == "Success":
            file_id = data.get("file_id", "")
            download_url = None
            if file_id:
                download_url = get_video_download_url(file_id)
            return VideoResult(
                task_id=task_id,
                status="Success",
                file_id=file_id,
                download_url=download_url,
            )
        elif status == "Fail":
            return VideoResult(
                task_id=task_id,
                status="Fail",
                error=data.get("error", "Unknown error"),
            )

        time.sleep(poll_interval)


def get_video_download_url(file_id: str) -> str:
    """Retrieve the download URL for a completed video file."""
    api_key = get_api_key()

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{_BASE_URL}/v1/files/retrieve",
            params={"file_id": file_id},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    url = data.get("file", {}).get("download_url", "")
    if not url:
        raise RuntimeError(f"No download_url in Minimax file response: {data}")
    return url


def generate_video_from_image(
    image_bytes: bytes,
    prompt: str,
    model: str = "I2V-01",
    poll_interval: int = 10,
    max_poll_time: int = 300,
) -> VideoResult:
    """End-to-end: submit image, poll until done, return result."""
    task_id = submit_image_to_video(image_bytes, prompt, model=model)
    return poll_video_status(task_id, poll_interval=poll_interval, max_poll_time=max_poll_time)
