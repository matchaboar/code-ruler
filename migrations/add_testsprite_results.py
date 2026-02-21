"""Migration: Add testsprite_results table.

Usage:
    uv run python migrations/add_testsprite_results.py [path/to/db.sqlite]

If no path is given, defaults to ./code_ruler.db.
"""

from __future__ import annotations

import sqlite3
import sys


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check if table already exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='testsprite_results'")
    if cur.fetchone():
        print("Table testsprite_results already exists — skipping migration.")
        conn.close()
        return

    print(f"Migrating {db_path} ...")

    cur.execute("""
        CREATE TABLE testsprite_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES rules(id),
            repo_url VARCHAR(1024) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            test_plan_json JSON,
            generated_tests TEXT,
            test_results_json JSON,
            diff TEXT,
            error_message TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """)

    cur.execute("CREATE INDEX idx_testsprite_results_rule_id ON testsprite_results(rule_id)")

    conn.commit()
    conn.close()
    print("Migration complete — testsprite_results table created.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "code_ruler.db"
    migrate(path)
