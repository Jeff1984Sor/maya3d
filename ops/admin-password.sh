#!/usr/bin/env bash
# Uso: ops/admin-password.sh <staging|prod>
# Troca a senha do painel: pede a nova duas vezes (sem mostrar), grava no .env da stack,
# gera um novo segredo de sessão (derruba quem estava logado) e reinicia só o painel.
set -euo pipefail
export SCRIPT_NAME=admin-password
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
[[ -t 0 ]] || die "rode num terminal: a senha é digitada sem aparecer"
confirm_prod

read -r -s -p "Nova senha do painel: " NEW; echo >&2
read -r -s -p "Repita a nova senha: " AGAIN; echo >&2
[[ "$NEW" == "$AGAIN" ]] || die "as senhas não conferem"
(( ${#NEW} >= 10 )) || die "use ao menos 10 caracteres"
[[ "$NEW" != *"'"* && "$NEW" != *$'\n'* ]] || die "a senha não pode ter aspas simples (')"

SECRET="$(openssl rand -hex 32)"
umask 077
TMP="$(mktemp "${STACK_ENV_FILE}.XXXX")"
# grava entre aspas simples: o .env é lido pelo bash (ops) e pelo docker compose
NEW="$NEW" SECRET="$SECRET" awk '
  BEGIN { p = "ADMIN_PASSWORD='\''" ENVIRON["NEW"] "'\''"; s = "ADMIN_SESSION_SECRET=" ENVIRON["SECRET"] }
  /^ADMIN_PASSWORD=/ { print p; fp = 1; next }
  /^ADMIN_SESSION_SECRET=/ { print s; fs = 1; next }
  { print }
  END { if (!fp) print p; if (!fs) print s }
' "$STACK_ENV_FILE" > "$TMP"
cp -p "$STACK_ENV_FILE" "${STACK_ENV_FILE}.bak"
mv "$TMP" "$STACK_ENV_FILE"
unset NEW AGAIN SECRET

load_stack_env
IMAGE_TAG="$(cat "${STACK_DIR}/.current_tag" 2>/dev/null || true)"
[[ -n "$IMAGE_TAG" ]] || die "sem ${STACK_DIR}/.current_tag: rode um deploy antes"
export IMAGE_TAG
compose up -d --no-deps --wait --wait-timeout 120 admin
rm -f "${STACK_ENV_FILE}.bak"
log "senha do painel (${STACK}) trocada; quem estava logado precisa entrar de novo"
