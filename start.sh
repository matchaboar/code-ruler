#!/usr/bin/env bash
set -euo pipefail

CHECK=false
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=true ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Start Postgres (if not already running) ──
if podman ps --format '{{.Names}}' | grep -q '^code-ruler-postgres$'; then
  echo "Postgres already running."
else
  echo "Starting Postgres..."
  podman run -d \
    --name code-ruler-postgres \
    --replace \
    -e POSTGRES_USER=dbos \
    -e POSTGRES_PASSWORD=dbos \
    -e POSTGRES_DB=code_ruler_dbos \
    -p 5432:5432 \
    docker.io/library/postgres:16-alpine
  # Wait for Postgres to be ready
  echo -n "Waiting for Postgres..."
  for i in $(seq 1 30); do
    if podman exec code-ruler-postgres pg_isready -U dbos -q 2>/dev/null; then
      echo " ready."
      break
    fi
    echo -n "."
    sleep 1
  done
fi

# ── 2. Install Python dependencies ──
echo "Syncing Python dependencies..."
uv sync

# ── 3. Install & build frontend ──
echo "Building frontend..."
(cd rule_viewer/frontend && npm install --silent && npm run build)

# ── 4. Lint & test (if --check) ──
if [ "$CHECK" = true ]; then
  echo "Running linter..."
  uv run ruff check .
  echo "Running unit tests..."
  uv run pytest
  echo "All checks passed."
fi

# ── 5. Kill any existing process on port 8000 ──
if pid=$(lsof -ti tcp:8000 2>/dev/null); then
  echo "Killing existing process on port 8000 (PID: $pid)..."
  kill $pid 2>/dev/null || true
  sleep 1
fi

# ── 6. Launch the app ──
echo ""
echo "Starting Code Ruler at http://127.0.0.1:8000"
echo ""
uv run rule-viewer
