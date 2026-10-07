# Dúvidas bloqueantes (máx. 5)

Não impedem o código da Fase 0, mas impedem **ativar** staging e começar a Fase 1.

1. **Repositório e registro:** o repositório GitHub já existe? Qual usuário/org (define `REGISTRY` em `ghcr.io/...`)?
2. **Domínio:** qual domínio base vai nos subdomínios `loja/admin/api` (e `-staging`)? O DNS está sob seu controle?
3. **Postgres do prod2:** qual versão, e o pacote pgvector pode ser instalado no host? (Sem ele a migração 0001 falha.)
4. **Impressoras:** quais modelos Bambu Lab (com AMS? fechada?) — define perfis do fatiador, materiais disponíveis (ASA exige fechada) e o ADR 0003.
5. **Bucket GCS:** já existe um bucket para arquivos (STL/renders) e outro para backups, e a VM tem permissão (service account)?
