#!/usr/bin/env bash
set -euo pipefail
# Encrypted backup stub. Wire restic repository credentials outside this repo.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_DIR:-$ROOT/backups}/$STAMP"
mkdir -p "$DEST"
if [[ "${DATABASE_URL:-}" == postgresql* ]]; then
  pg_dump "$DATABASE_URL" | gzip > "$DEST/postgres.sql.gz"
else
  sqlite_path="${DATABASE_URL#sqlite+pysqlite:///}"
  sqlite_path="${sqlite_path#sqlite:///}"
  if [[ -n "$sqlite_path" && "$sqlite_path" != /* ]]; then
    sqlite_path="$ROOT/${sqlite_path#./}"
  fi
  if [[ -f "$sqlite_path" ]]; then
    gzip -c "$sqlite_path" > "$DEST/sqlite.db.gz"
  fi
fi
if [[ -d "${STORAGE_LOCAL_PATH:-$ROOT/data/storage}" ]]; then
  tar -czf "$DEST/storage.tgz" -C "$(dirname "${STORAGE_LOCAL_PATH:-$ROOT/data/storage}")" "$(basename "${STORAGE_LOCAL_PATH:-$ROOT/data/storage}")"
fi
echo "Backup written to $DEST"
echo "Restore test: gunzip and load into an empty database, then verify generation_jobs and generation_outputs counts."
