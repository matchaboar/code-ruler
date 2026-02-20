"""Violation dataclass used across linter modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Violation:
    """A single linter violation."""

    file: str
    line: int
    column: int
    rule_slug: str
    severity: str
    message: str
    suggestion: str | None = None
