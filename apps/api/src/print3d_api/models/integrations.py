from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import TimestampMixin


class IntegrationSetting(TimestampMixin, Base):
    """Chaves e ajustes de integrações (IA, WhatsApp...) colados pelo dono no painel.

    Segredo vai cifrado com Fernet (FERNET_KEY do servidor); a API nunca devolve o valor de
    um segredo, só "configurado" e os 4 últimos caracteres. Valor aqui vence o do .env.
    """

    __tablename__ = "integration_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    secret: Mapped[bool] = mapped_column(Boolean, default=False)
