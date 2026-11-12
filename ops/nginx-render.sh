#!/usr/bin/env bash
# Uso: ops/nginx-render.sh <staging|prod> [<host-loja> <host-painel> <host-api>] [--force]
# Gera /etc/nginx/sites-available/print3d-<stack>.conf a partir de infra/nginx.
# Sem hosts: loja./admin./api. + BASE_DOMAIN. Com hosts: usa os informados
# (ex.: loja.exemplo.com.br painel.loja.exemplo.com.br api.loja.exemplo.com.br).
# Vários endereços para a mesma função: separe por vírgula (ex.: troca de domínio, o antigo
# segue no ar): exemplo.com.br,www.exemplo.com.br painel.exemplo.com.br api.exemplo.com.br
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
for name in STOREFRONT_HOST ADMIN_HOST API_HOST; do
  value="${!name//,/ }"  # vírgula → espaço: server_name aceita vários nomes
  [[ "$value" =~ ^[a-z0-9.\ -]+$ ]] || die "host inválido em ${name}: ${!name}"
  printf -v "$name" '%s' "$value"
done
export STOREFRONT_HOST ADMIN_HOST API_HOST

sudo install -d /etc/nginx/snippets
sudo install -m 644 "${PRINT3D_ROOT}/infra/nginx/snippets/"*.conf /etc/nginx/snippets/
envsubst '${STOREFRONT_HOST} ${ADMIN_HOST} ${API_HOST} ${STOREFRONT_PORT} ${ADMIN_PORT} ${API_PORT} ${STACK}' \
  < "${PRINT3D_ROOT}/infra/nginx/stack.conf.template" | sudo tee "$TARGET" >/dev/null
sudo ln -sf "$TARGET" "/etc/nginx/sites-enabled/print3d-${STACK}.conf"
if ! sudo nginx -t; then
  # nunca deixa uma configuração quebrada ativa: os outros sites do servidor dependem do nginx
  sudo rm -f "/etc/nginx/sites-enabled/print3d-${STACK}.conf"
  die "configuração inválida: desativada, nada foi recarregado"
fi
sudo systemctl reload nginx
log "nginx configurado: ${STOREFRONT_HOST}, ${ADMIN_HOST}, ${API_HOST}"
DOMAINS=""
for host in ${STOREFRONT_HOST} ${ADMIN_HOST} ${API_HOST}; do DOMAINS+=" -d ${host}"; done
log "para HTTPS: sudo certbot --nginx${DOMAINS} --redirect"
