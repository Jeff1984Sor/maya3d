# Fase 1 — Núcleo 3D e precificação

**DoD (spec):** cadastro de um paramétrico gera variantes com renders, gramas e preço de cada canal, visíveis no admin; testes do pricing engine com casos reais.

A impressora ainda não foi comprada, então a fase foi dividida. A parte A não depende de máquina.

## Parte A — entregue (2026-10-07, commit `cc241f9`, staging)
- **Motor de preço** (`packages/core/pricing.py`): custo pela fórmula da spec (falha só sobre custo direto; embalagem/insumos à parte) e preço por canal "de trás pra frente" com **faixas de tarifa** (resolve taxa fixa que depende do preço), arredondamento `,90` com reconferência de lucro após o arredondamento. Tarifas nunca no código.
- **Análise de malha** (`packages/mesh/analysis.py`): medidas, volume, área, malha fechada, unidade suspeita, encaixe na mesa em qualquer orientação.
- **Banco (migração 0002):** `materials`, `printers`, `packaging_boxes`, `cost_config` (semente conservadora), `channel_fee_bands`, `designs`, `products`, `variants`.
- **API de admin** `/v1/admin/*` protegida por `X-Admin-Token` (sem token configurado = 503):
  - CRUD: `materials` (com `low_stock`), `printers`, `packaging`, `channel-fees`
  - `cost-config` (GET/PUT)
  - `pricing/quote`: custo detalhado + preço/lucro por canal, avisos (material incompatível, ASA sem impressora fechada)
  - `mesh/analyze`: upload STL/OBJ/PLY → relatório + em quais impressoras cabe
- **Testes:** 63 unitários + integração com Postgres no CI (CRUD, cotação ponta a ponta, upload de STL).

## Parte B — pendente (depende da impressora / decisões)
- [ ] Fatiador CLI (ADR 0003) → gramas e tempo reais por variante (`slicing_source = fatiador`)
- [ ] 10 modelos paramétricos + geração de variações
- [ ] Renders Blender (fundo branco + cada cor)
- [ ] Telas do admin: produto (abas 5.5), material, impressora, embalagem, custos, com "✨ Enriquecer com IA"
- [ ] Tarifas reais de ML/Shopee via API (Fases 3/4) — até lá, cadastro manual em `channel-fees`

## Decisões
- Sem impressora fixa no código: a máquina é cadastro (`printers`, status `planejada` permitido).
- Embedding de produto adiado para a Fase 6 (dimensão depende do modelo escolhido).
- Admin via token estático até haver login + HTTPS; token nunca vai para o navegador (o painel Next chamará a API pelo servidor).
