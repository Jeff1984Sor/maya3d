"""Despachante da caixa de saída: roda dentro da API e envia quando o WhatsApp estiver
configurado (no painel Integrações ou no .env). Lê a configuração a cada ciclo: colou a chave
no painel, começa a enviar sem reiniciar nada.

SKIP LOCKED no serviço evita envio duplicado se houver mais de um processo da API.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from print3d_api.services import integrations
from print3d_api.services.whatsapp import dispatch_pending
from print3d_notify import NotifyProvider
from print3d_notify.meta import MetaWhatsAppProvider, WhatsAppSettings

log = logging.getLogger("print3d.dispatcher")
ProviderFactory = Callable[[WhatsAppSettings], NotifyProvider]


async def run_dispatcher(
    factory: async_sessionmaker[AsyncSession],
    base: WhatsAppSettings,
    wake: asyncio.Event,
    interval: float = 20.0,
    provider_factory: ProviderFactory = MetaWhatsAppProvider,
) -> None:
    while True:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(wake.wait(), timeout=interval)
        wake.clear()
        try:
            async with factory() as session:
                wa = await integrations.whatsapp_settings(session, base)
                if not wa.configured:
                    continue
                provider = provider_factory(wa)
                while await dispatch_pending(session, provider) > 0:
                    pass
        except Exception:  # banco fora etc.: tenta no próximo ciclo
            log.exception("falha no despachante")
