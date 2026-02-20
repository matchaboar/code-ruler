"""CLI entry point for Rule Marker linter."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from rule_marker.linter.engine import LintEngine
from rule_marker.linter.reporter import format_violations


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rule-marker",
        description="AST-based linter with decorator markers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan files for violations")
    scan_parser.add_argument("paths", nargs="+", help="Files or directories to scan")
    scan_parser.add_argument(
        "--format",
        choices=["console", "json", "markdown"],
        default="console",
        help="Output format",
    )
    scan_parser.add_argument("--db", default=None, help="SQLite database path for dynamic rules")

    # hook command
    hook_parser = subparsers.add_parser("hook", help="Run as Claude Code hook")
    hook_parser.add_argument(
        "--format",
        choices=["console", "json", "markdown"],
        default="markdown",
        help="Output format",
    )
    hook_parser.add_argument("--db", default=None, help="SQLite database path for dynamic rules")

    args = parser.parse_args(argv)

    if args.command == "scan":
        engine = LintEngine(db_path=args.db)
        violations = engine.scan(args.paths)
        if violations:
            output = format_violations(violations, args.format)
            print(output)
            sys.exit(1)
        else:
            print("No violations found.")

    elif args.command == "hook":
        from rule_marker.hooks.claude_code import run_hook

        run_hook(db_path=args.db, fmt=args.format)


if __name__ == "__main__":
    main(sys.argv[1:])
