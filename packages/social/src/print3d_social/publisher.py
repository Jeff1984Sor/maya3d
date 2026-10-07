"""Entrega de conteúdo ao MayaPost (que cuida de legenda, agenda e métricas)."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ContentPiece(BaseModel):
    product_id: str
    kind: str  # post | carrossel | video
    media_urls: list[str]
    channel_link: str  # link do canal correto (site/ML/Shopee)


@runtime_checkable
class ContentPublisher(Protocol):
    async def submit(self, piece: ContentPiece) -> str:
        """Envia ao MayaPost e devolve o id externo."""
        ...
