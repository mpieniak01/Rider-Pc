#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}" )/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
PID_DIR="${ROOT_DIR}/.pids"
DATA_DIR="${ROOT_DIR}/data"
GRAFANA_HOME="${ROOT_DIR}/data/grafana"
GRAFANA_CONF="${ROOT_DIR}/config/grafana.ini"
GRAFANA_LOG="${LOG_DIR}/grafana.log"
PANEL_PORT="${PANEL_PORT:-8080}"

mkdir -p "${LOG_DIR}" "${PID_DIR}" "${DATA_DIR}/redis" "${DATA_DIR}/prometheus" "${GRAFANA_HOME}"

if [[ ! -r "${GRAFANA_CONF}" ]]; then
  if [[ -r "/etc/grafana/grafana.ini" ]]; then
    GRAFANA_CONF="/etc/grafana/grafana.ini"
  else
    GRAFANA_CONF="/usr/share/grafana/conf/defaults.ini"
  fi
fi

info() {
  printf "[start-stack] %s\n" "$*"
}

warn() {
  printf "[start-stack] WARNING: %s\n" "$*" >&2
}

# Load .env once so every service (including helpers like Ollama) sees the same configuration
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.env"
  set +a
else
  warn "Missing .env file. Copy .env.example to .env and fill in your Rider-PI settings."
fi

ensure_venv() {
  if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
    info "Creating Python virtualenv (.venv)"
    python3 -m venv "${ROOT_DIR}/.venv"
  fi
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.venv/bin/activate"
  pip install -q -r "${ROOT_DIR}/requirements.txt"
}

start_redis() {
  local pid_file="${PID_DIR}/redis.pid"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    info "Redis already running (PID $(cat "${pid_file}"))"
    return
  fi

  if ! command -v redis-server >/dev/null 2>&1; then
    warn "redis-server not found. Install it with 'sudo apt install redis-server'. Skipping Redis startup."
    return
  fi

  info "Starting Redis on port 6379"
  redis-server \
    --port 6379 \
    --daemonize yes \
    --dir "${DATA_DIR}/redis" \
    --logfile "${LOG_DIR}/redis.log" \
    --pidfile "${pid_file}" \
    --save "" \
    --appendonly no
}

start_prometheus() {
  local pid_file="${PID_DIR}/prometheus.pid"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    info "Prometheus already running (PID $(cat "${pid_file}"))"
    return
  fi

  if ! command -v prometheus >/dev/null 2>&1; then
    warn "prometheus binary not found. Install it (e.g. 'sudo apt install prometheus') to enable metrics scraping."
    return
  fi

  local prometheus_log="${LOG_DIR}/prometheus.log"
  info "Starting Prometheus (logs: ${prometheus_log})"
  prometheus \
    --config.file="${ROOT_DIR}/config/prometheus.yml" \
    --storage.tsdb.path="${DATA_DIR}/prometheus" \
    --web.listen-address="0.0.0.0:9090" \
    >"${prometheus_log}" 2>&1 &
  echo $! > "${pid_file}"
}

start_grafana() {
  local pid_file="${PID_DIR}/grafana.pid"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    info "Grafana already running (PID $(cat "${pid_file}"))"
    return
  fi

  if ! command -v grafana-server >/dev/null 2>&1; then
    warn "grafana-server binary not found. Install it (e.g. 'sudo apt install grafana') if you need dashboards."
    return
  fi

  local grafana_log="${GRAFANA_LOG}"
  info "Starting Grafana (logs: ${grafana_log})"
  GF_PATHS_DATA="${GRAFANA_HOME}/data" \
  GF_PATHS_LOGS="${GRAFANA_HOME}/logs" \
  GF_PATHS_PLUGINS="${GRAFANA_HOME}/plugins" \
  grafana-server \
    --homepath /usr/share/grafana \
    --config "${GRAFANA_CONF}" \
    --packaging=deb \
    --pidfile "${PID_DIR}/grafana.pid" \
    >"${grafana_log}" 2>&1 &
  echo $! > "${pid_file}"
}

_detect_ollama_binding() {
  local config_path="${TEXT_PROVIDER_CONFIG:-${ROOT_DIR}/config/providers.toml}"
  python3 - <<'PY' "${config_path}" 2>/dev/null || true
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore
from urllib.parse import urlparse

config_path = sys.argv[1]
default_url = "http://127.0.0.1:11434"
host = None
try:
    with open(config_path, "rb") as fp:
        data = tomllib.load(fp)
        host = (data.get("text") or {}).get("ollama_host") or None
except Exception:
    host = None

host = host or default_url
if "://" not in host:
    host = f"http://{host}"
parsed = urlparse(host)
hostname = parsed.hostname or "127.0.0.1"
port = parsed.port or 11434
netloc = f"{hostname}:{port}"
is_local = hostname in ("127.0.0.1", "localhost", "::1", "0.0.0.0")
print(f"{netloc}|{1 if is_local else 0}")
PY
}

start_ollama() {
  local pid_file="${PID_DIR}/ollama.pid"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    info "Ollama already running (PID $(cat "${pid_file}"))"
    return
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    warn "ollama CLI not found. Install it from https://ollama.com/ to enable lokalny LLM."
    return
  fi

  local binding
  binding="$(_detect_ollama_binding)"
  local addr="${binding%|*}"
  local is_local="${binding#*|}"
  if [[ "${is_local}" != "1" ]]; then
    info "Skipping lokalne uruchomienie Ollamy (konfiguracja wskazuje host ${addr})."
    return
  fi

  mkdir -p "${LOG_DIR}"
  local ollama_log="${LOG_DIR}/ollama.log"
  info "Starting Ollama server on ${addr} (logs: ${ollama_log})"
  OLLAMA_HOST="${addr}" ollama serve >"${ollama_log}" 2>&1 &
  echo $! > "${pid_file}"
}

start_rider_pc() {
  local pid_file="${PID_DIR}/rider-pc.pid"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    info "Rider-PC server already running (PID $(cat "${pid_file}"))"
    return
  fi

  ensure_venv

  local server_port="${PANEL_PORT}"
  local rider_log="${LOG_DIR}/panel-${server_port}.log"
  info "Starting Rider panel on port ${server_port} (logs: ${rider_log})"
  SERVER_PORT="${server_port}" nohup "${ROOT_DIR}/.venv/bin/python" -m pc_client.main \
    >>"${rider_log}" 2>&1 &
  echo $! > "${pid_file}"
  info "Panel service started in background (http://localhost:${server_port}/)"
}

start_redis
start_prometheus
start_grafana
start_ollama
start_rider_pc

info "All available services started (see ${LOG_DIR} for logs)."
info "Use scripts/stop_local_stack.sh to stop background processes."
