#!/usr/bin/env bash
# shellcheck shell=bash
# Funções comuns dos scripts de /ops. Rodam SOMENTE no prod2 (nunca no Windows).

PRINT3D_ROOT="${PRINT3D_ROOT:-/srv/print3d}"

log() { printf '%s [%s] %s\n' "$(date -u +%FT%TZ)" "${SCRIPT_NAME:-ops}" "$*" >&2; }
die() { log "ERRO: $*"; exit 1; }

require_stack() {
  case "${1:-}" in
    staging|prod) STACK="$1" ;;
    *) die "stack inválida: '${1:-}' (use staging|prod)" ;;
  esac
  STACK_DIR="${PRINT3D_ROOT}/${STACK}"
  STACK_ENV_FILE="${STACK_DIR}/.env"
  [[ -f "$STACK_ENV_FILE" ]] || die "faltando ${STACK_ENV_FILE} (rode ops/bootstrap-server.sh)"
  export STACK STACK_DIR STACK_ENV_FILE
}

# Carrega segredos da stack no shell (BASE_DOMAIN, REGISTRY, DATABASE_URL...).
load_stack_env() {
  set -a
  # shellcheck disable=SC1090
  source "${PRINT3D_ROOT}/infra/compose/env/${STACK}.env"
  # shellcheck disable=SC1090
  source "$STACK_ENV_FILE"
  set +a
}

# Ação destrutiva em produção exige confirmação explícita (regra inegociável da spec).
confirm_prod() {
  [[ "$STACK" == "prod" ]] || return 0
  [[ "${CONFIRM_PROD:-}" == "yes" ]] && return 0
  [[ -t 0 ]] || die "ação em produção sem terminal: exporte CONFIRM_PROD=yes conscientemente"
  read -r -p "Isto afeta PRODUÇÃO. Digite 'prod' para continuar: " answer
  [[ "$answer" == "prod" ]] || die "cancelado"
}

compose() {
  docker compose \
    --env-file "${PRINT3D_ROOT}/infra/compose/env/${STACK}.env" \
    --env-file "$STACK_ENV_FILE" \
    -f "${PRINT3D_ROOT}/infra/compose/docker-compose.yml" "$@"
}

# stack_host loja|admin|api -> hostname público (prod: loja.dominio; staging: loja-staging.dominio)
stack_host() {
  local role="$1" suffix=""
  [[ "$STACK" == "staging" ]] && suffix="-staging"
  printf '%s%s.%s' "$role" "$suffix" "${BASE_DOMAIN:?BASE_DOMAIN não definido}"
}

# URL libpq (sem o '+psycopg' do SQLAlchemy)
libpq_url() { printf '%s' "${DATABASE_URL/+psycopg/}"; }
