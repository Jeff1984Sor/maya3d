# Fase 2 — Catálogo autônomo de 720+ peças (9 nichos)

**DoD (spec):** catálogo com 720+ produtos distribuídos conforme a tabela 2.8, todos com licença válida, renders, preço e textos; relatório de bloqueados com motivos.

## Parte A — entregue (2026-10-07, v0.3.0)
- **Guardião de IP — etapa de regras** (`packages/core/guardian`), determinística e sem IA:
  - licença (só CC0, CC BY com atribuição, comercial ou paramétrico próprio; NC/SA/ND/uso pessoal/desconhecida → bloqueia)
  - franquias e personagens, marcas famosas, times (liberáveis por `License` vigente no canal/categoria)
  - religioso: Cristo Redentor (exige licença), papas, logo de santuário/diocese, deboche
  - automotivo: peças de segurança, marca só como "compatível com", nada de "original/oficial" nem emblema, material mínimo (PLA nunca; sol → ASA)
  - fitness: peças de carga (com exceções para chaveiro/miniatura/medalha), PETG em ambiente úmido
  - fogo (só vela LED), formas de alimento, recipiente sem "embalados", "brinquedo", minifiguras, palavrões, nomes que lembram franquia de cachorrinhos
  - avisos obrigatórios (ímã, cortador, vela LED, impressão 3D no religioso, "não é brinquedo" + 14+)
  - anti-evasão: acentos, caixa, hífen, letras soletradas, leetspeak, plural; sem casar pedaço de palavra
- **Evals no CI:** 31 casos que DEVEM bloquear + 20 que DEVEM passar (lista da spec incluída).
- **Banco (migração 0003):** `niches` (semente dos 9 nichos, soma 720, voz por nicho), `licenses`, `guardian_term_overrides`, `audit_log`.
- **API admin:** `POST guardian/check` (registra na auditoria), `GET audit` (tela de bloqueados, só consulta), CRUD `niches`, `licenses`, `guardian/terms`. Mudança de custos também é auditada.

## Parte B — pendente
- [ ] Guardião visual: modelo multimodal analisa renders (logo, personagem, pessoa real) — depende de renders (Fase 1B) e chave de IA
- [ ] Agentes Curador, Designer paramétrico, Catalogador, Redator, Fotógrafo
- [ ] Personalizador de chaveiros letra+nome, gerador de caixas e configurador
- [ ] Compatibilidade veicular (marca → modelo → ano) e modelos de celular
- [ ] Deduplicação (embeddings + hash geométrico)
- [ ] Liberação automática de produtos por material mínimo quando houver impressora capaz (função `material_available` pronta)
