"""CLI entry point for Code Ruler rule extraction."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from code_ruler.db.base import get_engine, get_session_factory, init_db  # noqa: E402
from code_ruler.llm.client import DEFAULT_MODEL, get_client, init_llm_obs  # noqa: E402
from code_ruler.pipeline import run_pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="code-ruler",
        description="Extract coding rules from PR review data using Claude.",
    )
    parser.add_argument("command", choices=["extract-rules"], help="Command to run")
    parser.add_argument("--db", default="code_ruler.db", help="SQLite database path")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Bedrock model ID")
    parser.add_argument("--limit", type=int, default=None, help="Max review comments to process")
    parser.add_argument("--dry-run", action="store_true", help="Extract rules without storing")

    args = parser.parse_args(argv)

    if args.command == "extract-rules":
        init_llm_obs()
        engine = get_engine(args.db)
        init_db(engine)
        session_factory = get_session_factory(engine)

        client = get_client()

        with session_factory() as session:
            candidates = run_pipeline(
                client, session, args.model, limit=args.limit, dry_run=args.dry_run
            )

        if args.dry_run:
            print(f"\n--- Dry run complete. {len(candidates)} candidate rules found. ---")
            for c in candidates:
                print(f"  [{c.severity}] {c.slug}: {c.title}")
        else:
            print(f"\n--- Done. {len(candidates)} rules processed. ---")


if __name__ == "__main__":
    main(sys.argv[1:])
