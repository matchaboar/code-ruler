"""Tests for the GitHub extractor (unit tests with mocked API)."""

from __future__ import annotations

from github_extractor.client import parse_repo_url


def test_parse_https_url():
    """Test parsing a standard HTTPS GitHub URL."""
    owner, name = parse_repo_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert name == "repo"


def test_parse_https_url_trailing_slash():
    """Test parsing URL with trailing slash."""
    owner, name = parse_repo_url("https://github.com/owner/repo/")
    assert owner == "owner"
    assert name == "repo"


def test_parse_git_url():
    """Test parsing .git URL."""
    owner, name = parse_repo_url("https://github.com/owner/repo.git")
    assert owner == "owner"
    assert name == "repo"


def test_parse_short_form():
    """Test parsing owner/name short form."""
    owner, name = parse_repo_url("owner/repo")
    assert owner == "owner"
    assert name == "repo"


def test_parse_invalid_url():
    """Test parsing an invalid URL raises ValueError."""
    import pytest

    with pytest.raises(ValueError):
        parse_repo_url("invalid")
