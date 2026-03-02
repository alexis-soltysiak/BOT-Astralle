#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <backup-dir>" >&2
  exit 1
fi

BACKUP_DIR="$1"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_NAME="postgres-${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

docker exec astralle-postgres-1 pg_dump \
  -U "${POSTGRES_USER:-app}" \
  -d "${POSTGRES_DB:-app}" | gzip > "${BACKUP_DIR}/${ARCHIVE_NAME}"

find "$BACKUP_DIR" -type f -name 'postgres-*.sql.gz' -mtime +7 -delete

echo "backup written to ${BACKUP_DIR}/${ARCHIVE_NAME}"
