#!/usr/bin/env bash
# Uso: ops/diagnose.sh <staging|prod>  — retrato somente leitura da stack. Seguro rodar a qualquer hora.
set -uo pipefail
export SCRIPT_NAME=diagnose
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env
IMAGE_TAG="$(cat "${STACK_DIR}/.current_tag" 2>/dev/null || echo unknown)"; export IMAGE_TAG

section() { printf '\n== %s ==\n' "$1"; }

section "versão"; echo "tag atual: ${IMAGE_TAG} | anterior: $(cat "${STACK_DIR}/.previous_tag" 2>/dev/null || echo -)"
section "containers"; compose ps
section "uso de disco"; df -h / "${PRINT3D_ROOT}" | sort -u; docker system df
section "banco"; psql "$(libpq_url)" -Atc "select current_database(), version()" 2>&1 | head -2 \
  && psql "$(libpq_url)" -Atc "select extname from pg_extension order by 1" 2>&1 | tr '\n' ' '; echo
section "migração atual"; compose run --rm --no-deps api alembic current 2>&1 | tail -3
section "health local"
curl -fsS "http://127.0.0.1:${API_PORT}/health/ready" || echo "api/ready indisponível"; echo
section "últimos erros (api, worker)"; compose logs --tail=30 api worker 2>&1 | grep -iE 'error|exception|traceback' | tail -20 || true
