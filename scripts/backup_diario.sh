#!/bin/bash
set -euo pipefail
umask 077
: "${BACKUP_DIR:?Configure BACKUP_DIR con almacenamiento persistente cifrado}"
if [[ "$BACKUP_DIR" != /* || ! -d "$BACKUP_DIR" || ! -w "$BACKUP_DIR" ]]; then
    echo 'BACKUP_DIR debe ser un directorio absoluto existente y escribible.' >&2
    exit 1
fi
# systemd fija WorkingDirectory y el intérprete; no se cargan secretos del checkout.
backup_fecha=$(date -u +%Y%m%dT%H%M%S%NZ)
exec .venv/bin/python scripts/postgres_backup.py "$BACKUP_DIR/asistencias-$backup_fecha.dump"
