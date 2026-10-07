# 0001 — Monorepo com uv (Python) e pnpm (Node)

- **Status:** Aceita
- **Data:** 2026-10-07

## Contexto
Backend Python, dois apps Next.js, app Expo futuro e pacotes compartilhados. Desenvolvimento no Windows sem executar nada; tudo roda em CI/prod2.

## Decisão
- **Python:** workspace **uv** (`apps/api`, `apps/worker`, `packages/*`), `ruff` (lint+format), `mypy --strict`, `pytest`. Pacotes com `src/` layout e build `hatchling`.
- **Node:** workspace **pnpm** (`apps/storefront`, `apps/admin`, `packages/shared`); `packages/shared` é consumido como TS-fonte (`transpilePackages`), sem etapa de build.
- Um só repositório, um só pipeline; imagens: `backend` (api+worker), `storefront`, `admin`.

## Alternativas consideradas
- Poetry/pip-tools: sem workspace nativo tão simples.
- Turborepo/Nx: ganho de cache ainda não compensa a complexidade com 3 pacotes Node.
- Repositórios separados: duplicaria tokens, tipos e CI.

## Consequências
Lockfiles (`uv.lock`, `pnpm-lock.yaml`) são gerados no primeiro CI e passam a ser obrigatórios (`--locked`/`--frozen-lockfile`). `apps/mobile` entra no workspace pnpm só na Fase 6.5.
