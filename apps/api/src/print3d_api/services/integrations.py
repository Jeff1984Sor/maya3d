"""Integrações configuradas pelo painel: chave de IA, WhatsApp da Meta etc.

O dono cola as chaves na tela Integrações; ficam no banco cifradas com Fernet (a FERNET_KEY
é criada pelo bootstrap do servidor). Ordem de precedência: painel > .env > padrão.
"""

import logging
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AISettings
from print3d_api.config import get_settings
from print3d_api.models import IntegrationSetting
from print3d_api.services import audit
from print3d_channels.shipping import MelhorEnvio, ShippingQuoter
from print3d_core.security import TokenVault, TokenVaultError
from print3d_notify.meta import WhatsAppSettings

log = logging.getLogger("print3d.integrations")


@dataclass(frozen=True)
class Field:
    key: str  # mesmo nome da variável de ambiente
    group: str
    label: str
    secret: bool = False
    hint: str = ""
    choices: tuple[str, ...] = ()


FIELDS: tuple[Field, ...] = (
    Field("AI_PROVIDER", "ia", "Fornecedor de IA", choices=("openai", "claude")),
    Field("AI_API_KEY", "ia", "Chave da IA", secret=True, hint="platform.openai.com → API keys"),
    Field(
        "AI_EMBEDDING_PROVIDER",
        "ia",
        "Fornecedor da busca por significado",
        choices=("openai",),
        hint="só precisa se a IA principal for Claude",
    ),
    Field(
        "AI_EMBEDDING_API_KEY",
        "ia",
        "Chave da busca por significado",
        secret=True,
        hint="só precisa se a IA principal for Claude",
    ),
    Field("WHATSAPP_TOKEN", "whatsapp", "Token de acesso", secret=True, hint="token permanente"),
    Field("WHATSAPP_PHONE_NUMBER_ID", "whatsapp", "ID do número de telefone"),
    Field("WHATSAPP_GRAPH_VERSION", "whatsapp", "Versão da Graph API", hint="ex.: v23.0"),
    Field("WHATSAPP_APP_SECRET", "whatsapp", "Chave secreta do app", secret=True),
    Field(
        "WHATSAPP_VERIFY_TOKEN",
        "whatsapp",
        "Token de verificação do webhook",
        hint="clique em gerar e cole o mesmo na Meta",
    ),
    Field(
        "WHATSAPP_TEMPLATE_STATUS",
        "whatsapp",
        "Template aprovado (fora das 24 h)",
        hint="nome do template com 1 variável",
    ),
    Field("WHATSAPP_TEMPLATE_LANG", "whatsapp", "Idioma do template", hint="pt_BR"),
    Field(
        "PUBLIC_API_URL",
        "geral",
        "Endereço público da API",
        hint="https://api.<domínio> — retorno do Mercado Livre/Meta (exige domínio)",
    ),
    Field(
        "PUBLIC_STORE_URL",
        "geral",
        "Endereço público da loja",
        hint="https://<domínio> — fotos dos anúncios nos marketplaces",
    ),
    Field(
        "ML_CLIENT_ID",
        "mercadolivre",
        "App ID",
        hint="developers.mercadolivre.com.br → sua aplicação",
    ),
    Field("ML_CLIENT_SECRET", "mercadolivre", "Chave secreta", secret=True),
    Field(
        "MP_ACCESS_TOKEN",
        "mercadopago",
        "Access Token",
        secret=True,
        hint="Mercado Pago → Suas integrações → credenciais (teste começa com TEST-)",
    ),
    Field("MP_PUBLIC_KEY", "mercadopago", "Public Key", hint="para o cartão (depois do domínio)"),
    Field(
        "MP_WEBHOOK_SECRET",
        "mercadopago",
        "Assinatura secreta dos avisos",
        secret=True,
        hint="Webhooks → assinatura secreta (com domínio; sem ela o sistema consulta a cada 2 min)",
    ),
    Field("SHOPEE_PARTNER_ID", "shopee", "Partner ID", hint="open.shopee.com → seu app"),
    Field("SHOPEE_PARTNER_KEY", "shopee", "Partner Key", secret=True),
    Field(
        "SHOPEE_HOST",
        "shopee",
        "Endereço da API (opcional)",
        hint="vazio = produção; teste: https://partner.test-stable.shopeemobile.com",
    ),
    Field(
        "MELHORENVIO_TOKEN",
        "frete",
        "Token do Melhor Envio",
        secret=True,
        hint="painel do Melhor Envio → Integrações → gerar token",
    ),
    Field("MELHORENVIO_ENV", "frete", "Ambiente", choices=("producao", "sandbox")),
    Field(
        "MELHORENVIO_CONTACT_EMAIL",
        "frete",
        "E-mail de contato técnico",
        hint="o Melhor Envio exige um e-mail de contato nas chamadas",
    ),
    Field(
        "MELHORENVIO_SERVICES",
        "frete",
        "Serviços (opcional)",
        hint="IDs separados por vírgula; vazio = todos",
    ),
)
BY_KEY = {f.key: f for f in FIELDS}
GENERATABLE = {"WHATSAPP_VERIFY_TOKEN"}


class IntegrationError(Exception):
    pass


@lru_cache
def _vault(key: str) -> TokenVault:
    return TokenVault(key)


def vault() -> TokenVault | None:
    key = get_settings().fernet_key
    return _vault(key.get_secret_value()) if key and key.get_secret_value() else None


async def load(session: AsyncSession) -> dict[str, str]:
    """Valores do painel, já decifrados. Segredo que não decifra (chave trocada) é ignorado."""
    rows = (await session.scalars(select(IntegrationSetting))).all()
    out: dict[str, str] = {}
    v = vault()
    for row in rows:
        if not row.secret:
            out[row.key] = row.value
            continue
        if v is None:
            log.warning("segredo no banco sem FERNET_KEY no servidor", extra={"key": row.key})
            continue
        try:
            out[row.key] = v.decrypt(row.value)
        except TokenVaultError:
            log.warning("segredo não decifrou (FERNET_KEY trocada?)", extra={"key": row.key})
    return out


def _overlay(base: Any, values: dict[str, str], prefix: str) -> Any:
    """Põe os valores do painel por cima; campo SecretStr no destino recebe SecretStr
    (vale pelo tipo do campo, não por ser segredo na tela — ex.: token de verificação)."""
    fields = type(base).model_fields
    update: dict[str, Any] = {}
    for key, value in values.items():
        name = key.removeprefix(prefix).lower()
        if not key.startswith(prefix) or name not in fields:
            continue
        update[name] = SecretStr(value) if "SecretStr" in str(fields[name].annotation) else value
    return base.model_copy(update=update) if update else base


async def ai_settings(session: AsyncSession, base: AISettings | None = None) -> AISettings:
    values = {k: v for k, v in (await load(session)).items() if k.startswith("AI_")}
    result: AISettings = _overlay(base or AISettings(), values, "AI_")
    return result


async def whatsapp_settings(
    session: AsyncSession, base: WhatsAppSettings | None = None
) -> WhatsAppSettings:
    # WHATSAPP_GRAPH_VERSION → graph_version etc.
    values = {k: v for k, v in (await load(session)).items() if k.startswith("WHATSAPP_")}
    result: WhatsAppSettings = _overlay(base or WhatsAppSettings(), values, "WHATSAPP_")
    return result


async def save(
    session: AsyncSession, values: dict[str, str | None], clear: list[str], actor: str = "admin"
) -> None:
    """Grava o que veio preenchido; campo vazio mantém o atual; `clear` apaga."""
    unknown = [k for k in [*values, *clear] if k not in BY_KEY]
    if unknown:
        raise IntegrationError(f"campo desconhecido: {', '.join(unknown)}")
    v = vault()
    changed: list[str] = []
    for key, raw in values.items():
        value = (raw or "").strip()
        if not value:
            continue
        field = BY_KEY[key]
        if field.choices and value not in field.choices:
            raise IntegrationError(f"{field.label}: use {' ou '.join(field.choices)}")
        if field.secret:
            if v is None:
                raise IntegrationError("servidor sem FERNET_KEY: não dá para guardar segredos")
            value = v.encrypt(value)
        row = await session.get(IntegrationSetting, key)
        if row is None:
            session.add(IntegrationSetting(key=key, value=value, secret=field.secret))
        else:
            row.value, row.secret = value, field.secret
        changed.append(key)
    for key in clear:
        row = await session.get(IntegrationSetting, key)
        if row is not None:
            await session.delete(row)
            changed.append(f"-{key}")
    if changed:
        # nunca o valor: só quais campos mudaram
        await audit.record(
            session, actor=actor, action="integracoes_alteradas", payload={"campos": changed}
        )
    await session.commit()


async def generate(session: AsyncSession, key: str) -> str:
    if key not in GENERATABLE:
        raise IntegrationError("este campo não é gerado automaticamente")
    token = secrets.token_urlsafe(24)
    await save(session, {key: token}, [])
    return token


async def view(session: AsyncSession) -> list[dict[str, Any]]:
    """O que o painel mostra: nunca o segredo, só se está configurado e de onde vem."""
    db_values = await load(session)
    stored = {r.key for r in (await session.scalars(select(IntegrationSetting))).all()}
    env = {
        **{f.key: os.environ.get(f.key) for f in FIELDS},
        **{f"AI_{k.upper()}": v for k, v in AISettings().model_dump().items()},
        **{f"WHATSAPP_{k.upper()}": v for k, v in WhatsAppSettings().model_dump().items()},
    }
    out = []
    for f in FIELDS:
        value = db_values.get(f.key)
        source = "painel" if f.key in stored else None
        env_value = env.get(f.key)
        if isinstance(env_value, SecretStr):
            env_value = env_value.get_secret_value()
        if value is None and env_value:
            value, source = str(env_value), "servidor"
        preview = None
        if value:
            preview = (
                ("••••" + value[-4:])
                if f.secret and len(value) > 8
                else ("••••" if f.secret else value)
            )
        out.append(
            {
                "key": f.key,
                "group": f.group,
                "label": f.label,
                "secret": f.secret,
                "hint": f.hint,
                "choices": list(f.choices),
                "configured": bool(value),
                "source": source,
                "preview": preview,
                "generatable": f.key in GENERATABLE,
            }
        )
    return out


async def shipping_quoter(session: AsyncSession) -> ShippingQuoter | None:
    """Melhor Envio configurado (painel > .env) ou None (a loja mostra frete a combinar)."""
    values = await load(session)

    def get(key: str) -> str | None:
        return values.get(key) or os.environ.get(key) or None

    token, email = get("MELHORENVIO_TOKEN"), get("MELHORENVIO_CONTACT_EMAIL")
    if not token or not email:
        return None
    return MelhorEnvio(
        token,
        env=get("MELHORENVIO_ENV") or "producao",
        contact_email=email,
        services=get("MELHORENVIO_SERVICES"),
    )


def env_value(key: str) -> str | None:
    """Valor do .env para chaves sem classe de configuração própria."""
    return os.environ.get(key) or None
