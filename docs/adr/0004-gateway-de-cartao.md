# 0004 — Gateway de pagamento (cartão) e Pix

- **Status:** Aceita (2026-11-13) — Mercado Pago para Pix e cartão; Cora segue como alternativa futura para Pix/boleto
- **Data:** 2026-10-07

## Contexto
Loja própria precisa de Pix com desconto e cartão, com tokenização (nunca guardar dados de cartão), webhooks idempotentes e boa API para Pix. A spec pede avaliar primeiro o banco **Cora** para Pix/boleto.

## Decisão
Tudo atrás de `PaymentProvider`. Escolha do fornecedor adiada para a Fase 6, comparando: (1) Pix/boleto via Cora (API), (2) gateway de cartão com tokenização e split de taxa transparente (candidatos a pesquisar: Mercado Pago, Pagar.me, Stripe, Asaas).

## Critérios
Taxa efetiva por meio de pagamento, prazo de repasse, API de Pix, tokenização/cartão salvo, webhooks assinados, suporte a MEI, qualidade da documentação e sandbox.

## Consequências
Nenhum código de pagamento nas Fases 0–5. O ADR será atualizado com a comparação datada.

## Atualização 2026-11-13
Mercado Pago em produção para **Pix** (QR + webhook assinado + consulta a cada 2 min) e **cartão**
(Card Payment Brick: o número do cartão fica no Mercado Pago; o servidor recebe só o token e cobra o
total do pedido calculado aqui, com a tarifa do canal `site_card`). Ambos pela API de Payments, que o
Mercado Pago mantém mas não evolui mais; a migração para a API de Orders fica registrada como pendência.
