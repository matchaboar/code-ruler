"""PyGithub wrapper with rate-limit-aware retry."""

from __future__ import annotations

import os
import time

from github import Github
from github.Repository import Repository


def create_github_client(token: str | None = None) -> Github:
    """Create a PyGithub client using the provided token or GITHUB_TOKEN env var."""
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "GitHub token required. Set GITHUB_TOKEN env var or pass --token."
        )
    return Github(token, per_page=100)


def get_repo(client: Github, owner: str, name: str) -> Repository:
    """Get a repository by owner/name."""
    return client.get_repo(f"{owner}/{name}")


def check_rate_limit(client: Github, min_remaining: int = 50) -> None:
    """Sleep if API rate limit remaining is below threshold."""
    rate = client.get_rate_limit().core
    if rate.remaining < min_remaining:
        reset_time = rate.reset.timestamp()
        sleep_seconds = max(reset_time - time.time(), 0) + 1
        print(f"Rate limit low ({rate.remaining} remaining). Sleeping {sleep_seconds:.0f}s...")
        time.sleep(sleep_seconds)


def parse_repo_url(url: str) -> tuple[str, str]:
    """Parse a GitHub repo URL into (owner, name).

    Accepts formats:
        https://github.com/owner/name
        https://github.com/owner/name.git
        owner/name
    """
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    if "github.com" in url:
        parts = url.split("github.com/")[-1].split("/")
    else:
        parts = url.split("/")

    if len(parts) < 2:
        raise ValueError(f"Cannot parse repo URL: {url}")

    return parts[0], parts[1]
