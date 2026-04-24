#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3003}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CURL_NO_PROXY="${CURL_NO_PROXY:-localhost,127.0.0.1}"

cd "$ROOT_DIR"
mkdir -p api/data
touch api/data/.gitkeep

if [ -d "$ROOT_DIR/.venv" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERROR] Python not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm is required to start the frontend" >&2
  exit 1
fi

cleanup() {
  if [ -n "${API_PID:-}" ]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [ -n "${WEB_PID:-}" ]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}

trap 'cleanup' EXIT INT TERM

echo "==> Starting backend on http://localhost:$API_PORT"
PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON_BIN" -m uvicorn api.main:app --host 0.0.0.0 --port "$API_PORT" &
API_PID=$!

for _ in $(seq 1 30); do
  if curl --noproxy "$CURL_NO_PROXY" -fsS "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl --noproxy "$CURL_NO_PROXY" -fsS "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
  echo "[ERROR] Backend failed to become healthy" >&2
  exit 1
fi

echo "==> Starting frontend on http://localhost:$WEB_PORT"
npm --prefix "$ROOT_DIR/web-vue" run dev -- --host 0.0.0.0 --port "$WEB_PORT" &
WEB_PID=$!

for _ in $(seq 1 30); do
  if curl --noproxy "$CURL_NO_PROXY" -fsS "http://localhost:$WEB_PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl --noproxy "$CURL_NO_PROXY" -fsS "http://localhost:$WEB_PORT" >/dev/null 2>&1; then
  echo "[ERROR] Frontend failed to become ready" >&2
  exit 1
fi

cat <<EOF

RAG Platform is running.

Frontend:  http://localhost:$WEB_PORT
Backend:   http://localhost:$API_PORT
Health:    http://localhost:$API_PORT/api/v1/health

Default admin account:
  Email:    admin@example.com
  Password: admin

Local runtime data is stored under api/data/ and is ignored by git.
Press Ctrl+C to stop both processes.

EOF

wait
