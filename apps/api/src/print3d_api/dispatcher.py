"""Despachante da caixa de saída: roda dentro da API enquanto o WhatsApp estiver configurado.

Ciclo curto (ou na hora, quando o webhook gera resposta). SKIP LOCKED no serviço evita envio
duplicado se houver mais de um processo da API.
"""

import asyncio
import contextlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from print3d_api.services.whatsapp import dispatch_pending
from print3d_notify import NotifyProvider

log = logging.getLogger("print3d.dispatcher")


async def run_dispatcher(
    factory: async_sessionmaker[AsyncSession],
    provider: NotifyProvider,
    wake: asyncio.Event,
    interval: float = 20.0,
) -> None:
    while True:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(wake.wait(), timeout=interval)
        wake.clear()
        try:
            async with factory() as session:
                while await dispatch_pending(session, provider) > 0:
                    pass
        except Exception:  # banco fora etc.: tenta no próximo ciclo
            log.exception("falha no despachante")
