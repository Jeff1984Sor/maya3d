#!/usr/bin/env bash
# Uso: ops/restore-test.sh <staging|prod>
# Teste mensal de restauração: restaura o último dump num banco TEMPORÁRIO e valida.
# Só toca no banco descartável 'print3d_restore_test' (criado e removido aqui).
set -euo pipefail
export SCRIPT_NAME=restore-test
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env

LATEST="$(ls -1t "${STACK_DIR}/backups/"*.dump 2>/dev/null | head -1 || true)"
[[ -n "$LATEST" ]] || die "nenhum dump em ${STACK_DIR}/backups"

TMP_DB="print3d_restore_test"
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${TMP_DB}" -c "CREATE DATABASE ${TMP_DB}"
cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${TMP_DB}" >/dev/null; }
trap cleanup EXIT

for ext in vector pg_trgm unaccent; do
  sudo -u postgres psql -d "$TMP_DB" -c "CREATE EXTENSION IF NOT EXISTS ${ext}" >/dev/null
done

log "restaurando ${LATEST}"
sudo -u postgres pg_restore --no-owner --dbname="$TMP_DB" "$LATEST"

BRANDS="$(sudo -u postgres psql -d "$TMP_DB" -Atc 'select count(*) from brand_settings')"
[[ "$BRANDS" == "1" ]] || die "validação falhou: brand_settings tem ${BRANDS} linhas (esperado 1)"
log "restauração validada (${LATEST})"
