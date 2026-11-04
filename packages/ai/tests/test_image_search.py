import httpx
import pytest

from print3d_ai.image_search import ImageSearch, ImageSearchError, OpenverseSearch

ITEM = {
    "id": "1e7ea71f-4ae1-406e-bfdb-006dbc6d151b",
    "title": "Dog",
    "url": "https://live.staticflickr.com/x.jpg",
    "thumbnail": "https://api.openverse.org/v1/images/1e7e/thumb/",
    "creator": "Ana",
    "license": "by-sa",
    "license_version": "2.0",
    "attribution": '"Dog" by Ana is licensed under CC BY-SA 2.0.',
    "foreign_landing_url": "https://www.flickr.com/photos/x",
    "width": 800,
    "height": 600,
}


def _search(handler: httpx.MockTransport) -> OpenverseSearch:
    return OpenverseSearch(httpx.AsyncClient(transport=handler))


async def test_busca_so_licenca_comercial() -> None:
    seen: dict[str, str] = {}

    def handle(req: httpx.Request) -> httpx.Response:
        seen.update(req.url.params)
        seen["ua"] = req.headers["user-agent"]
        return httpx.Response(200, json={"results": [ITEM, {**ITEM, "url": None}]})

    search = _search(httpx.MockTransport(handle))
    assert isinstance(search, ImageSearch)
    hits = await search.search("dog", 50)
    assert seen["license_type"] == "commercial"
    assert seen["mature"] == "false"
    assert seen["page_size"] == "20"
    assert seen["ua"].startswith("print3d-admin")
    assert len(hits) == 1  # sem url não serve
    assert (hits[0].license, hits[0].creator) == ("CC BY-SA 2.0", "Ana")


async def test_limite_de_buscas_vira_mensagem() -> None:
    search = _search(httpx.MockTransport(lambda req: httpx.Response(429)))
    with pytest.raises(ImageSearchError, match="limite"):
        await search.search("dog")


async def test_id_invalido_nem_consulta() -> None:
    search = _search(httpx.MockTransport(lambda req: httpx.Response(500)))
    with pytest.raises(ImageSearchError, match="inválido"):
        await search.get("../../etc")


async def test_download_so_imagem_por_https() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith(".html"):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"jpg")

    search = _search(httpx.MockTransport(handle))
    image = await search.download("https://x.org/a.jpg")
    assert (image.data, image.mime, image.ext) == (b"jpg", "image/jpeg", "jpg")
    with pytest.raises(ImageSearchError, match="HTTPS"):
        await search.download("http://x.org/a.jpg")
    with pytest.raises(ImageSearchError, match="não é uma imagem"):
        await search.download("https://x.org/a.html")
