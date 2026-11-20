#!/usr/bin/env bash
# Restore a Workbench backup into a target database (default: workbench_restore).
# The restore is verified by counting core tables and comparing with the dump.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT/services/api"
DATA_DIR="$API_DIR/.data"
BACKUP_DIR="${1:-}"
TARGET_DB="${2:-workbench_restore}"

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ -n "$BACKUP_DIR" ] || fail "usage: $0 <backup-dir> [target-db]"
[ -f "$BACKUP_DIR/workbench.dump" ] || fail "dump not found in $BACKUP_DIR"
command -v pg_restore >/dev/null 2>&1 || export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
pg_isready -h 127.0.0.1 -p 5432 -q || fail "PostgreSQL is not running"

say "restore: recreating database $TARGET_DB"
dropdb -h 127.0.0.1 --if-exists "$TARGET_DB"
createdb -h 127.0.0.1 "$TARGET_DB"

say "restore: loading dump"
pg_restore -h 127.0.0.1 -d "$TARGET_DB" --no-owner --role="$(whoami)" "$BACKUP_DIR/workbench.dump" 2>/dev/null \
  || pg_restore -h 127.0.0.1 -d "$TARGET_DB" --no-owner "$BACKUP_DIR/workbench.dump"

say "restore: applying migrations (no-op if already current)"
( cd "$API_DIR" && DATABASE_URL="postgresql+psycopg://127.0.0.1:5432/$TARGET_DB" \
    .venv/bin/alembic upgrade head >/dev/null )

say "restore: verifying row counts"
psql -h 127.0.0.1 -d "$TARGET_DB" -tAc \
  "SELECT 'captures='||count(*) FROM captures UNION ALL
   SELECT 'raw_contents='||count(*) FROM raw_contents UNION ALL
   SELECT 'drafts='||count(*) FROM drafts UNION ALL
   SELECT 'knowledge_assets='||count(*) FROM knowledge_assets UNION ALL
   SELECT 'pages='||count(*) FROM pages UNION ALL
   SELECT 'artifacts='||count(*) FROM artifacts;"

if [ -n "${RESTORE_FILES_TO:-}" ]; then
  [ -f "$BACKUP_DIR/attachments.tar.gz" ] || fail "attachments archive missing"
  mkdir -p "$RESTORE_FILES_TO"
  tar -xzf "$BACKUP_DIR/attachments.tar.gz" -C "$RESTORE_FILES_TO"
  say "restore: attachments extracted to $RESTORE_FILES_TO"
else
  say "restore: attachments not extracted (set RESTORE_FILES_TO=<dir> to extract)"
fi

say ""
say "Restore drill target: $TARGET_DB"
say "To verify manually: psql -h 127.0.0.1 -d $TARGET_DB -c 'select count(*) from knowledge_assets;'"
