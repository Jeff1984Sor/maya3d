#!/usr/bin/env bash
# Uso (no prod2, uma vez por stack): ops/bootstrap-server.sh <staging|prod>
# Idempotente. Cria diretórios, banco + extensões, .env com segredos aleatórios
# e instala os timers de backup. NÃO apaga nada e NÃO sobrescreve .env existente.
set -euo pipefail
SCRIPT_NAME=bootstrap
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

STACK_ARG="${1:-}"
case "$STACK_ARG" in staging|prod) ;; *) die "uso: bootstrap-server.sh <staging|prod>" ;; esac
STACK="$STACK_ARG"; STACK_DIR="${PRINT3D_ROOT}/${STACK}"

command -v docker >/dev/null || die "docker não encontrado"
docker compose version >/dev/null || die "docker compose v2 não encontrado"

log "diretórios"
sudo install -d -o "$USER" -g "$USER" "$PRINT3D_ROOT" "$STACK_DIR" "${STACK_DIR}/backups"

DB="print3d_${STACK}"
ROLE="print3d_${STACK}"
if [[ ! -f "${STACK_DIR}/.env" ]]; then
  log "gerando ${STACK_DIR}/.env"
  DB_PASS="$(openssl rand -hex 24)"
  FERNET="$(head -c32 /dev/urandom | base64 | tr '+/' '-_')"
  umask 077
  sed -e "s#postgresql+psycopg://[^@]*@#postgresql+psycopg://${ROLE}:${DB_PASS}@#" \
      -e "s#/print3d_staging#/${DB}#" \
      -e "s#^FERNET_KEY=.*#FERNET_KEY=${FERNET}#" \
      "$(dirname "$0")/../infra/compose/env/server.env.example" > "${STACK_DIR}/.env"
  # senha também fica disponível para o passo de criação do role abaixo
  printf '%s' "$DB_PASS" > "${STACK_DIR}/.dbpass.tmp"
  log "EDITE ${STACK_DIR}/.env: BASE_DOMAIN, REGISTRY, CORS_ORIGINS, chaves de IA"
fi

if sudo -u postgres psql -Atc "select 1 from pg_database where datname='${DB}'" | grep -q 1; then
  log "banco ${DB} já existe"
else
  [[ -f "${STACK_DIR}/.dbpass.tmp" ]] || die "banco não existe e não há senha gerada; crie manualmente"
  log "criando role e banco ${DB}"
  sudo -u postgres psql -v ON_ERROR_STOP=1 \
    -c "CREATE ROLE ${ROLE} LOGIN PASSWORD '$(cat "${STACK_DIR}/.dbpass.tmp")'" \
    -c "CREATE DATABASE ${DB} OWNER ${ROLE}"
fi
rm -f "${STACK_DIR}/.dbpass.tmp"

log "extensões (exige pacote postgresql-<versão>-pgvector instalado no host)"
for ext in vector pg_trgm unaccent; do
  sudo -u postgres psql -d "$DB" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS ${ext}"
done

log "timers de backup (systemd)"
sudo install -m 644 "$(dirname "$0")"/systemd/*.service "$(dirname "$0")"/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now "print3d-backup@${STACK}.timer"
[[ "$STACK" == "staging" ]] && sudo systemctl enable --now "print3d-restore-test@${STACK}.timer"

cat >&2 <<EOF

Próximos passos manuais (uma vez):
  1. Postgres do host precisa aceitar conexões da rede docker (listen_addresses e pg_hba.conf
     para 172.16.0.0/12 com scram-sha-256). Ver docs/runbook-ops.md.
  2. docker login ghcr.io (token read:packages) para o deploy puxar imagens.
  3. DNS dos 3 hosts -> IP do prod2; depois: ops/nginx-render.sh ${STACK} e certbot.
EOF
