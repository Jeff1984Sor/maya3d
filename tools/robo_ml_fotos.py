"""Robô do dono: fotos extras para os anúncios — infográfico de MEDIDAS e 2 recortes de DETALHE.

Para cada anúncio publicado no ML: baixa a foto principal do produto, gera as 3 imagens (medidas
reais da variante anunciada, cores da marca), sobe no produto (loja e ML usam as mesmas fotos) e
pede para a API reenviar fotos + descrição com o bloco de medidas ao anúncio.

    python tools/robo_ml_fotos.py --api https://api.<dominio> --loja https://<dominio>
        [--conta-nova-desde N] [--so-produto ID] [--dry-run]

Retoma de onde parou (estado em ~/Downloads/robo-fotos-estado.json). Token em
~/Downloads/robo-token.txt (painel → Integrações → Robô).
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
import time
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "packages" / "mesh" / "src" / "print3d_mesh" / "parametric" / "fonts"
SIZE = 1200


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    name = "Poppins-Bold.ttf" if bold else "Poppins-SemiBold.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


def hex_rgb(value: str, fallback: str) -> tuple[int, int, int]:
    v = (value or fallback).lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def cm(mm: float) -> str:
    value = round(mm / 10, 1)
    return f"{int(value)} cm" if value == int(value) else f"{value:.1f} cm".replace(".", ",")


def object_box(img: Image.Image) -> tuple[int, int, int, int]:
    """Caixa da peça: tudo que difere do fundo (cor dos cantos). Sem fundo liso = foto toda."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    corners = [rgb.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).convert("L")
    mask = diff.point(lambda v: 255 if v > 28 else 0).filter(ImageFilter.MedianFilter(5))
    box = mask.getbbox()
    if box is None:
        return 0, 0, w, h
    x0, y0, x1, y1 = box
    if (x1 - x0) * (y1 - y0) > 0.92 * w * h:
        return 0, 0, w, h
    pad = int(0.03 * max(w, h))
    return max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)


def arrow(
    d: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float], color: Any, w: int = 6
) -> None:
    d.line([a, b], fill=color, width=w)
    for p, q in ((a, b), (b, a)):  # pontas
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / length, dy / length
        tip = p
        left = (p[0] + ux * 28 - uy * 16, p[1] + uy * 28 + ux * 16)
        right = (p[0] + ux * 28 + uy * 16, p[1] + uy * 28 - ux * 16)
        d.polygon([tip, left, right], fill=color)


def pill(
    d: ImageDraw.ImageDraw, center: tuple[float, float], text: str, bg: Any, fg: Any, size: int = 44
) -> None:
    f = font(size)
    tw, th = d.textbbox((0, 0), text, font=f)[2:]
    x, y = center[0] - tw / 2, center[1] - th / 2
    d.rounded_rectangle([x - 26, y - 14, x + tw + 26, y + th + 22], radius=40, fill=bg)
    d.text((x, y - 4), text, font=f, fill=fg)


def plain_background(img: Image.Image) -> bool:
    x0, y0, x1, y1 = object_box(img)
    return (x1 - x0) * (y1 - y0) < 0.9 * img.width * img.height


def measures_image(photo: Image.Image, dims: list[float], colors: dict[str, str]) -> Image.Image:
    bg, ink = hex_rgb(colors.get("bg", ""), "#F7EFE6"), hex_rgb(colors.get("ink", ""), "#3B1F2B")
    accent = hex_rgb(colors.get("primary", ""), "#C4503C")
    white = (255, 255, 255)
    canvas = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(canvas)
    d.text((80, 60), "MEDIDAS", font=font(76), fill=ink)
    d.text((84, 160), "tamanho real da peça (aproximado)", font=font(34, bold=False), fill=ink)
    width, depth, height = dims
    if not plain_background(photo):
        # foto com cenário: setas mediriam a foto, não a peça -> foto + quadro de medidas
        pic = photo.copy()
        pic.thumbnail((560, 760), Image.Resampling.LANCZOS)
        mask = Image.new("L", pic.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, *pic.size], radius=40, fill=255)
        canvas.paste(pic, (80, 280 + (760 - pic.height) // 2), mask)
        rows = (
            ("Altura", cm(height)),
            ("Largura", cm(max(width, depth))),
            ("Profundidade", cm(min(width, depth))),
        )
        y = 360
        for label, value in rows:
            d.rounded_rectangle([700, y, 1120, y + 170], radius=36, fill=white)
            d.text((740, y + 24), label, font=font(34, bold=False), fill=ink)
            d.text((740, y + 74), value, font=font(64), fill=accent)
            y += 210
        return canvas
    piece = photo.crop(object_box(photo))
    piece.thumbnail((680, 560), Image.Resampling.LANCZOS)
    x0 = (SIZE - piece.width) // 2 - 80
    y0 = 260 + (560 - piece.height) // 2
    canvas.paste(piece, (x0, y0))
    x1, y1 = x0 + piece.width, y0 + piece.height
    ax = x1 + 70  # altura: seta vertical à direita da peça
    arrow(d, (ax, y0), (ax, y1), accent)
    pill(d, (ax + 120, (y0 + y1) / 2), cm(height), accent, white)
    ay = y1 + 60  # largura: seta horizontal abaixo da peça
    arrow(d, (x0, ay), (x1, ay), accent)
    pill(d, ((x0 + x1) / 2, ay + 80), cm(max(width, depth)), accent, white)
    pill(d, (SIZE / 2, SIZE - 80), f"Profundidade: {cm(min(width, depth))}", ink, bg, 36)
    return canvas


def detail_image(
    photo: Image.Image,
    region: tuple[float, float, float, float],
    label: str,
    colors: dict[str, str],
) -> Image.Image:
    bg, ink = hex_rgb(colors.get("bg", ""), "#F7EFE6"), hex_rgb(colors.get("ink", ""), "#3B1F2B")
    x0, y0, x1, y1 = object_box(photo)
    w, h = x1 - x0, y1 - y0
    side = min(w, h) * 0.62
    cx, cy = x0 + w * region[0], y0 + h * region[1]
    crop = photo.crop(
        (int(cx - side / 2), int(cy - side / 2), int(cx + side / 2), int(cy + side / 2))
    )
    crop = crop.convert("RGB").resize((960, 960), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (SIZE, SIZE), bg)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *crop.size], radius=48, fill=255)
    canvas.paste(crop, (120, 180), mask)
    d = ImageDraw.Draw(canvas)
    d.text((120, 60), "DETALHES", font=font(64), fill=ink)
    pill(d, (SIZE / 2, SIZE - 70), label, ink, bg, 34)
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--loja", required=True, help="endereço HTTPS da loja (fotos públicas)")
    ap.add_argument("--conta-nova-desde", type=int, default=0)
    ap.add_argument("--so-produto", action="append", type=int, default=[])
    ap.add_argument("--dry-run", action="store_true", help="gera as imagens numa pasta, não envia")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    state_path = pathlib.Path.home() / "Downloads" / "robo-fotos-estado.json"
    state: dict[str, Any] = (
        json.loads(state_path.read_text()) if state_path.exists() else {"feitos": []}
    )
    colors = (c.get("/brand").json().get("colors") or {}).get("light", {})
    listings = [
        x
        for x in c.get("/mercadolivre/listings").json()
        if x["status"] == "publicado"
        and x["id"] > args.conta_nova_desde
        and (not args.so_produto or x["product_id"] in args.so_produto)
    ]
    print(f"{len(listings)} anúncio(s)")
    out_dir = pathlib.Path.home() / "Downloads" / "robo-fotos"
    ok = 0
    for x in listings:
        pid = x["product_id"]
        try:
            product = c.get(f"/products/{pid}").json()
            variant = next((v for v in product["variants"] if v["id"] == x["variant_id"]), None)
            dims = (variant or {}).get("dims_mm") or []
            if pid not in state["feitos"]:
                images = c.get(f"/products/{pid}/images").json()
                if not images:
                    print(f"! {product['title']}: sem foto")
                    continue
                raw = httpx.get(f"{args.loja.rstrip('/')}/m/{images[0]['key']}", timeout=60).content
                photo = Image.open(io.BytesIO(raw)).convert("RGB")
                extras: list[tuple[str, Image.Image]] = []
                if len(dims) == 3:
                    extras.append(
                        ("medidas", measures_image(photo, [float(v) for v in dims], colors))
                    )
                extras.append(
                    ("detalhe-1", detail_image(photo, (0.5, 0.3), "acabamento e contornos", colors))
                )
                extras.append(
                    (
                        "detalhe-2",
                        detail_image(photo, (0.5, 0.7), "detalhes da impressão 3D", colors),
                    )
                )
                for name, img in extras:
                    buf = io.BytesIO()
                    img.save(buf, "PNG", optimize=True)
                    if args.dry_run:
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / f"{pid}-{name}.png").write_bytes(buf.getvalue())
                        continue
                    r = c.post(
                        f"/products/{pid}/images",
                        files={"file": (f"{name}.png", buf.getvalue(), "image/png")},
                    )
                    r.raise_for_status()
                if args.dry_run:
                    print(f"~ {product['title']}: imagens em {out_dir}")
                    continue
                state["feitos"].append(pid)
                state_path.write_text(json.dumps(state))
            if args.dry_run:
                continue
            r = c.post(f"/mercadolivre/listings/{x['id']}/refresh")
            if r.status_code == 200:
                ok += 1
                print(f"+ {product['title']}: {r.json()['pictures']} fotos no ML")
            else:
                print(f"x {product['title']}: {r.text[:200]}")
            time.sleep(1)
        except Exception as exc:  # um anúncio com erro não para os outros
            print(f"x produto {pid}: {exc}")
    print(f"atualizados: {ok} de {len(listings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
