"""Busca de imagens na internet para o assistente do painel (atrás de um Provider).

Só imagens com licença aberta que permite uso comercial: a loja vende o que imprime.
Openverse (api.openverse.org/v1/images/, conferido em 2026-11-04): sem chave, anônimo tem
limite de 20/min e 200/dia; cada resultado traz autor, licença e texto de atribuição.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
USER_AGENT = "print3d-admin/1.0 (assistente do painel)"


class ImageSearchError(Exception):
    pass


@dataclass(frozen=True)
class ImageHit:
    id: str
    title: str
    url: str  # imagem em tamanho cheio
    thumbnail: str
    creator: str
    license: str  # ex.: "CC BY 2.0"
    attribution: str
    source_page: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    mime: str
    ext: str


@runtime_checkable
class ImageSearch(Protocol):
    async def search(self, query: str, limit: int = 12) -> list[ImageHit]: ...
    async def get(self, image_id: str) -> ImageHit: ...
    async def download(self, url: str) -> DownloadedImage: ...


def _license(item: dict[str, Any]) -> str:
    code = str(item.get("license") or "").upper()
    if code in ("CC0", "PDM"):
        return "domínio público" if code == "PDM" else "CC0"
    return f"CC {code} {item.get('license_version') or ''}".strip()


def _hit(item: dict[str, Any]) -> ImageHit:
    return ImageHit(
        id=str(item["id"]),
        title=str(item.get("title") or "sem título")[:120],
        url=str(item["url"]),
        thumbnail=str(item.get("thumbnail") or item["url"]),
        creator=str(item.get("creator") or "desconhecido")[:80],
        license=_license(item),
        attribution=str(item.get("attribution") or "")[:400],
        source_page=str(item.get("foreign_landing_url") or ""),
        width=item.get("width"),
        height=item.get("height"),
    )


class OpenverseSearch:
    base_url = "https://api.openverse.org/v1"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"User-Agent": USER_AGENT}
        try:
            if self._client is not None:
                return await self._client.get(url, headers=headers, **kwargs)
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                return await client.get(url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ImageSearchError(f"busca de imagens fora do ar: {type(exc).__name__}") from exc

    async def search(self, query: str, limit: int = 12) -> list[ImageHit]:
        res = await self._get(
            f"{self.base_url}/images/",
            params={
                "q": query[:200],
                "license_type": "commercial",  # a loja vende o que imprime
                "mature": "false",
                "page_size": max(1, min(limit, 20)),
            },
        )
        if res.status_code == 429:
            raise ImageSearchError("limite de buscas de imagem atingido: tente em 1 minuto")
        if res.status_code >= 400:
            raise ImageSearchError(f"busca de imagens recusou ({res.status_code})")
        return [_hit(item) for item in res.json().get("results", []) if item.get("url")]

    async def get(self, image_id: str) -> ImageHit:
        if not image_id.replace("-", "").isalnum() or len(image_id) > 64:
            raise ImageSearchError("id de imagem inválido")
        res = await self._get(f"{self.base_url}/images/{image_id}/")
        if res.status_code == 404:
            raise ImageSearchError("imagem não encontrada")
        if res.status_code >= 400:
            raise ImageSearchError(f"busca de imagens recusou ({res.status_code})")
        return _hit(res.json())

    async def download(self, url: str) -> DownloadedImage:
        if not url.startswith("https://"):
            raise ImageSearchError("só baixo imagens por HTTPS")
        res = await self._get(url)
        if res.status_code >= 400:
            raise ImageSearchError(f"o site da imagem recusou ({res.status_code})")
        mime = res.headers.get("content-type", "").split(";")[0].strip().lower()
        if mime not in IMAGE_TYPES:
            raise ImageSearchError("o link não é uma imagem JPG, PNG ou WEBP")
        if len(res.content) > MAX_IMAGE_BYTES:
            raise ImageSearchError("imagem grande demais (máximo 20 MB)")
        return DownloadedImage(res.content, mime, IMAGE_TYPES[mime])
