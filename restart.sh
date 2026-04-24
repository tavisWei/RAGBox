#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3003}"

kill_port_processes() {
  local port="$1"
  local pids

  pids="$(lsof -ti tcp:"$port" || true)"
  if [ -z "$pids" ]; then
    echo "==> No process is listening on port $port"
    return
  fi

  echo "==> Stopping processes on port $port: $pids"
  kill $pids 2>/dev/null || true

  for _ in $(seq 1 10); do
    if ! lsof -ti tcp:"$port" >/dev/null 2>&1; then
      echo "==> Port $port is free"
      return
    fi
    sleep 1
  done

  pids="$(lsof -ti tcp:"$port" || true)"
  if [ -n "$pids" ]; then
    echo "==> Force killing remaining processes on port $port: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

cd "$ROOT_DIR"

echo "==> Restarting RAGBox"
kill_port_processes "$API_PORT"
kill_port_processes "$WEB_PORT"

echo "==> Starting services again"
exec "$ROOT_DIR/start.sh"
