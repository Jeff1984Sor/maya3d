# 0002 — Fila de jobs: arq (+ cron do próprio arq)

- **Status:** Aceita
- **Data:** 2026-10-07

## Contexto
Jobs pesados (render, fatiamento, publicação, IA) e rotinas periódicas. Redis já faz parte da stack.

## Decisão
**arq** (asyncio, Redis) para jobs e `cron_jobs` do arq para rotinas periódicas. Evita um segundo agendador (APScheduler) até haver necessidade comprovada. Saúde do worker: heartbeat no Redis a cada minuto, verificado pelo healthcheck do container.

## Alternativas consideradas
- **Celery:** mais maduro e com mais recursos (canvas, rate limit nativo), porém síncrono por padrão e mais pesado; só se o arq faltar algo concreto.
- **APScheduler:** dispensável enquanto o cron do arq bastar.

## Consequências
Código de job é `async`. Tarefas CPU-bound longas (Blender, fatiador) rodam como subprocesso/container dedicado chamado pelo job, não dentro do loop. Reavaliar se precisarmos de prioridades/filas múltiplas complexas.
