#!/usr/bin/env bash
# Uso: ops/check-ports.sh <staging|prod>
# Falha se alguma porta da stack já estiver ocupada por OUTRO serviço do servidor.
# Se a própria stack já estiver rodando (re-deploy), as portas dela são ignoradas.
set -euo pipefail
export SCRIPT_NAME=check-ports
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env
IMAGE_TAG="${IMAGE_TAG:-$(cat "${STACK_DIR}/.current_tag" 2>/dev/null || echo check)}"; export IMAGE_TAG
export REGISTRY="${REGISTRY:-ghcr.io/x}"

if [[ -n "$(compose ps -q 2>/dev/null || true)" ]]; then
  log "stack ${STACK} já em execução: portas são dela, nada a checar"; exit 0
fi

conflicts=0
for port in "$API_PORT" "$STOREFRONT_PORT" "$ADMIN_PORT"; do
  if ss -H -ltn "sport = :${port}" | grep -q .; then
    log "CONFLITO: porta ${port} já está em uso:"; ss -ltnp "sport = :${port}" >&2 || true
    conflicts=1
  else
    log "porta ${port} livre"
  fi
done
[[ $conflicts -eq 0 ]] || die "ajuste as portas em infra/compose/env/${STACK}.env (e libere-as no firewall do GCP)"
