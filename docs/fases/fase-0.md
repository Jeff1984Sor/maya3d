# Fase 0 — Fundação e CI/CD sem rodar nada localmente

**DoD:** um push na main sobe API + admin + storefront "hello" em staging com HTTPS, e o pipeline fica verde.

Legenda: ✅ escrito no repositório · ⏳ depende de ação no GitHub/servidor · ❌ não feito.
**Nada abaixo foi executado ainda** (regra: nada roda no Windows). A validação acontece no primeiro push.

## Código e repositório
- ✅ Monorepo: workspace uv (Python) + pnpm (Node), `packages/*`, `apps/*`
- ✅ API FastAPI: config, logs JSON, request-id, health live/ready, `GET /v1/brand`
- ✅ Banco: SQLAlchemy 2 async, Alembic, migração 0001 (pgvector, pg_trgm, unaccent, `brand_settings` com semente neutra)
- ✅ Worker arq: `ping`, heartbeat por minuto, healthcheck de container
- ✅ Storefront e admin "hello" lendo a marca da API, tema por tokens (5.1), `/api/health`
- ✅ `core` (nichos 720, canais, TokenVault Fernet) e contratos de provedor (`ai`, `channels`, `notify`, `mesh`, `social`)
- ✅ Guarda `tools/check_brand.py` (marca fixa quebra o CI)

## Infra e CI/CD
- ✅ Dockerfiles (backend único para api+worker; web por `APP`)
- ✅ Compose único parametrizado por stack; Nginx por template; scripts `/ops` (deploy, rollback, migrate, smoke, diagnose, backup, restore-test, bootstrap, nginx-render) e timers systemd
- ✅ GitHub Actions: `ci.yml` (guards, backend com Postgres+pgvector, frontend), `cd.yml` (build GHCR → staging+smoke → produção por tag/manual/auto)

## Ações do dono (uma vez)
- ⏳ Criar repo no GitHub e fazer o primeiro push
- ⏳ Secrets do repo: `SSH_HOST`, `SSH_USER` (`mayacorp22`), `SSH_KEY`, `SSH_KNOWN_HOSTS`; environments `staging` e `production` (este com revisor obrigatório, se quiser aprovação)
- ⏳ Variável opcional `AUTO_PROMOTE_PROD=true` para promoção automática da main
- ⏳ No prod2: seguir [runbook-ops.md](../runbook-ops.md) (bootstrap, pgvector no host, DNS, certbot)
- ⏳ Primeiro CI: commitar `uv.lock` e `pnpm-lock.yaml` gerados (o 1º CI publica ambos como artefatos `uv-lock` e `pnpm-lock`; baixe e commite)
- ⏳ Ajustar `REGISTRY`, `BASE_DOMAIN`, `CORS_ORIGINS` nos `.env` das stacks

## Riscos conhecidos (olhar primeiro se o CI falhar)
- Tipagem estrita do mypy/ruff não foi rodada: ajustes pequenos esperados no 1º CI.
- `web.Dockerfile`: caminho do `server.js` standalone em monorepo (`apps/<app>/server.js`) precisa ser conferido no 1º build.
- Postgres do host precisa aceitar conexões da rede docker (runbook, passo 2).
