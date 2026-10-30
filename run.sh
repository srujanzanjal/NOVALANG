#!/usr/bin/env bash
# Launch the playground backend (FastAPI/uvicorn) and frontend (Vite) together.
# Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

cleanup() {
  echo ""
  echo "Shutting down..."
  # Kill the whole process group of each child.
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# backend
echo "Starting backend (uvicorn) ..."
source .venv/bin/activate
uvicorn playground.backend.main:app --reload &
BACKEND_PID=$!

# frontend
echo "Starting frontend (vite) ..."
(cd playground/frontend && npm run dev) &
FRONTEND_PID=$!

echo "Backend PID $BACKEND_PID, frontend PID $FRONTEND_PID. Press Ctrl-C to stop both."
wait
