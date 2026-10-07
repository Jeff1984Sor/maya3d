# 0003 — Fatiador CLI para gramas e tempo reais

- **Status:** Proposta — **validar na Fase 1** (não pesquisado ainda; a spec exige verificar qual CLI é estável hoje)
- **Data:** 2026-10-07

## Contexto
Preço depende de gramas e tempo **reais** do fatiador por perfil de impressora/filamento. Precisa rodar headless em container no prod2, exportar 3MF multicor e extrair métricas.

## Decisão (provisória)
Candidato principal: **OrcaSlicer CLI**; alternativa: Bambu Studio CLI. Ambos acessados só através do contrato `print3d_mesh.Slicer` (`SliceResult`: gramas por cor, segundos, perfil).

## Spike de validação (critérios de aceite, Fase 1)
1. Roda sem display em container Linux; versão fixada na imagem.
2. Aceita perfis exportados dos modelos Bambu do dono (ver [dúvida 4](../duvidas-bloqueantes.md)).
3. Entrega gramas por filamento e tempo de forma parseável (G-code/JSON/3MF metadata).
4. Estabilidade em lote (centenas de fatiamentos) e tempo por peça aceitável.
5. Gera 3MF multicor para AMS e variante com pausa para troca manual.

## Consequências
Se nenhum candidato passar, fallback: estimativa calibrada por regressão sobre fatiamentos reais, marcada como "estimado" — e a spec proíbe chute, então só com aviso explícito.
