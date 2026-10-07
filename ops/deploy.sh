#!/usr/bin/env bash
# Uso: ops/deploy.sh <staging|prod> <image_tag>
# Fluxo: pull -> migra banco -> sobe stack -> espera healthchecks.
# Se a subida falhar, volta os containers para a tag anterior (o banco NÃO volta:
# migrações devem ser expand/contract, compatíveis com a versão anterior — ver ADR 0005).
set -euo pipefail
SCRIPT_NAME=deploy
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"
IMAGE_TAG="${2:?uso: deploy.sh <stack> <image_tag>}"
load_stack_env
export IMAGE_TAG
confirm_prod

TAG_FILE="${STACK_DIR}/.current_tag"
PREVIOUS_TAG="$(cat "$TAG_FILE" 2>/dev/null || true)"

log "deploy ${STACK} -> ${IMAGE_TAG} (anterior: ${PREVIOUS_TAG:-nenhuma})"
bash "$(dirname "$0")/check-ports.sh" "$STACK"
compose pull

log "migrações"
compose run --rm --no-deps api alembic upgrade head

log "subindo stack"
if ! compose up -d --remove-orphans --wait --wait-timeout 180; then
  log "falha na subida; diagnóstico:"
  compose ps >&2 || true
  compose logs --tail=50 >&2 || true
  if [[ -n "$PREVIOUS_TAG" && "$PREVIOUS_TAG" != "$IMAGE_TAG" ]]; then
    log "rollback automático para ${PREVIOUS_TAG}"
    IMAGE_TAG="$PREVIOUS_TAG" compose up -d --remove-orphans --wait --wait-timeout 180 \
      || log "rollback também falhou — intervenção manual necessária"
  fi
  exit 1
fi

[[ -n "$PREVIOUS_TAG" ]] && echo "$PREVIOUS_TAG" > "${STACK_DIR}/.previous_tag"
echo "$IMAGE_TAG" > "$TAG_FILE"
docker image prune -f --filter "until=168h" >/dev/null
log "deploy concluído: ${STACK}@${IMAGE_TAG}"
