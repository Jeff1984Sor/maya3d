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
| 5 | Produtos e variantes no painel (Guardião automático), catálogo | ✅ v0.5 |
| 6 | Pedidos, fila de impressão por cor/material, tela Produção, aprovação de amostra, caixa de saída | ✅ v0.5 |
| 7 | Loja: catálogo, produto, carrinho, checkout Pix, frete (regra Sorocaba), acompanhamento | ✅ v0.6 (conta/login com domínio) |
| 8 | IA: provedores Claude/OpenAI, tela IA, "✨ Enriquecer" ✅ v0.5 · Redator por canal, busca por significado, assistente da loja ✅ v0.8 · Guardião visual ✅ v0.12 | ✅ |
| 8b | Biblioteca de modelos (acervos enviados pelo painel → organizados, medidos → produto) · paramétricos cruz/placa/lembrancinha/suporte · Integrações no painel | ✅ v0.9 |
| 8c | CMS: fotos de produto, marca (nome/cores/logo), página inicial (aviso, destaque, vitrines) e páginas institucionais no painel | ✅ v0.10 |
| 8d | Frete automático (Melhor Envio): Correios/transportadoras no carrinho e no checkout, recotado no servidor; token em Integrações, CEP de origem em Operação | ✅ v0.11 |
| 8e | Guardião visual: IA olha cada foto (personagem, marca, logo, time, pessoa real, qualidade); bloqueio por regra fixa; dono libera com motivo auditado | ✅ v0.12 |
| 8f | App Android/iOS (Expo SDK 57): início, busca, assistente, produto, carrinho, frete, checkout Pix, pedidos; EAS por tag (contas e domínio para publicar) | ✅ v0.13 |
| 9 | Mercado Livre (OAuth+PKCE, tokens cifrados, prévia com tarifa real, anúncio, pedidos pagos e perguntas por notificação) ✅ v0.14 · Shopee (assinatura HMAC, fotos enviadas à Shopee, push assinado de pedidos) ✅ v0.15 — ligam com domínio | ✅ |
| 9b | Mercado Pago: Pix automático (QR + copia e cola), confirmação por consulta a cada 2 min e por aviso assinado; valor conferido antes de liberar | ✅ v0.16 |
| 10 | Fatiador e renders em containers; CMS; conteúdo/MayaPost; app Expo; Analista | |

## O que o dono pluga depois (e o que acontece)
| Quando tiver... | Faz isto | Ativa |
|---|---|---|
| Impressora | cadastra em Impressoras (status ativa) + perfil do fatiador | gramas/tempo reais, preços reais, fila de impressão |
| Domínio | DNS + `BASE_DOMAIN` + certbot (runbook) | HTTPS, login de clientes, callbacks ML/Shopee/Meta |
| Chave de IA (OpenAI ou Anthropic) | cola em **Integrações** no painel; modelos escolhidos na tela IA | Enriquecer, Redator por canal, assistente da loja; com modelo de embedding (OpenAI), busca por significado |
| WhatsApp Business (Meta) | cola token, ID do número e versão em **Integrações** (webhook precisa de domínio) | avisos, botão Aprovar/Pedir ajuste da amostra, comandos do dono ("1234 enviado", "fila", "vendas") |
| Mercado Livre / Shopee | app nas plataformas + OAuth no painel | publicação e pedidos |
| Mercado Pago | credenciais em **Integrações** (teste: TEST-…) | Pix automático já; cartão e aviso instantâneo com domínio |
| Bucket GCS | `GCS_*` no `.env` | arquivos e backups fora do servidor |
