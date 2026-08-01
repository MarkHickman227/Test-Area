# ApplyPilot data safety

Jobs, preferences, and CVs live in the **Postgres Docker volume** `applypilot_pgdata` on the VPS.

## Do not

- `docker compose down -v` — destroys the Postgres volume
- `docker volume rm applypilot_applypilot_pgdata`
- Recreate an empty `db` volume unless you are restoring from backup

## Safe restart / redeploy

```bash
cd /root/applypilot
./scripts/backup-db.sh
docker compose up -d --build   # keeps the db volume
```

## Backups (VPS)

| Item | Detail |
|------|--------|
| Script | `scripts/backup-db.sh` |
| Cron | Daily `03:15` UTC |
| Location | `/root/applypilot/backups/applypilot_*.sql.gz` |
| Latest | `backups/applypilot_latest.sql.gz` |
| Retention | 30 days |

## Restore

```bash
/root/applypilot/scripts/restore-db.sh backups/applypilot_latest.sql.gz
```
