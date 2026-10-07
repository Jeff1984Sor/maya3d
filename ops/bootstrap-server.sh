#!/usr/bin/env bash
# Uso (no prod2, uma vez por stack): ops/bootstrap-server.sh <staging|prod>
# Idempotente. Cria diretórios, banco + extensões, .env com segredos aleatórios
# e instala os timers de backup. NÃO apaga nada e NÃO sobrescreve .env existente.
set -euo pipefail
export SCRIPT_NAME=bootstrap
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
      -e "s#^ADMIN_API_TOKEN=.*#ADMIN_API_TOKEN=$(openssl rand -hex 32)#" \
      "$(dirname "$0")/../infra/compose/env/server.env.example" > "${STACK_DIR}/.env"
  # modo IP (ADR 0007): detecta o IP externo (metadata do GCP) e monta o CORS com as portas da stack
  # shellcheck disable=SC1090
  source "$(dirname "$0")/../infra/compose/env/${STACK}.env"
  EXT_IP="$(curl -4 -fsS --max-time 5 https://ifconfig.me 2>/dev/null || true)"
  if [[ -n "$EXT_IP" ]]; then
    sed -i -e "s#^PUBLIC_HOST=.*#PUBLIC_HOST=${EXT_IP}#" \
      -e "s#^CORS_ORIGINS=.*#CORS_ORIGINS=[\"http://${EXT_IP}:${STOREFRONT_PORT}\",\"http://${EXT_IP}:${ADMIN_PORT}\"]#" \
      "${STACK_DIR}/.env"
  else
    log "IP externo não detectado: preencha PUBLIC_HOST e CORS_ORIGINS em ${STACK_DIR}/.env"
  fi
  # senha também fica disponível para o passo de criação do role abaixo
  printf '%s' "$DB_PASS" > "${STACK_DIR}/.dbpass.tmp"
  log "EDITE ${STACK_DIR}/.env: BASE_DOMAIN, REGISTRY, CORS_ORIGINS, chaves de IA"
fi

if sudo -u postgres psql -Atc "select 1 from pg_database where datname='${DB}'" | grep -q 1; then
  log "banco ${DB} já existe"
else
  [[ -f "${STACK_DIR}/.dbpass.tmp" ]] || die "banco não existe e não há senha gerada; crie manualmente"
  log "criando role e banco ${DB}"
  # SQL via stdin: a senha nunca aparece na linha de comando (o sudo grava argv no auth.log)
  printf "CREATE ROLE %s LOGIN PASSWORD '%s';\nCREATE DATABASE %s OWNER %s;\n" \
    "$ROLE" "$(cat "${STACK_DIR}/.dbpass.tmp")" "$DB" "$ROLE" \
    | sudo -u postgres psql -v ON_ERROR_STOP=1 -q
fi
rm -f "${STACK_DIR}/.dbpass.tmp"

PGMAJOR="$(sudo -u postgres psql -Atc "show server_version_num" | cut -c1-2)"
sudo -u postgres psql -Atc "select 1 from pg_available_extensions where name='vector'" | grep -q 1 \
  || die "pgvector ausente no Postgres ${PGMAJOR}: sudo apt install postgresql-${PGMAJOR}-pgvector (e rode de novo)"
log "extensões (exige pacote postgresql-<versão>-pgvector instalado no host)"
for ext in vector pg_trgm unaccent; do
  sudo -u postgres psql -d "$DB" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS ${ext}"
done

log "timers de backup (systemd)"
for unit in "$(dirname "$0")"/systemd/*.service "$(dirname "$0")"/systemd/*.timer; do
  # o usuário dos serviços é quem executa o bootstrap (deploy, mayacorp22...), não um nome fixo
  sed "s/^User=.*/User=${USER}/" "$unit" | sudo tee "/etc/systemd/system/$(basename "$unit")" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now "print3d-backup@${STACK}.timer"
[[ "$STACK" == "staging" ]] && sudo systemctl enable --now "print3d-restore-test@${STACK}.timer"

cat >&2 <<EOF

Próximos passos manuais (uma vez):
  1. pg_hba.conf do host precisa de uma linha 'local' com scram-sha-256 para os roles print3d_*
     (os containers usam o socket Unix). Ver docs/runbook-ops.md, seção 2.
  2. docker login ghcr.io (token read:packages) para o deploy puxar imagens.
  3. DNS dos 3 hosts -> IP do prod2; depois: ops/nginx-render.sh ${STACK} e certbot.
EOF
