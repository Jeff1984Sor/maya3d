# CLAUDE.md — memória do projeto

Plataforma de impressão 3D com IA (9 nichos, 720+ peças, ML + Shopee + loja própria + apps).
Especificação completa: [docs/especificacao/prompt-impressao3d.md](docs/especificacao/prompt-impressao3d.md) — **leia a seção relevante antes de implementar uma fase**.

## Regras inegociáveis
1. **Nada roda no Windows.** Editar → commit → push → GitHub Actions (CI) → staging no prod2 → smoke → produção. Execução manual só por SSH no prod2 com scripts versionados em `/ops`.
2. **Ação destrutiva em produção: pare e peça confirmação** (drop, delete em massa, reset de tokens, apagar anúncios). `ops/*` já exigem `confirm_prod`.
3. **Marca nunca fixa no código** (tabela `brand_settings`). `tools/check_brand.py` quebra o CI se aparecer. Slugs técnicos usam `print3d`.
4. **Tarifas de marketplace nunca no código** (API do canal ou tabela `ChannelFee`). **Modelos de IA nunca no código** (env `AI_MODEL_*`).
5. **Pesquise a documentação oficial atual** antes de qualquer integração externa (ML, Shopee, Meta, Melhor Envio, gateway, Bambu).
6. Tudo que fala com serviço externo fica atrás de um **Provider** (Protocol em `packages/*`).
7. Segredos só em `/srv/print3d/<stack>/.env` e GitHub Secrets; tokens de terceiros cifrados com Fernet (`print3d_core.TokenVault`).
8. Migrações **expand/contract** (compatíveis com a versão anterior; rollback não reverte banco) — ADR 0005.
9. Gramas/tempo/medidas vêm do pipeline 3D, a IA nunca inventa números.

## Mapa do repositório
| Caminho | O que é |
|---|---|
| `apps/api` | FastAPI (rotas, modelos SQLAlchemy, migrações Alembic em `migrations/`) |
| `apps/worker` | jobs arq (heartbeat/ping hoje) |
| `apps/storefront`, `apps/admin` | Next.js 15 + Tailwind 4 (tokens em `packages/shared`) |
| `apps/mobile` | Expo — só na Fase 6.5 (README de plano) |
| `packages/core` | nichos, canais, TokenVault |
| `packages/{ai,channels,notify,mesh,social}` | contratos (Protocols) dos provedores |
| `packages/shared` | TS: tokens, tema seguro da marca, cliente da API |
| `infra/` | Dockerfiles, compose (staging/prod com o mesmo arquivo), Nginx |
| `ops/` | scripts do prod2: deploy, rollback, migrate, smoke, backup, diagnose, bootstrap |
| `tools/` | guardas de CI (check_brand) |
| `docs/` | ADRs, fases, runbook, troca de marca, spec |

## Comandos (todos no CI ou no prod2 — nunca no Windows)
- Backend: `uv sync --all-packages --group dev` · `ruff check .` · `ruff format --check .` · `mypy ...` · `pytest` (`RUN_DB_TESTS=1` só no CI, com Postgres+pgvector).
- Frontend: `pnpm install` · `pnpm lint|typecheck|test|build`.
- Servidor: `bash ops/deploy.sh <staging|prod> <tag>` · `ops/smoke.sh` · `ops/diagnose.sh` · `ops/rollback.sh`.
- Nova migração: gerar no CI/SSH (`ops/migrate.sh`), nomear `AAAAMMDD_NNNN_slug.py`, `alembic check` deve passar.

## Estado das fases
| Fase | Estado |
|---|---|
| 0 Fundação e CI/CD | **Concluída em 2026-10-07** (staging no ar por IP, sem HTTPS — ADR 0007) — ver [docs/fases/fase-0.md](docs/fases/fase-0.md) |
| 1 Núcleo 3D e precificação | **Parte A entregue** (motor de preço, análise de STL, cadastros, API admin). Parte B aguarda impressora — ver [docs/fases/fase-1.md](docs/fases/fase-1.md) |
| 2 Catálogo autônomo | **Parte A entregue** (Guardião de regras + evals, nichos, licenças, auditoria) — ver [docs/fases/fase-2.md](docs/fases/fase-2.md) |
| 3–8 | não iniciadas |

## Decisões abertas / pendências
- ADR 0003 (fatiador) e 0004 (gateway de cartão): propostos, a validar — ver `docs/adr/`.
- Servidor: `srv1703721` (IP 2.25.130.240), usuário `deploy`, raiz `/srv/print3d`. Outros serviços rodam lá: usar só as portas 38000–38002 (staging) e 39000–39002 (prod). Postgres 16 do host via socket Unix.
- `uv.lock` e `pnpm-lock.yaml` commitados (CI usa `--locked`/`--frozen-lockfile`).
- Painel admin (v0.4.0): login por `ADMIN_PASSWORD` (no `.env` de cada stack), sessão HMAC; o token da API (`ADMIN_API_TOKEN`) nunca vai ao navegador. Cadastros simples são gerados de `apps/admin/src/lib/resources.ts` (campo novo na API = uma linha lá).
- Checagem local permitida: `npx pnpm@9.15.0 -r typecheck|lint|test` (o `next build` local falha só por symlink do Windows no standalone; no CI passa).
- Produção no ar: v0.1.0 (loja :39001, admin :39002, API :39000). Domínio + HTTPS antes da Fase 3.
- O dono não usa a interface do GitHub. Produção **sem aprovação manual** (autorizado em 2026-10-07): para publicar, criar e enviar uma tag `vX.Y.Z` daqui; o CD passa por CI → staging + smoke → prod. Acompanhar via API pública do GitHub (limite de 60 consultas/h) ou testando as portas.
- Lint/testes locais são permitidos só como análise estática (`uv run python -m pytest`, ruff, mypy, shellcheck); nada de servidor/app no Windows.
- Dúvidas bloqueantes para o dono: [docs/duvidas-bloqueantes.md](docs/duvidas-bloqueantes.md).
