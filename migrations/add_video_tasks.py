"""Migration: Add video_tasks table.

Usage:
    uv run python migrations/add_video_tasks.py [path/to/db.sqlite]

If no path is given, defaults to ./code_ruler.db.
"""

from __future__ import annotations

import sqlite3
import sys


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check if table already exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='video_tasks'")
    if cur.fetchone():
        print("Table video_tasks already exists — skipping migration.")
        conn.close()
        return

    print(f"Migrating {db_path} ...")

    cur.execute("""
        CREATE TABLE video_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL REFERENCES rules(id),
            task_id VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'Processing',
            file_id VARCHAR(255),
            download_url TEXT,
            prompt TEXT,
            error TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """)

    cur.execute("CREATE INDEX idx_video_tasks_rule_id ON video_tasks(rule_id)")

    conn.commit()
    conn.close()
    print("Migration complete — video_tasks table created.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "code_ruler.db"
    migrate(path)
