# 0007 — Acesso por IP e portas dedicadas (temporário)

- **Status:** Aceita — **emenda a topologia do ADR 0005** até existir um domínio
- **Data:** 2026-10-07

## Contexto
Ainda não há domínio: o acesso é pelo IP do servidor. O prod2 já hospeda vários outros serviços, então não podemos ocupar portas comuns (80/443/3000/8000...) nem assumir um Nginx exclusivo nosso.

## Decisão
- Sem Nginx e sem HTTPS por enquanto. Cada serviço é publicado direto em porta alta dedicada: **staging 38000 (api), 38001 (storefront), 38002 (admin); produção 39000/39001/39002**. Redis nunca é publicado.
- `BIND_ADDR=0.0.0.0` nos `env/<stack>.env` para acesso externo; as portas precisam ser liberadas no firewall do GCP (somente essas 6).
- `ops/check-ports.sh` roda antes de todo deploy e aborta se outro serviço ocupar a porta (ignora a própria stack já em execução).
- `BASE_DOMAIN` vazio = modo IP (`PUBLIC_HOST` + portas); quando houver domínio, preencher `BASE_DOMAIN`, usar `ops/nginx-render.sh` + certbot e fechar `BIND_ADDR` para `127.0.0.1`.

## Consequências
- Tráfego em **HTTP puro**: aceitável para o "hello" da Fase 0, **inaceitável** para login, checkout e admin com dados reais. Obter domínio + HTTPS é pré-requisito da Fase 5/6 (e já para qualquer tela de login do admin).
- Restrinja no firewall do GCP as portas de **staging e do admin** ao seu IP, se possível.
- Callbacks OAuth/webhooks (Mercado Livre, Shopee, Meta) normalmente exigem URL HTTPS: a Fase 3 depende do domínio.
