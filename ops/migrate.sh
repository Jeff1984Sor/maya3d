#!/usr/bin/env bash
# Uso: ops/migrate.sh <staging|prod> [alembic args...]   (padrão: upgrade head)
# Ex.: ops/migrate.sh staging current
set -euo pipefail
SCRIPT_NAME=migrate
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"

require_stack "${1:-}"; shift || true
load_stack_env
IMAGE_TAG="$(cat "${STACK_DIR}/.current_tag" 2>/dev/null || true)"
[[ -n "$IMAGE_TAG" ]] || die "stack ${STACK} nunca recebeu deploy"
export IMAGE_TAG

# downgrade pode destruir dados: pede confirmação em prod
[[ "${*}" == *downgrade* ]] && confirm_prod

if [[ $# -eq 0 ]]; then set -- upgrade head; fi
compose run --rm --no-deps api alembic "$@"
