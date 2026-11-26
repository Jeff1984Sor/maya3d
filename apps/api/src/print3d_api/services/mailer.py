"""E-mail para o dono (SMTP configurado em Integrações → E-mail; senha cifrada no banco)."""

import asyncio
import smtplib
import socket
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.services import integrations


class MailError(Exception):
    pass


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    security: str  # ssl | starttls
    user: str
    password: str
    sender: str
    owner: str | None


async def settings(session: AsyncSession) -> SmtpSettings | None:
    values = await integrations.load(session)

    def get(key: str) -> str:
        return (values.get(key) or integrations.env_value(key) or "").strip()

    host, user, password = get("SMTP_HOST"), get("SMTP_USER"), get("SMTP_PASSWORD")
    if not host or not user or not password:
        return None
    security = get("SMTP_SECURITY") or "ssl"
    port = get("SMTP_PORT")
    return SmtpSettings(
        host=host,
        port=int(port) if port.isdigit() else (465 if security == "ssl" else 587),
        security=security,
        user=user,
        password=password,
        sender=get("SMTP_FROM") or user,
        owner=get("OWNER_EMAIL") or None,
    )


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    mime: str  # ex.: application/xml


# Nome fixo no EHLO: dentro do container, socket.getfqdn() pode travar no DNS reverso e o
# servidor SMTP derruba a conexão antes de o cliente se apresentar.
EHLO_NAME = "localhost"


def _send_sync(cfg: SmtpSettings, msg: EmailMessage, steps: list[str] | None = None) -> None:
    start = time.monotonic()

    def step(name: str) -> None:
        if steps is not None:
            steps.append(f"{name} ({time.monotonic() - start:.1f}s)")

    ctx = ssl.create_default_context()
    smtp: smtplib.SMTP
    if cfg.security == "ssl":
        smtp = smtplib.SMTP_SSL(
            cfg.host, cfg.port, local_hostname=EHLO_NAME, context=ctx, timeout=30
        )
    else:
        smtp = smtplib.SMTP(cfg.host, cfg.port, local_hostname=EHLO_NAME, timeout=30)
    with smtp:
        step("conectou")
        smtp.ehlo()
        step("apresentou-se")
        if cfg.security != "ssl":
            smtp.starttls(context=ctx)
            smtp.ehlo()
            step("criptografou")
        smtp.login(cfg.user, cfg.password.replace(" ", ""))
        step("senha aceita")
        smtp.send_message(msg)
        step("enviado")


def _probe_sync(host: str, port: int, security: str) -> str:
    """Só abre a conexão e lê a saudação do servidor (sem login)."""
    try:
        raw = socket.create_connection((host, port), timeout=10)
    except OSError as exc:
        return f"conexão falhou: {type(exc).__name__}: {exc}"
    try:
        sock = raw
        if security == "ssl":
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        sock.settimeout(10)
        banner = sock.recv(200).decode("utf-8", "replace").strip()
        return f"ok: {banner[:80]}" if banner else "conectou, mas o servidor não respondeu"
    except OSError as exc:
        return f"conectou, mas caiu: {type(exc).__name__}: {exc}"
    finally:
        raw.close()


async def diagnose(session: AsyncSession) -> dict[str, str]:
    """Testa, do servidor, as portas do SMTP e o envio de um e-mail de teste ao dono."""
    cfg = await settings(session)
    host = cfg.host if cfg else "smtp.gmail.com"
    out: dict[str, str] = {}
    for port, sec in ((465, "ssl"), (587, "plain"), (25, "plain")):
        out[f"porta {port}"] = await asyncio.to_thread(_probe_sync, host, port, sec)
    if cfg is None:
        out["envio"] = "e-mail não configurado"
        return out
    msg = EmailMessage()
    msg["Subject"], msg["From"] = "Teste de e-mail da loja", cfg.sender
    msg["To"] = cfg.owner or cfg.user
    msg.set_content("Chegou! O e-mail está funcionando.")
    steps: list[str] = []
    try:
        await asyncio.to_thread(_send_sync, cfg, msg, steps)
        out["envio"] = f"enviado para {msg['To']}"
    except (OSError, smtplib.SMTPException) as exc:
        out["envio"] = f"falhou: {type(exc).__name__}: {str(exc)[:200]}"
    out["etapas"] = " → ".join(steps) or "nenhuma"
    out["config"] = (
        f"{cfg.host}:{cfg.port} {cfg.security}, senha com {len(cfg.password)} caracteres"
    )
    return out


async def send(
    session: AsyncSession,
    *,
    subject: str,
    text: str,
    to: str | None = None,
    attachments: tuple[Attachment, ...] = (),
) -> str:
    """Envia e devolve o destinatário. Sem SMTP ou sem destino → MailError (nada se perde:
    quem chama registra o motivo e o dono baixa os arquivos pelo painel)."""
    cfg = await settings(session)
    if cfg is None:
        raise MailError("e-mail não configurado (Integrações → E-mail)")
    destino = to or cfg.owner
    if not destino:
        raise MailError("sem e-mail do dono (Integrações → E-mail → Seu e-mail para avisos)")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, cfg.sender, destino
    msg.set_content(text)
    for a in attachments:
        main, _, sub = a.mime.partition("/")
        msg.add_attachment(a.content, maintype=main, subtype=sub, filename=a.filename)
    try:
        await asyncio.to_thread(_send_sync, cfg, msg)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailError(f"falha ao enviar e-mail: {type(exc).__name__}: {exc}") from exc
    return destino
