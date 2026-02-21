"""FastAPI app entry point and uvicorn CLI wrapper."""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()
from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from rule_viewer.api.routes import get_db, router  # noqa: E402

app = FastAPI(title="Code Ruler - Rule Viewer", version="0.1.0")
app.include_router(router)

# Serve frontend static files in production with SPA fallback
_frontend_dist = Path(__file__).parent / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.responses import FileResponse

    # Mount static assets first so JS/CSS/images are served directly
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    # SPA catch-all: serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # Serve the actual file if it exists (e.g. favicon.ico)
        file_path = _frontend_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_frontend_dist / "index.html"))


def configure_db(db_path: str) -> None:
    """Configure the database session for the FastAPI app."""
    from rule_viewer.api.pipeline import configure_db_path

    configure_db_path(db_path)

    from sqlalchemy import event

    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # Enable WAL mode so the API can read while pipeline threads write.
    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    # Ensure all tables exist (imports rule + extractor models as a side effect)
    from code_ruler.db.base import init_db

    init_db(engine)

    factory = sessionmaker(bind=engine)

    def _get_db() -> Session:
        session = factory()
        try:
            yield session  # type: ignore[misc]
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db


def _build_frontend() -> None:
    """Build the frontend so the served bundle is always up-to-date."""
    import subprocess

    frontend_dir = Path(__file__).parent / "frontend"
    if not (frontend_dir / "package.json").exists():
        return
    print("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)
    print("Frontend build complete.")


def app_cli(argv: list[str] | None = None) -> None:
    """CLI wrapper for running the rule viewer with uvicorn."""
    parser = argparse.ArgumentParser(
        prog="rule-viewer",
        description="Start the Rule Viewer web UI.",
    )
    parser.add_argument("--db", default="code_ruler.db", help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")

    args = parser.parse_args(argv)

    # Initialize Datadog LLM Observability BEFORE configure_db() so ddtrace
    # patches the anthropic library before any transitive imports load it.
    from code_ruler.llm.client import init_llm_obs

    init_llm_obs()

    configure_db(args.db)

    # Initialize DBOS durable workflows if Postgres URL is configured.
    dbos_pg_url = os.environ.get("DBOS_SYSTEM_DATABASE_URL")
    if dbos_pg_url:
        from dbos import DBOS, DBOSConfig

        from rule_viewer.api.pipeline import mark_dbos_launched

        config: DBOSConfig = {"name": "code-ruler", "system_database_url": dbos_pg_url}
        DBOS(fastapi=app, config=config)
        DBOS.launch()
        mark_dbos_launched()

    # Always rebuild the frontend so the served bundle reflects the latest source.
    _build_frontend()

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    app_cli(sys.argv[1:])
