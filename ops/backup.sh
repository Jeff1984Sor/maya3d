#!/usr/bin/env bash
# Uso: ops/backup.sh <staging|prod>  — pg_dump comprimido, copia p/ GCS, retém 7 dias locais.
# Arquivos (renders, STL) vivem no GCS com versionamento de objetos ativado no bucket.
set -euo pipefail
SCRIPT_NAME=backup
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env

OUT_DIR="${STACK_DIR}/backups"
FILE="${OUT_DIR}/print3d_${STACK}_$(date -u +%Y%m%dT%H%M%SZ).dump"
install -d -m 700 "$OUT_DIR"

log "pg_dump -> ${FILE}"
pg_dump "$(libpq_url)" --format=custom --no-owner --file="$FILE"
[[ -s "$FILE" ]] || die "dump vazio"
pg_restore --list "$FILE" >/dev/null || die "dump corrompido"

if [[ -n "${GCS_BACKUP_BUCKET:-}" ]]; then
  gcloud storage cp "$FILE" "gs://${GCS_BACKUP_BUCKET}/postgres/${STACK}/" --quiet
  log "enviado para gs://${GCS_BACKUP_BUCKET}/postgres/${STACK}/"
else
  log "GCS_BACKUP_BUCKET vazio: backup só local (configure o bucket!)"
fi

find "$OUT_DIR" -name '*.dump' -mtime +7 -delete
log "backup concluído"
