# Dúvidas bloqueantes

Respondidas:
1. ~~Repositório~~ → `github.com/Jeff1984Sor/maya3d`, registro `ghcr.io/jeff1984sor`.
2. ~~Domínio~~ → por enquanto o IP do servidor, em portas dedicadas ([ADR 0007](adr/0007-acesso-por-ip-e-portas-dedicadas.md)).

Em aberto (não bloqueiam a Fase 0; o bootstrap diagnostica):
3. **Versão do Postgres e pgvector no prod2:** o `bootstrap-server.sh` detecta a versão e diz o comando exato de instalação do pgvector se faltar.
4. **Impressoras Bambu (modelo, AMS, fechada?):** necessário na Fase 1 (perfis do fatiador, ADR 0003; ASA exige impressora fechada). Para descobrir: o modelo está na etiqueta ou no app Bambu Handy.
5. **Buckets GCS (arquivos e backups):** sem bucket, backup fica só local e arquivos 3D só no disco. Necessário antes da Fase 1 para armazenar STL/renders.

Pendência nova: **domínio + HTTPS** antes da Fase 3 (callbacks OAuth/webhooks exigem HTTPS) e antes de qualquer login.
