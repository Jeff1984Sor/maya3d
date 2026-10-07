#!/usr/bin/env bash
# Uso: ops/rollback.sh <staging|prod>  — volta containers para a tag anterior (.previous_tag).
set -euo pipefail
SCRIPT_NAME=rollback
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
load_stack_env
confirm_prod

PREVIOUS="$(cat "${STACK_DIR}/.previous_tag" 2>/dev/null || true)"
[[ -n "$PREVIOUS" ]] || die "sem .previous_tag para ${STACK}"
CURRENT="$(cat "${STACK_DIR}/.current_tag" 2>/dev/null || true)"

log "rollback ${STACK}: ${CURRENT} -> ${PREVIOUS} (banco não é revertido)"
IMAGE_TAG="$PREVIOUS" compose up -d --remove-orphans --wait --wait-timeout 180
echo "$PREVIOUS" > "${STACK_DIR}/.current_tag"
echo "$CURRENT" > "${STACK_DIR}/.previous_tag"
