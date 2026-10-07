#!/usr/bin/env bash
# Uso: ops/smoke.sh <staging|prod> [--local]
# Smoke tests pós-deploy. Padrão: via HTTPS público (valida Nginx + certificado).
# --local: direto nas portas do localhost (antes de configurar DNS/Nginx).
set -euo pipefail
SCRIPT_NAME=smoke
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env

if [[ "${2:-}" == "--local" ]]; then
  API="http://127.0.0.1:${API_PORT}"; STORE="http://127.0.0.1:${STOREFRONT_PORT}"; ADMIN="http://127.0.0.1:${ADMIN_PORT}"
else
  API="https://$(stack_host api)"; STORE="https://$(stack_host loja)"; ADMIN="https://$(stack_host admin)"
fi

# check <nome> <url> [padrão que deve aparecer no corpo]
check() {
  local name="$1" url="$2" pattern="${3:-}" body
  for attempt in $(seq 1 24); do
    if body="$(curl -fsS --max-time 8 "$url" 2>/dev/null)" && { [[ -z "$pattern" ]] || grep -q "$pattern" <<<"$body"; }; then
      log "OK   ${name}"; return 0
    fi
    sleep 5
  done
  log "FALHOU ${name} (${url})"; return 1
}

failed=0
check "api live"        "${API}/health/live"       '"status":"ok"' || failed=1
check "api ready"       "${API}/health/ready"      '"status":"ok"' || failed=1
check "api marca"       "${API}/v1/brand"          '"name"'        || failed=1
check "storefront"      "${STORE}/api/health"      '"app":"storefront"' || failed=1
check "storefront home" "${STORE}/"                                || failed=1
check "admin"           "${ADMIN}/api/health"      '"app":"admin"' || failed=1

[[ $failed -eq 0 ]] || die "smoke tests falharam em ${STACK}"
log "todos os smoke tests passaram em ${STACK}"
