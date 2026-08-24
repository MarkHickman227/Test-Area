#!/usr/bin/env bash
set -euo pipefail
# Restore test helper for local/dev dumps created by backup.sh.
ARCHIVE="${1:?usage: restore.sh backups/<stamp>}"
if [[ -f "$ARCHIVE/postgres.sql.gz" ]]; then
  gunzip -c "$ARCHIVE/postgres.sql.gz" | psql "$DATABASE_URL"
elif [[ -f "$ARCHIVE/sqlite.db.gz" ]]; then
  gunzip -c "$ARCHIVE/sqlite.db.gz" > "${2:?destination sqlite path required}"
fi
echo "Restore attempted from $ARCHIVE"
