#!/bin/bash
# Run on the Hostinger VPS as root. Pulls the CV scoring repair onto
# /root/applypilot and rebuilds Docker Compose without deleting Postgres.
set -euo pipefail

APP_DIR=/root/applypilot
BRANCH=cursor/repair-applypilot-cv-53b6
ZIP_URL="https://github.com/MarkHickman227/Test-Area/archive/refs/heads/${BRANCH}.zip"
STAGING=/tmp/applypilot-repair-$$

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on the VPS." >&2
  exit 1
fi
if [[ ! -d "$APP_DIR" || ! -f "$APP_DIR/config/.env" ]]; then
  echo "Need $APP_DIR with config/.env — aborting." >&2
  exit 1
fi

cd "$APP_DIR"
if [[ -x ./scripts/backup-db.sh ]]; then
  ./scripts/backup-db.sh || true
fi

rm -rf "$STAGING"
mkdir -p "$STAGING"
curl -fL --retry 4 --retry-delay 4 -o "$STAGING/repair.zip" "$ZIP_URL"

SRC="$(python3 - "$STAGING/repair.zip" "$STAGING/src" <<'PY'
import sys
from pathlib import Path
from zipfile import ZipFile

zip_path, dest = Path(sys.argv[1]), Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
with ZipFile(zip_path) as zf:
    zf.extractall(dest)
roots = [p for p in dest.iterdir() if p.is_dir()]
if len(roots) != 1:
    raise SystemExit(f"expected one zip root, found {roots}")
print(roots[0])
PY
)"

# Keep live secrets, backups, and the named Postgres volume.
for part in backend frontend db docker-compose.yml scripts docs; do
  if [[ -e "$SRC/$part" ]]; then
    rm -rf "$APP_DIR/$part"
    cp -a "$SRC/$part" "$APP_DIR/$part"
  fi
done
chmod +x "$APP_DIR/scripts/"*.sh 2>/dev/null || true

cd "$APP_DIR"
docker compose up -d --build
docker compose ps

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/health | grep -q 'cv-match-1'; then
    echo "repair_version is cv-match-1"
    break
  fi
  sleep 2
done
curl -sS http://127.0.0.1:8000/api/health
echo
curl -sS -X POST http://127.0.0.1:8000/api/cvs/reparse
echo
curl -sS --max-time 300 -X POST 'http://127.0.0.1:8000/api/pipeline/backfill?limit=25'
echo
curl -sS http://127.0.0.1:8000/api/analytics
echo
rm -rf "$STAGING"
echo "Repair pull finished. Repeat POST /api/pipeline/backfill if score_ge_60 is still 0."
