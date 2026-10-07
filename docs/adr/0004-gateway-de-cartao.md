# 0004 — Gateway de pagamento (cartão) e Pix

- **Status:** Proposta — **decidir antes da Fase 6** (exige pesquisa de tarifas e APIs atuais)
- **Data:** 2026-10-07

## Contexto
Loja própria precisa de Pix com desconto e cartão, com tokenização (nunca guardar dados de cartão), webhooks idempotentes e boa API para Pix. A spec pede avaliar primeiro o banco **Cora** para Pix/boleto.

## Decisão
Tudo atrás de `PaymentProvider`. Escolha do fornecedor adiada para a Fase 6, comparando: (1) Pix/boleto via Cora (API), (2) gateway de cartão com tokenização e split de taxa transparente (candidatos a pesquisar: Mercado Pago, Pagar.me, Stripe, Asaas).

## Critérios
Taxa efetiva por meio de pagamento, prazo de repasse, API de Pix, tokenização/cartão salvo, webhooks assinados, suporte a MEI, qualidade da documentação e sandbox.

## Consequências
Nenhum código de pagamento nas Fases 0–5. O ADR será atualizado com a comparação datada.
