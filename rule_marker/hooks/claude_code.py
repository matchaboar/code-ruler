"""Claude Code hook: reads stdin JSON, runs engine, outputs violations."""

from __future__ import annotations

import json
import sys

from rule_marker.linter.engine import LintEngine
from rule_marker.linter.reporter import format_violations


def run_hook(db_path: str, fmt: str = "markdown") -> None:
    """Run the linter as a Claude Code PostToolUse hook.

    Reads edited file path from stdin JSON and outputs violations.
    """
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Extract file path from the hook input
    file_path = None
    tool_input = input_data.get("tool_input", {})
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path") or tool_input.get("path")

    if not file_path:
        return

    engine = LintEngine(db_path=db_path)
    violations = engine.scan([file_path])

    if violations:
        output = format_violations(violations, fmt)
        print(output)
