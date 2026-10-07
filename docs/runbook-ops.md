# Runbook de operação (prod2)

Tudo aqui roda **no prod2 por SSH** (usuário `mayacorp22`), nunca no Windows.

## 1. Primeiro setup de uma stack
```bash
# da sua máquina, uma vez, para ter ops/ e infra/ no servidor (depois o CD faz isso sozinho):
scp -r ops infra mayacorp22@PROD2:/srv/print3d/        # crie /srv/print3d antes: sudo install -d -o mayacorp22 /srv/print3d

# no prod2:
bash /srv/print3d/ops/bootstrap-server.sh staging
```
O script cria diretórios, role + banco `print3d_staging`, extensões (`vector`, `pg_trgm`, `unaccent`), `.env` com `FERNET_KEY` e senha de banco aleatórios, e timers de backup. **Revise o `.env`** (`BASE_DOMAIN`, `REGISTRY`, `CORS_ORIGINS`, chaves de IA). Repita com `prod`.

## 2. Postgres do host acessível pelos containers
- Instale o pgvector do seu Postgres: `sudo apt install postgresql-<versão>-pgvector`.
- `postgresql.conf`: `listen_addresses = 'localhost,172.17.0.1'` (IP da bridge docker0).
- `pg_hba.conf`: `host print3d_staging,print3d_prod print3d_staging,print3d_prod 172.16.0.0/12 scram-sha-256`
- Firewall: porta 5432 **fechada** para a internet.

## 3. Registro de imagens
`docker login ghcr.io -u <usuario>` com token `read:packages` (fica em `~/.docker/config.json`).

## 4. DNS e HTTPS
Aponte para o IP do prod2: `loja`, `admin`, `api` (produção) e `loja-staging`, `admin-staging`, `api-staging` sob `BASE_DOMAIN`.
```bash
bash /srv/print3d/ops/nginx-render.sh staging
sudo certbot --nginx -d loja-staging.DOMINIO -d admin-staging.DOMINIO -d api-staging.DOMINIO --redirect
```

## 5. Secrets no GitHub
`SSH_HOST`, `SSH_USER`, `SSH_KEY` (chave privada dedicada ao deploy), `SSH_KNOWN_HOSTS` (`ssh-keyscan PROD2`).

## Rotina
| Quero... | Comando |
|---|---|
| ver o estado | `bash ops/diagnose.sh staging` |
| testar a stack | `bash ops/smoke.sh staging [--local]` |
| voltar versão | `bash ops/rollback.sh prod` (banco não volta) |
| migração manual | `bash ops/migrate.sh staging current` |
| backup agora | `bash ops/backup.sh prod` |
| testar restauração | `bash ops/restore-test.sh staging` (mensal, automático em staging) |

## Se o deploy falhar
`deploy.sh` volta sozinho para a tag anterior e imprime `compose ps` + logs. Depois: `diagnose.sh`. Migrações já aplicadas ficam — por isso devem ser *expand/contract* (ADR 0005).
