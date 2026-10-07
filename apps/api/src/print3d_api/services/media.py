"""Imagens da loja (fotos de produto, logo, destaque da home).

Toda imagem enviada é aberta e regravada por nós (WebP, no máximo 1600 px, sem metadados
EXIF/GPS do celular), com miniatura de 480 px. Arquivo que não abre como imagem é recusado.
Ficam em files/media/ e são servidas publicamente só por esse prefixo.
"""

import io
import uuid
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from print3d_core.storage import LocalStorage

PREFIX = "media"
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 60_000_000  # protege contra "bomba de descompressão"
FULL_SIDE = 1600
THUMB_SIDE = 480


class MediaError(Exception):
    pass


@dataclass(frozen=True)
class SavedImage:
    key: str
    thumb_key: str
    width: int
    height: int


def public_url(key: str | None) -> str | None:
    """Caminho público servido pela loja (rota /m/... da vitrine)."""
    return f"/m/{key}" if key else None


def _encode(img: Image.Image, side: int) -> bytes:
    copy = img.copy()
    copy.thumbnail((side, side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    copy.save(buf, "WEBP", quality=85, method=4)
    return buf.getvalue()


def save_image(storage: LocalStorage, data: bytes, *, folder: str = "img") -> SavedImage:
    if len(data) > MAX_BYTES:
        raise MediaError("imagem acima de 20 MB")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        opened = Image.open(io.BytesIO(data))
        opened.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise MediaError("arquivo não é uma imagem válida (use JPG, PNG ou WebP)") from exc
    upright: Image.Image = ImageOps.exif_transpose(opened)  # foto em pé continua em pé
    img = upright.convert("RGBA" if "A" in upright.getbands() else "RGB")
    name = uuid.uuid4().hex
    key = f"{PREFIX}/{folder}/{name}.webp"
    thumb = f"{PREFIX}/{folder}/{name}-480.webp"
    for k, side in ((key, FULL_SIDE), (thumb, THUMB_SIDE)):
        path = storage.local_path(k)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_encode(img, side))
    return SavedImage(key=key, thumb_key=thumb, width=img.width, height=img.height)


def delete(storage: LocalStorage, *keys: str | None) -> None:
    for key in keys:
        if key and key.startswith(f"{PREFIX}/"):
            storage.local_path(key).unlink(missing_ok=True)
