"""Migration: Add repo_id column to rules table and scope uniqueness to (slug, repo_id).

Usage:
    uv run python migrations/add_rule_repo_id.py [path/to/db.sqlite]

If no path is given, defaults to ./code_ruler.db.
"""

from __future__ import annotations

import sqlite3
import sys


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check if repo_id column already exists
    cols = [row[1] for row in cur.execute("PRAGMA table_info(rules)")]
    if "repo_id" in cols:
        print("Column repo_id already exists on rules — skipping migration.")
        conn.close()
        return

    print(f"Migrating {db_path} ...")

    # Step 1: Add repo_id as nullable
    cur.execute("ALTER TABLE rules ADD COLUMN repo_id INTEGER")

    # Step 2: Populate from provenance -> pull_requests -> repositories
    cur.execute("""
        UPDATE rules
        SET repo_id = (
            SELECT pr.repo_id
            FROM rule_provenance rp
            JOIN pull_requests pr ON rp.pull_request_id = pr.id
            WHERE rp.rule_id = rules.id
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM rule_provenance rp
            JOIN pull_requests pr ON rp.pull_request_id = pr.id
            WHERE rp.rule_id = rules.id
        )
    """)

    # Step 3: For rules with no provenance, assign to the first available repo
    cur.execute("SELECT id FROM repositories ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if row:
        fallback_repo_id = row[0]
        cur.execute(
            "UPDATE rules SET repo_id = ? WHERE repo_id IS NULL",
            (fallback_repo_id,),
        )
    else:
        # No repos at all — check if there are orphan rules
        cur.execute("SELECT COUNT(*) FROM rules WHERE repo_id IS NULL")
        orphan_count = cur.fetchone()[0]
        if orphan_count > 0:
            print(f"WARNING: {orphan_count} rules have no repo_id and no repositories exist.")
            print("Creating a placeholder repository...")
            cur.execute(
                "INSERT INTO repositories (owner, name, full_name, html_url, default_branch) "
                "VALUES ('unknown', 'unknown', 'unknown/unknown', '', 'main')"
            )
            fallback_repo_id = cur.lastrowid
            cur.execute(
                "UPDATE rules SET repo_id = ? WHERE repo_id IS NULL",
                (fallback_repo_id,),
            )

    # Step 4: Verify no NULLs remain
    cur.execute("SELECT COUNT(*) FROM rules WHERE repo_id IS NULL")
    null_count = cur.fetchone()[0]
    if null_count > 0:
        conn.rollback()
        conn.close()
        raise RuntimeError(f"{null_count} rules still have NULL repo_id — aborting")

    # Step 5: Drop old unique index on slug, add new unique constraint on (slug, repo_id)
    # SQLite doesn't support DROP CONSTRAINT, so we drop the index if it exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='rules'")
    indexes = [row[0] for row in cur.fetchall()]
    for idx_name in indexes:
        # Drop auto-generated unique index on slug
        if "slug" in idx_name.lower():
            cur.execute(f"DROP INDEX IF EXISTS [{idx_name}]")
            print(f"  Dropped index: {idx_name}")

    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rule_slug_repo ON rules (slug, repo_id)"
    )
    print("  Created unique index: uq_rule_slug_repo(slug, repo_id)")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "code_ruler.db"
    migrate(path)
