#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT/.venv-agent}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "$VENV_PATH" ]; then
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

# shellcheck disable=SC1090
. "$VENV_PATH/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT/config/agent/requirements-test.txt" -c "$ROOT/config/agent/constraints.txt"

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_ASYNCIO_MODE=auto

cd "$ROOT"
pytest \
  pc_client/tests \
  tests/test_project_issues.py \
  -q --maxfail=1 \
  -p pytest_asyncio.plugin \
  -p pytest_timeout \
  --timeout=30 --timeout-method=thread
