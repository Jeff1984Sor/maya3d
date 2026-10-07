# Troca de marca

A identidade vive na tabela `brand_settings` (uma linha, editável no admin quando a tela existir; até lá, via SQL em staging/prod por SSH). Frontends, e-mails, prompts da IA e geradores leem dali. O CI (`tools/check_brand.py`) impede nome de marca fixo no código.

## O que muda sozinho
Nome, slogan, logos, favicon, cores (claro/escuro), fontes, contatos, redes, CNPJ/razão social e voz da marca por nicho.

## O que NÃO muda sozinho (checklist manual)
| Item | Passo |
|---|---|
| Domínio e subdomínios | DNS + `BASE_DOMAIN` no `.env` + `ops/nginx-render.sh <stack> --force` + certbot |
| Nome do app nas lojas Apple/Google | Ajustar em App Store Connect / Play Console (Fase 6.5) |
| Templates de WhatsApp aprovados | Reenviar para aprovação na Meta com o novo nome |
| Loja no Mercado Livre / Shopee | Alterar nome da loja nos painéis dos canais |
| Remetente de e-mail / SPF / DKIM | Configurar no provedor de e-mail |
| Slugs técnicos (`print3d`, repo, bancos, containers) | **Não mudam** — neutros de propósito |

## Passo a passo rápido
1. Atualizar `brand_settings` (nome, logos, cores...).
2. Aguardar o cache (60 s) ou reiniciar a API.
3. Percorrer a tabela acima.
