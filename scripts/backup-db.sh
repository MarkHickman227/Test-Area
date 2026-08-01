#!/bin/bash
set -euo pipefail
cd /root/applypilot
mkdir -p backups
chmod 700 backups
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="backups/applypilot_${TS}.sql.gz"
docker exec applypilot-db pg_dump -U applypilot -d applypilot --no-owner --no-acl | gzip -c > "$OUT"
cp -a "$OUT" backups/applypilot_latest.sql.gz
find backups -name 'applypilot_2*.sql.gz' -mtime +30 -delete
ls -lh "$OUT"
