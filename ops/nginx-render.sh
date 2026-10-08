#!/usr/bin/env bash
# Uso: ops/nginx-render.sh <staging|prod> [<host-loja> <host-painel> <host-api>] [--force]
# Gera /etc/nginx/sites-available/print3d-<stack>.conf a partir de infra/nginx.
# Sem hosts: loja./admin./api. + BASE_DOMAIN. Com hosts: usa os informados
# (ex.: maya3d.mayacorp.com.br painel.maya3d.mayacorp.com.br api.maya3d.mayacorp.com.br).
# Só ACRESCENTA um arquivo no nginx: não mexe nos outros sites do servidor.
# Não sobrescreve conf existente (o certbot já editou o bloco HTTPS) sem --force.
set -euo pipefail
export SCRIPT_NAME=nginx-render
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env

FORCE=""
HOSTS=()
for arg in "${@:2}"; do
  if [[ "$arg" == "--force" ]]; then FORCE=1; else HOSTS+=("$arg"); fi
done

TARGET="/etc/nginx/sites-available/print3d-${STACK}.conf"
if [[ -f "$TARGET" && -z "$FORCE" ]]; then
  log "${TARGET} já existe; use --force para recriar (perde ajustes do certbot)"; exit 0
fi

if [[ ${#HOSTS[@]} -eq 3 ]]; then
  STOREFRONT_HOST="${HOSTS[0]}"; ADMIN_HOST="${HOSTS[1]}"; API_HOST="${HOSTS[2]}"
elif [[ ${#HOSTS[@]} -eq 0 ]]; then
  STOREFRONT_HOST="$(stack_host loja)"; ADMIN_HOST="$(stack_host admin)"; API_HOST="$(stack_host api)"
else
  die "informe os 3 hosts (loja, painel, api) ou nenhum"
fi
export STOREFRONT_HOST ADMIN_HOST API_HOST

sudo install -d /etc/nginx/snippets
sudo install -m 644 "${PRINT3D_ROOT}/infra/nginx/snippets/"*.conf /etc/nginx/snippets/
envsubst '${STOREFRONT_HOST} ${ADMIN_HOST} ${API_HOST} ${STOREFRONT_PORT} ${ADMIN_PORT} ${API_PORT} ${STACK}' \
  < "${PRINT3D_ROOT}/infra/nginx/stack.conf.template" | sudo tee "$TARGET" >/dev/null
sudo ln -sf "$TARGET" "/etc/nginx/sites-enabled/print3d-${STACK}.conf"
sudo nginx -t
sudo systemctl reload nginx
log "nginx configurado: ${STOREFRONT_HOST}, ${ADMIN_HOST}, ${API_HOST}"
log "para HTTPS: sudo certbot --nginx -d ${STOREFRONT_HOST} -d ${ADMIN_HOST} -d ${API_HOST} --redirect"
