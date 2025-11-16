#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="${ROOT_DIR}/.pids"
LOG_DIR="${ROOT_DIR}/logs"
PANEL_PORT="${PANEL_PORT:-8080}"

stop_pid() {
  local name="$1"
  local desc="${2:-$1}"
  local pid_file="${PID_DIR}/${name}.pid"

  if [[ ! -f "${pid_file}" ]]; then
    printf "[stop-stack] %s not running (missing %s)\n" "${desc}" "${pid_file}"
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" 2>/dev/null; then
    printf "[stop-stack] Stopping %s (PID %s)\n" "${desc}" "${pid}"
    kill "${pid}" 2>/dev/null || true
    sleep 1
    if kill -0 "${pid}" 2>/dev/null; then
      printf "[stop-stack] %s still running, sending SIGKILL\n" "${desc}"
      kill -9 "${pid}" 2>/dev/null || true
    fi
  else
    printf "[stop-stack] %s process not found, cleaning pid file\n" "${desc}"
  fi
  rm -f "${pid_file}"
}

stop_pid "rider-pc" "panel (port ${PANEL_PORT})"
panel_log="${LOG_DIR}/panel-${PANEL_PORT}.log"
if [[ -f "${panel_log}" ]]; then
  printf "[stop-stack] Panel log available at %s\n" "${panel_log}"
fi
stop_pid "prometheus"
stop_pid "grafana"

# Redis writes its own pid when daemonized; use redis-cli if available.
if [[ -f "${PID_DIR}/redis.pid" ]]; then
  PID="$(cat "${PID_DIR}/redis.pid")"
  if command -v redis-cli >/dev/null 2>&1; then
    printf "[stop-stack] Shutting down Redis via redis-cli\n"
    redis-cli -p 6379 shutdown nosave >/dev/null 2>&1 || true
  fi
  if kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null || true
    sleep 1
    kill -9 "${PID}" 2>/dev/null || true
  fi
  rm -f "${PID_DIR}/redis.pid"
else
  printf "[stop-stack] Redis not running (missing %s/redis.pid)\n" "${PID_DIR}"
fi

printf "[stop-stack] Done.\n"
