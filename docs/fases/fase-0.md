# Fase 0 — Fundação e CI/CD sem rodar nada localmente

**DoD:** um push na main sobe API + admin + storefront "hello" em staging com HTTPS, e o pipeline fica verde.

**Status: concluída em 2026-10-07**, com um desvio aceito: **sem HTTPS** até existir domínio ([ADR 0007](../adr/0007-acesso-por-ip-e-portas-dedicadas.md)).

## Evidência
- CD run `37621625666` (commit `7600f28`): CI (guardas, backend com Postgres+pgvector, frontend) → build das 3 imagens → deploy staging → smoke, tudo verde.
- Staging no ar: loja `http://2.25.130.240:38001`, admin `:38002`, API `:38000` (`/health/ready` com banco e redis ok, `/v1/brand` servindo a marca do banco).

## Entregue
- Monorepo uv + pnpm; API FastAPI (health, marca, logs JSON, request-id); Alembic 0001 (pgvector, pg_trgm, unaccent, `brand_settings`); worker arq com heartbeat; storefront e admin lendo a marca da API.
- `core` (nichos, canais, TokenVault) e contratos de provedores (`ai`, `channels`, `notify`, `mesh`, `social`).
- Infra: Dockerfiles, compose único por stack, portas dedicadas, Postgres do host via socket Unix, scripts `/ops` e timers de backup/restauração.
- CI/CD: `ci.yml` + `cd.yml`, deploy por SSH com rollback automático, guarda de marca.

## Pendências herdadas
- [x] Trocar a senha do banco de staging (vazou em log durante o bootstrap; script corrigido; trocada em 2026-10-07).
- [ ] Commitar `pnpm-lock.yaml` (artefato `pnpm-lock` do CI).
- [x] Bootstrap da stack de produção e primeira promoção: **v0.1.0 em produção** (2026-10-07), deploy feito no servidor com `ops/deploy.sh prod v0.1.0`.
- [ ] Domínio + HTTPS (obrigatório antes de login, checkout e Fase 3).
- [ ] Restringir portas de staging/admin ao seu IP (regras `DOCKER-USER`; o Docker ignora o ufw).
