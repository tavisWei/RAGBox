#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_CACHE_DIR="${NPM_CACHE_DIR:-$ROOT_DIR/.npm-cache}"

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERROR] Python not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm is required to build the frontend" >&2
  exit 1
fi

echo "==> Preparing local runtime directory"
mkdir -p api/data
touch api/data/.gitkeep

if [ -d "$ROOT_DIR/.venv" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
fi

echo "==> Installing backend dependencies"
"$PYTHON_BIN" -m pip install -r requirements.txt

echo "==> Installing frontend dependencies"
mkdir -p "$NPM_CACHE_DIR"
npm_config_cache="$NPM_CACHE_DIR" npm --prefix web-vue install

echo "==> Building frontend"
npm_config_cache="$NPM_CACHE_DIR" npm --prefix web-vue run build

echo
echo "Build completed."
echo
echo "For local development, run:"
echo "  ./start.sh"
echo
echo "Before deploying to a server, make sure you configure your model providers"
echo "through the application UI or a private runtime data volume instead of committing keys to git."
