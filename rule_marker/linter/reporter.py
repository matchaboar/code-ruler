"""Formats violations for output (console/JSON/markdown)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rule_marker.linter.violations import Violation


def format_console(violations: list[Violation]) -> str:
    """Format violations in ruff-style console output."""
    lines = []
    for v in violations:
        lines.append(f"{v.file}:{v.line}:{v.column}: {v.rule_slug}: {v.message}")
    return "\n".join(lines)


def format_json(violations: list[Violation]) -> str:
    """Format violations as JSON."""
    data = [
        {
            "file": v.file,
            "line": v.line,
            "column": v.column,
            "rule_slug": v.rule_slug,
            "severity": v.severity,
            "message": v.message,
            "suggestion": v.suggestion,
        }
        for v in violations
    ]
    return json.dumps(data, indent=2)


def format_markdown(violations: list[Violation]) -> str:
    """Format violations as markdown for LLM hooks."""
    if not violations:
        return ""

    lines = ["## Rule Marker Violations\n"]
    for v in violations:
        severity_icon = {"error": "x", "warning": "!", "info": "i"}.get(v.severity, "?")
        lines.append(f"- **[{severity_icon}] {v.rule_slug}** `{v.file}:{v.line}:{v.column}`")
        lines.append(f"  {v.message}")
        if v.suggestion:
            lines.append(f"  *Suggestion:* {v.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_violations(violations: list[Violation], fmt: str = "console") -> str:
    """Format violations in the specified format."""
    formatters = {
        "console": format_console,
        "json": format_json,
        "markdown": format_markdown,
    }
    formatter = formatters.get(fmt, format_console)
    return formatter(violations)
