# 0005 — Topologia de deploy e política de migrações

- **Status:** Aceita
- **Data:** 2026-10-07

## Contexto
Um único servidor (prod2, GCP) com Postgres já instalado no host. Staging e produção precisam coexistir, isolados.

## Decisão
- **Uma stack docker compose por ambiente** (`name: print3d-<stack>`), **mesmo arquivo** `infra/compose/docker-compose.yml`, parametrizado por `infra/compose/env/<stack>.env` (público) + `/srv/print3d/<stack>/.env` (segredos).
- Portas só em `127.0.0.1` (staging 13000/13001/18000; prod 3000/3001/8000). **Nginx** no host termina TLS (Let's Encrypt/certbot) e faz proxy por subdomínio: `loja|admin|api[-staging].BASE_DOMAIN`.
- **Postgres no host**, um banco/role por stack; extensões `vector`, `pg_trgm`, `unaccent`. **Redis por stack** dentro do compose.
- **Imagens** construídas no CI e publicadas no GHCR com tag imutável (`sha-xxxxxxx` ou `vX.Y.Z`); **a mesma imagem** vai de staging para produção (frontends sem `NEXT_PUBLIC_*`: falam com a API via `API_INTERNAL_URL` no servidor).
- **Fluxo:** push main → CI → build → deploy staging (`ops/deploy.sh`) → smoke → produção (tag `v*`, ou manual, ou automática com `AUTO_PROMOTE_PROD=true`).
- **Migrações expand/contract:** o deploy migra *antes* de subir o código novo, e o rollback volta só containers. Logo, toda migração precisa ser compatível com a versão anterior (adicionar → migrar dados → remover em release posterior). Nada de `DROP`/renomear coluna no mesmo release do código que a abandona.

## Alternativas consideradas
Kubernetes/Cloud Run (custo e complexidade desnecessários para 1 VM); Postgres em container (o do host já existe e tem backup).

## Consequências
Ponto único de falha (1 VM) aceito nesta fase; backups diários + teste mensal de restauração mitigam. Postgres do host precisa aceitar a rede docker (runbook).
