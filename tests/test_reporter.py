"""Tests for violation reporters."""

from __future__ import annotations

import json

from rule_marker.linter.violations import Violation
from rule_marker.linter.reporter import format_console, format_json, format_markdown


def _make_violation() -> Violation:
    return Violation(
        file="handlers.py",
        line=15,
        column=5,
        rule_slug="pure-function",
        severity="warning",
        message="pure_function must not call 'print'",
        suggestion="Remove the print statement",
    )


def test_format_console():
    """Test console format output."""
    v = _make_violation()
    output = format_console([v])
    assert "handlers.py:15:5" in output
    assert "pure-function" in output
    assert "print" in output


def test_format_json():
    """Test JSON format output."""
    v = _make_violation()
    output = format_json([v])
    data = json.loads(output)
    assert len(data) == 1
    assert data[0]["file"] == "handlers.py"
    assert data[0]["line"] == 15
    assert data[0]["rule_slug"] == "pure-function"


def test_format_markdown():
    """Test markdown format output."""
    v = _make_violation()
    output = format_markdown([v])
    assert "## Rule Marker Violations" in output
    assert "pure-function" in output
    assert "handlers.py:15:5" in output


def test_format_empty():
    """Test formatting with no violations."""
    assert format_console([]) == ""
    assert format_json([]) == "[]"
    assert format_markdown([]) == ""
