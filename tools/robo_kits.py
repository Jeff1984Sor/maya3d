"""Robô do dono: cria KITS (várias unidades num produto só) a partir de produtos que já vendemos.

Cada kit: produto novo com o desenho/licença da 1ª peça, uma variante com gramas e tempo SOMADOS
das peças (estimativa, como as peças), foto montada com as peças e a etiqueta "KIT N UNIDADES",
e ativação (o Guardião decide). Idempotente: kit com o mesmo título é pulado.

    python tools/robo_kits.py --api https://api.<dominio> --loja https://<dominio> [--dry-run]

Depois: robo_ml_publicar.py (--so-produto) e robo_ml_fotos.py para medidas e detalhes.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import sys
from typing import Any

import httpx
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from robo_ml_fotos import SIZE, font, hex_rgb, object_box

# (título, nicho, categoria, [(título da peça, quantidade)], frase de uso)
KITS: list[tuple[str, str, str, list[tuple[str, int]], str]] = [
    (
        "Kit 6 Flocos de Neve - Enfeites de Natal",
        "datas-comemorativas",
        "natal",
        [
            ("Floco de Neve Clássico - Enfeite de Natal", 3),
            ("Floco de Neve Cristal - Enfeite de Natal", 3),
        ],
        "Seis flocos de neve (dois modelos) para a árvore, guirlandas e vitrines de Natal.",
    ),
    (
        "Kit 6 Enfeites de Natal Sortidos",
        "datas-comemorativas",
        "natal",
        [
            ("Estrela de Natal em Relevo – Enfeite 3D", 1),  # noqa: RUF001 (título real do produto)
            ("Floco de Neve Clássico - Enfeite de Natal", 1),
            ("Floco de Neve Cristal - Enfeite de Natal", 1),
            ("Coração Natalino Vazado com Estrela", 1),
            ("Bengala Doce de Natal Enfeite", 1),
            ("Árvore de Natal 3D com Bolinhas de Enfeite", 1),
        ],
        "Seis enfeites diferentes para pendurar na árvore, com argola para fita.",
    ),
    (
        "Kit 12 Enfeites de Natal Sortidos",
        "datas-comemorativas",
        "natal",
        [
            ("Estrela de Natal em Relevo – Enfeite 3D", 2),  # noqa: RUF001
            ("Floco de Neve Clássico - Enfeite de Natal", 2),
            ("Floco de Neve Cristal - Enfeite de Natal", 2),
            ("Coração Natalino Vazado com Estrela", 2),
            ("Bengala Doce de Natal Enfeite", 2),
            ("Árvore de Natal 3D com Bolinhas de Enfeite", 2),
        ],
        "Doze enfeites (seis modelos, dois de cada) para deixar a árvore completa.",
    ),
    (
        "Kit 4 Argolas Porta-Guardanapo Estrela de Natal",
        "datas-comemorativas",
        "natal",
        [("Argola Porta Guardanapo Estrela de Natal", 4)],
        "Quatro argolas para arrumar a mesa da ceia de Natal.",
    ),
    (
        "Kit 10 Mini Árvores de Natal Plissadas com Estrela",
        "datas-comemorativas",
        "natal",
        [("Mini Árvore de Natal Plissada com Estrela", 10)],
        "Dez mini árvores de 10 cm com estrela de encaixe: mesa posta, presente e lembrancinha.",
    ),
    (
        "Kit 4 Porta-Copos Hexagonal Favo de Mel",
        "casa-e-decoracao",
        "casa-e-decoracao",
        [("Porta Copos Hexagonal Favo de Mel", 4)],
        "Jogo com quatro porta-copos para proteger a mesa com charme.",
    ),
    (
        "Kit 4 Porta-Copos Redondo Vazado",
        "casa-e-decoracao",
        "casa-e-decoracao",
        [("Porta Copos Redondo Vazado", 4)],
        "Jogo com quatro porta-copos vazados, leves e fáceis de limpar.",
    ),
    (
        "Kit 3 Ganchos de Parede Minimalistas",
        "casa-e-decoracao",
        "casa-e-decoracao",
        [("Gancho de Parede Minimalista", 3)],
        "Três ganchos para bolsas, chaves, panos e toalhas (parafuso não incluso).",
    ),
    (
        "Kit 10 Chaveiros Nossa Senhora Aparecida - Lembrancinha",
        "religioso",
        "acessorios-e-lembrancinhas",
        [("Chaveiro Nossa Senhora Aparecida", 10)],
        "Dez chaveiros para lembrancinha de batizado, primeira comunhão, missa e festas.",
    ),
    (
        "Kit 10 Chaveiros Medalha de São Bento - Lembrancinha",
        "religioso",
        "acessorios-e-lembrancinhas",
        [("Chaveiro Medalha de São Bento", 10)],
        "Dez chaveiros de São Bento para lembrancinha e proteção.",
    ),
    (
        "Kit 10 Terços Católicos - Lembrancinha",
        "religioso",
        "acessorios-e-lembrancinhas",
        [("Terço Católico Branco", 10)],
        "Dez terços para lembrancinha de batizado, primeira comunhão e crisma.",
    ),
    (
        "Kit 10 Medalhas de São Bento - Lembrancinha",
        "religioso",
        "cruzes-e-crucifixos",
        [("Medalha de São Bento", 10)],
        "Dez medalhas de São Bento para lembrancinha e proteção.",
    ),
]


def pick_variant(variants: list[dict[str, Any]]) -> dict[str, Any]:
    return next(
        (v for v in variants if str(v.get("size_label") or "").startswith("M")), variants[0]
    )


def kit_photo(photos: list[Image.Image], total: int, colors: dict[str, str]) -> Image.Image:
    """Grade com as peças (até 9) e a etiqueta "KIT N UNIDADES"."""
    bg = hex_rgb(colors.get("bg", ""), "#F7EFE6")
    accent = hex_rgb(colors.get("primary", ""), "#C4503C")
    tiles = (photos * total)[: min(total, 9)]
    cols = 2 if len(tiles) <= 4 else 3
    rows = -(-len(tiles) // cols)
    canvas = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(canvas)
    area_top, area = 60, SIZE - 220
    cell = min((SIZE - 120) // cols, area // rows)
    x_start = (SIZE - cell * cols) // 2
    for i, photo in enumerate(tiles):
        piece = photo.crop(object_box(photo))
        piece.thumbnail((cell - 24, cell - 24), Image.Resampling.LANCZOS)
        cx = x_start + (i % cols) * cell + (cell - piece.width) // 2
        cy = area_top + (i // cols) * cell + (cell - piece.height) // 2
        canvas.paste(piece, (cx, cy))
    label = f"KIT {total} UNIDADES"
    f = font(64)
    tw, th = d.textbbox((0, 0), label, font=f)[2:]
    x, y = (SIZE - tw) / 2, SIZE - 130
    d.rounded_rectangle([x - 40, y - 20, x + tw + 40, y + th + 30], radius=50, fill=accent)
    d.text((x, y - 6), label, font=f, fill=(255, 255, 255))
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--loja", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    products = {p["title"]: p for p in c.get("/products", params={"limit": 1000}).json()}
    colors = (c.get("/brand").json().get("colors") or {}).get("light", {})
    created: list[int] = []
    for title, niche, category, parts, use in KITS:
        if title in products:
            print(f"= {title}: já existe (produto {products[title]['id']})")
            continue
        missing = [name for name, _ in parts if name not in products]
        if missing:
            print(f"! {title}: peça não encontrada: {missing}")
            continue
        details = [c.get(f"/products/{products[name]['id']}").json() for name, _ in parts]
        variants = [pick_variant(d["variants"]) for d in details]
        total = sum(q for _, q in parts)
        grams: dict[str, float] = {}
        for v, (_, qty) in zip(variants, parts, strict=True):
            for mat, g in (v.get("grams_by_material") or {}).items():
                grams[mat] = round(grams.get(mat, 0) + float(g) * qty, 1)
        seconds = sum(
            int(v.get("print_seconds") or 0) * q for v, (_, q) in zip(variants, parts, strict=True)
        )
        dims = max((v.get("dims_mm") or [0, 0, 0] for v in variants), key=lambda d: max(d))
        photos = []
        for d in details:
            imgs = c.get(f"/products/{d['id']}/images").json()
            if imgs:
                raw = httpx.get(f"{args.loja.rstrip('/')}/m/{imgs[0]['key']}", timeout=60).content
                photos.append(Image.open(io.BytesIO(raw)).convert("RGB"))
        lines = "\n".join(f"• {q}x {name}" for name, q in parts)
        description = (
            f"{use}\n\nO KIT TEM {total} PEÇAS:\n{lines}\n\n"
            "Cada peça tem o mesmo tamanho e acabamento da peça vendida avulsa."
        )
        if args.dry_run:
            print(f"~ {title}: {total} un., {sum(grams.values())} g, {seconds // 60} min")
            continue
        design = details[0]["design"]
        made = c.post(
            "/products",
            json={
                "niche": niche,
                "category": category,
                "title": title,
                "description": description,
                "tags": ["kit", *details[0].get("tags", [])[:10]],
                "occasions": details[0].get("occasions", []),
                "customizable": False,
                "min_material": details[0].get("min_material"),
                "design": {
                    k: design.get(k)
                    for k in (
                        "origin",
                        "author",
                        "license",
                        "source_url",
                        "attribution_text",
                        "source_file_url",
                    )
                }
                | {"name": title},
            },
        )
        made.raise_for_status()
        pid = made.json()["id"]
        c.post(
            f"/products/{pid}/variants",
            json={
                "size_label": f"Kit {total} un.",
                "dims_mm": dims,
                "grams_by_material": grams,
                "print_seconds": seconds,
                "post_minutes": 5 + 2 * total,
                "params": {"kit": [[name, q] for name, q in parts], "estimativa": True},
            },
        ).raise_for_status()
        buf = io.BytesIO()
        kit_photo(photos, total, colors).save(buf, "PNG", optimize=True)
        c.post(
            f"/products/{pid}/images", files={"file": ("kit.png", buf.getvalue(), "image/png")}
        ).raise_for_status()
        res = c.patch(f"/products/{pid}", json={"status": "ativo"})
        state = res.json().get("guardian_status") if res.status_code < 400 else res.text[:160]
        print(f"+ {title} (produto {pid}): {total} un., {sum(grams.values())} g — {state}")
        created.append(pid)
    print("criados:", created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
