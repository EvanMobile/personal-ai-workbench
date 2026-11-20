#!/usr/bin/env bash
# Create a full local backup: database, attachments, config copy, migration version.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT/services/api"
DATA_DIR="$API_DIR/.data"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_ROOT/$STAMP"

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v pg_dump >/dev/null 2>&1 || export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
command -v pg_dump >/dev/null 2>&1 || fail "pg_dump not found"

pg_isready -h 127.0.0.1 -p 5432 -q || fail "PostgreSQL is not running; start it first"

mkdir -p "$TARGET"

say "backup: database"
pg_dump -h 127.0.0.1 -d workbench -Fc -f "$TARGET/workbench.dump"

say "backup: attachments"
if [ -d "$DATA_DIR/uploads" ]; then
  tar -czf "$TARGET/attachments.tar.gz" -C "$DATA_DIR" uploads
else
  : > "$TARGET/attachments.empty"
fi

say "backup: configuration (contains secrets; keep this directory private)"
if [ -f "$API_DIR/.env" ]; then
  cp "$API_DIR/.env" "$TARGET/config.env"
  chmod 600 "$TARGET/config.env"
fi
cp "$API_DIR/.env.example" "$TARGET/config.env.example"

say "backup: migration version"
( cd "$API_DIR" && .venv/bin/alembic current > "$TARGET/alembic_version.txt" 2>/dev/null || true )

(
  cd "$TARGET"
  {
    echo "created_at=$(date -Iseconds)"
    echo "database=workbench"
    echo "alembic=$(tail -1 alembic_version.txt 2>/dev/null || echo unknown)"
    shasum -a 256 workbench.dump 2>/dev/null || true
    [ -f attachments.tar.gz ] && shasum -a 256 attachments.tar.gz || true
  } > manifest.txt
)

say ""
say "Backup complete: $TARGET"
say "  workbench.dump        PostgreSQL custom-format dump"
say "  attachments.tar.gz    uploaded raw files"
say "  config.env            local config (mode 600; contains secrets if any)"
say "  alembic_version.txt   migration revision"
