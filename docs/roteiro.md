# Roteiro — tudo pronto, só esperando plugar

Decisão do dono (2026-10-07): construir o sistema inteiro agora. Impressora, domínio e contas
externas são **plugados depois por configuração**, sem programar de novo. Cada integração fica
atrás de um Provider, com testes de contrato e estado "não configurado" visível no painel.

## Ordem de construção
| # | Entrega | Estado |
|---|---|---|
| 0 | Infra, CI/CD, backups | ✅ v0.1 |
| 1 | Motor de preço, análise de STL, cadastros, API admin | ✅ v0.2 |
| 2 | Guardião de IP, nichos, licenças, auditoria | ✅ v0.3 |
| 3 | Painel admin com login | ✅ v0.4 |
| 4 | Modelos paramétricos (chaveiro letra+nome, caixas) gerados no worker + armazenamento + visualizador 3D | ✅ v0.5 |
| 5 | Produtos e variantes no painel (Guardião automático), catálogo | |
| 6 | Pedidos, fila de impressão por cor/material, tela Produção, aprovação de amostra | |
| 7 | Loja: catálogo, produto, carrinho, conta, checkout, frete (regra Sorocaba) | |
| 8 | IA: provedor Claude, "✨ Enriquecer", Redator, Guardião visual, busca semântica, assistente | |
| 9 | Mercado Livre e Shopee (OAuth, publicação, pedidos, perguntas) | |
| 10 | Fatiador e renders em containers; CMS; conteúdo/MayaPost; app Expo; Analista | |

## O que o dono pluga depois (e o que acontece)
| Quando tiver... | Faz isto | Ativa |
|---|---|---|
| Impressora | cadastra em Impressoras (status ativa) + perfil do fatiador | gramas/tempo reais, preços reais, fila de impressão |
| Domínio | DNS + `BASE_DOMAIN` + certbot (runbook) | HTTPS, login de clientes, callbacks ML/Shopee/Meta |
| Chave Anthropic | `AI_API_KEY` + `AI_MODEL_*` no `.env` | Enriquecer, Redator, Guardião visual, assistente |
| WhatsApp Business (Meta) | token + número no `.env` | avisos de venda e status de pedido |
| Mercado Livre / Shopee | app nas plataformas + OAuth no painel | publicação e pedidos |
| Gateway de pagamento | chaves no `.env` (ADR 0004) | checkout com cartão/Pix |
| Bucket GCS | `GCS_*` no `.env` | arquivos e backups fora do servidor |
