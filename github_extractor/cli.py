"""CLI entry point for GitHub extractor."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from github_extractor.client import create_github_client
from github_extractor.database import get_engine, get_session_factory, init_db
from github_extractor.extractor import extract_repo


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="github-extractor",
        description="Extract merged PR review data from GitHub repos into SQLite.",
    )
    parser.add_argument("repo_url", help="GitHub repository URL (e.g. https://github.com/owner/repo)")
    parser.add_argument("--db", default="code_ruler.db", help="SQLite database path (default: code_ruler.db)")
    parser.add_argument("--token", default=None, help="GitHub PAT (default: GITHUB_TOKEN env var)")
    parser.add_argument("--limit", type=int, default=None, help="Max number of merged PRs to extract")

    args = parser.parse_args(argv)

    engine = get_engine(args.db)
    init_db(engine)
    session_factory = get_session_factory(engine)

    client = create_github_client(args.token)

    print(f"Extracting PRs from {args.repo_url}...")
    with session_factory() as session:
        extract_repo(client, args.repo_url, session, limit=args.limit)


if __name__ == "__main__":
    main(sys.argv[1:])
