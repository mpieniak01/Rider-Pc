#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT/.venv-agent}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "$VENV_PATH" ]; then
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

if [ ! -f "$VENV_PATH/bin/activate" ]; then
  echo "Error: Failed to create virtual environment" >&2
  exit 1
fi
# shellcheck disable=SC1090
. "$VENV_PATH/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT/config/agent/requirements-test.txt" -c "$ROOT/config/agent/constraints.txt"

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_ASYNCIO_MODE=auto

# Note: The old version set several environment variables for hardware-free testing
# (RIDER_APPS_PATH, FACE_LCD_*, RIDER_NO_HW). These are no longer needed and have
# been intentionally removed. If any tests depend on them, please update the tests.
cd "$ROOT"
pytest \
  pc_client/tests \
  tests/test_project_issues.py \
  -q --maxfail=1 \
  -p pytest_asyncio.plugin \
  -p pytest_timeout \
  --timeout=30 --timeout-method=thread
