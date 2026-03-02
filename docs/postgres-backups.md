# Postgres Backups

## Manual backup

On the VM:

```bash
cd ~/apps/astralle
mkdir -p ~/backups/postgres
POSTGRES_USER=app POSTGRES_DB=app bash infra/scripts/backup-postgres.sh ~/backups/postgres
```

This creates a compressed dump and keeps the last 7 days by default.

## Recommended daily cron

Edit the deploy user's crontab:

```bash
crontab -e
```

Add:

```cron
15 3 * * * cd /home/deploy/apps/astralle && POSTGRES_USER=app POSTGRES_DB=app /bin/bash infra/scripts/backup-postgres.sh /home/deploy/backups/postgres >> /home/deploy/backups/postgres/backup.log 2>&1
```

## Restore example

Copy a dump back to the VM if needed, then:

```bash
gunzip -c /home/deploy/backups/postgres/postgres-YYYYMMDDTHHMMSSZ.sql.gz | docker exec -i astralle-postgres-1 psql -U app -d app
```

Test restore at least once before relying on backups.
