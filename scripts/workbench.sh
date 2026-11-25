#!/usr/bin/env bash
# Personal AI Workbench - start / stop / status for PostgreSQL, API, Worker and Web.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT/services/api"
WEB_DIR="$ROOT/apps/web"
RUN_DIR="$ROOT/.run"
DATA_DIR="$API_DIR/.data"
PGDATA="${PGDATA:-/opt/homebrew/var/postgresql@17}"
PG_BIN="${PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
API_URL="http://127.0.0.1:${API_PORT}"
WEB_URL="http://127.0.0.1:${WEB_PORT}"

if [ -x "$PG_BIN/pg_ctl" ]; then
  export PATH="$PG_BIN:$PATH"
fi

mkdir -p "$RUN_DIR" "$DATA_DIR"
chmod +x "$0" 2>/dev/null || true

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

pg_ready() { pg_isready -h 127.0.0.1 -p 5432 -q >/dev/null 2>&1; }

start_pg() {
  if pg_ready; then
    say "postgres: already running"
    return
  fi
  [ -d "$PGDATA" ] || fail "PostgreSQL data directory not found: $PGDATA"
  say "postgres: starting ($PGDATA)"
  pg_ctl -D "$PGDATA" -l "$RUN_DIR/postgres.log" start >/dev/null
  for _ in $(seq 1 30); do
    pg_ready && { say "postgres: ready"; return; }
    sleep 0.5
  done
  fail "postgres did not become ready; see $RUN_DIR/postgres.log"
}

ensure_db() {
  local exists
  exists="$(psql -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='workbench'" || true)"
  if [ "$exists" != "1" ]; then
    say "database: creating workbench"
    createdb -h 127.0.0.1 workbench
  fi
  exists="$(psql -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='workbench_test'" || true)"
  if [ "$exists" != "1" ]; then
    say "database: creating workbench_test"
    createdb -h 127.0.0.1 workbench_test
  fi
  ( cd "$API_DIR" && .venv/bin/alembic upgrade head >/dev/null )
  say "database: migrations up to date"
}

pid_alive() {
  local file="$1"
  [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null
}

spawn_detached() {
  # Start a long-running process in its own session so the launcher can exit.
  local name="$1"; shift
  LOG="$RUN_DIR/$name.log" PIDFILE="$RUN_DIR/$name.pid" WORKDIR="$PWD" \
    python3 -c 'import os, subprocess, sys
log = open(os.environ["LOG"], "ab")
process = subprocess.Popen(
    sys.argv[1:],
    cwd=os.environ["WORKDIR"],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
open(os.environ["PIDFILE"], "w").write(str(process.pid))' "$@"
}

start_api() {
  if pid_alive "$RUN_DIR/api.pid"; then
    say "api: already running (pid $(cat "$RUN_DIR/api.pid"))"
    return
  fi
  [ -x "$API_DIR/.venv/bin/uvicorn" ] || fail "API venv missing; install dependencies first"
  say "api: starting on $API_URL"
  ( cd "$API_DIR" && SSL_CERT_FILE="/etc/ssl/cert.pem" spawn_detached api .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" )
  for _ in $(seq 1 40); do
    if curl -fsS "$API_URL/health/ready" >/dev/null 2>&1; then
      say "api: ready"
      return
    fi
    sleep 0.5
  done
  tail -20 "$RUN_DIR/api.log" >&2 || true
  fail "api did not become ready"
}

start_worker() {
  if pid_alive "$RUN_DIR/worker.pid"; then
    say "worker: already running (pid $(cat "$RUN_DIR/worker.pid"))"
    return
  fi
  [ -x "$API_DIR/.venv/bin/python" ] || fail "API venv missing; install dependencies first"
  rm -f "$RUN_DIR/worker.heartbeat"
  say "worker: starting"
  ( cd "$API_DIR" && spawn_detached worker .venv/bin/python -m app.workers.rag_worker )
  for _ in $(seq 1 20); do
    if pid_alive "$RUN_DIR/worker.pid"; then
      say "worker: ready"
      return
    fi
    sleep 0.5
  done
  tail -20 "$RUN_DIR/worker.log" >&2 || true
  fail "worker did not start"
}

start_web() {
  if pid_alive "$RUN_DIR/web.pid"; then
    say "web: already running (pid $(cat "$RUN_DIR/web.pid"))"
    return
  fi
  command -v pnpm >/dev/null 2>&1 || fail "pnpm is required for the web app"
  [ -f "$WEB_DIR/package.json" ] || fail "web app not found at $WEB_DIR"
  if [ ! -d "$WEB_DIR/node_modules" ]; then
    say "web: installing dependencies"
    ( cd "$WEB_DIR" && pnpm install --silent )
  fi
  say "web: starting on $WEB_URL"
  ( cd "$WEB_DIR" && spawn_detached web pnpm dev --host 127.0.0.1 --port "$WEB_PORT" )
  for _ in $(seq 1 60); do
    if curl -fsS "$WEB_URL" >/dev/null 2>&1; then
      say "web: ready"
      return
    fi
    sleep 0.5
  done
  tail -20 "$RUN_DIR/web.log" >&2 || true
  fail "web did not become ready"
}

stop_service() {
  local name="$1" file="$2" port="${3:-}" wait_loops="${4:-20}"
  if pid_alive "$file"; then
    local pid; pid="$(cat "$file")"
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 "$wait_loops"); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -KILL "$pid" 2>/dev/null || true
    say "$name: stopped"
  else
    say "$name: not running"
  fi
  rm -f "$file"
}

stop_pg() {
  if pg_ready; then
    say "postgres: stopping"
    pg_ctl -D "$PGDATA" -m fast stop >/dev/null 2>&1 || true
  fi
}

cmd_start() {
  start_pg
  ensure_db
  start_api
  start_worker
  start_web
  say ""
  say "Workbench is ready:"
  say "  Web: $WEB_URL"
  say "  API: $API_URL/docs"
  say "  Health: $API_URL/health"
}

cmd_stop() {
  stop_service worker "$RUN_DIR/worker.pid" "" 150
  stop_service web "$RUN_DIR/web.pid" "$WEB_PORT"
  stop_service api "$RUN_DIR/api.pid" "$API_PORT"
  if [ "${1:-}" = "--all" ] || [ "${1:-}" = "all" ]; then
    stop_pg
  else
    say "postgres: left running (use '$0 stop --all' to stop it)"
  fi
}

cmd_status() {
  printf 'postgres : '
  if pg_ready; then printf 'ready\n'; else printf 'down\n'; fi
  printf 'api      : '
  if curl -fsS "$API_URL/health" 2>/dev/null; then printf '\n'; else printf 'down\n'; fi
  printf 'worker   : '
  if pid_alive "$RUN_DIR/worker.pid"; then
    printf 'ready (pid %s)\n' "$(cat "$RUN_DIR/worker.pid")"
  else
    printf 'down\n'
  fi
  printf 'web      : '
  if curl -fsS "$WEB_URL" >/dev/null 2>&1; then printf 'ready (%s)\n' "$WEB_URL"; else printf 'down\n'; fi
}

cmd_logs() {
  local target="${1:-api}"
  tail -n 80 "$RUN_DIR/$target.log" 2>/dev/null || fail "no log for $target"
}

case "${1:-start}" in
  start) cmd_start ;;
  stop) shift; cmd_stop "${1:-}" ;;
  restart) cmd_stop; sleep 1; cmd_start ;;
  status) cmd_status ;;
  url) say "$WEB_URL" ;;
  logs) shift; cmd_logs "${1:-api}" ;;
  *) fail "usage: $0 {start|stop [--all]|restart|status|url|logs [api|worker|web|postgres]}" ;;
esac
