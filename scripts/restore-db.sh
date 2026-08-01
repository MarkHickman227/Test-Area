#!/bin/bash
set -euo pipefail
cd /root/applypilot
DUMP="${1:-backups/applypilot_latest.sql.gz}"
if [[ ! -f "$DUMP" ]]; then
  echo "Dump not found: $DUMP" >&2
  exit 1
fi
echo "Restoring from $DUMP (existing data will be replaced in tables from dump)..."
gunzip -c "$DUMP" | docker exec -i applypilot-db psql -U applypilot -d applypilot
echo "Restore complete."
docker exec applypilot-db psql -U applypilot -d applypilot -c "SELECT count(*) AS jobs FROM jobs; SELECT count(*) AS prefs FROM user_preferences;"
