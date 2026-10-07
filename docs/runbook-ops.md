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
Os containers falam com o Postgres pelo **socket Unix** (`/var/run/postgresql` montado no container): não precisa mudar `listen_addresses` nem reiniciar o Postgres, e nada de rede é exposto. Basta uma linha em `pg_hba.conf`, inserida **antes** das demais `local`, e `reload`:
```bash
HBA=/etc/postgresql/16/main/pg_hba.conf
sudo cp "$HBA" "$HBA.bak-print3d"
sudo sed -i '0,/^local[[:space:]]/s//local   print3d_staging,print3d_prod   print3d_staging,print3d_prod   scram-sha-256\n&/' "$HBA"
sudo -u postgres psql -c "select pg_reload_conf()"      # reload: não derruba conexões dos outros serviços
```
A linha só vale para os roles/bancos `print3d_*`; os outros serviços continuam como estavam. Para desfazer: restaurar o `.bak-print3d` e dar reload.

## 3. Registro de imagens
`docker login ghcr.io -u <usuario>` com token `read:packages` (fica em `~/.docker/config.json`).

## 4. Acesso por IP e firewall (modo atual, ADR 0007)
Sem domínio: `PUBLIC_HOST` = IP externo (o bootstrap detecta). Portas: **staging 38000/38001/38002, prod 39000/39001/39002**.
```bash
bash /srv/print3d/ops/check-ports.sh staging     # confirma que nenhum outro serviço usa as portas
gcloud compute firewall-rules create print3d-staging --allow tcp:38000-38002 --source-ranges SEU_IP/32
```
Se alguma porta estiver ocupada, troque em `infra/compose/env/<stack>.env` e commite. Acesso é HTTP puro: não coloque dados reais nem login até haver domínio + HTTPS.

**Quando houver domínio:** preencher `BASE_DOMAIN`, DNS (`loja|admin|api` e `-staging`), `ops/nginx-render.sh <stack>`, `certbot --nginx ...`, e mudar `BIND_ADDR=127.0.0.1`.

## 5. Secrets no GitHub
`SSH_HOST`, `SSH_USER`, `SSH_KEY` (chave privada dedicada ao deploy), `SSH_KNOWN_HOSTS` (`ssh-keyscan PROD2`).

## Rotina

> O CD faz um deploy por vez em cada ambiente (filas `deploy-staging` e `deploy-prod`): push na main e tag ao mesmo tempo não colidem mais.
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
