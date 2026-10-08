"""Robô do dono: publica no Mercado Livre os produtos ativos de uma categoria.

Uma variante por produto (a "M", senão a primeira). O preço no ML é o do Pix do site mais a
tarifa REAL que o ML informa (prévia), arredondado para ,90 — o dono recebe o mesmo líquido.
Pula produtos que já têm anúncio. Uso:

    python tools/robo_ml_publicar.py <categoria> --api https://api.<dominio> [--dry-run]

Token do robô em ~/Downloads/robo-token.txt (painel → Integrações → Robô).
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
import time
from decimal import Decimal

import httpx


def ends_90(value: Decimal) -> Decimal:
    return Decimal(math.ceil(value + Decimal("0.10"))) - Decimal("0.10")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("categoria")
    ap.add_argument("--api", required=True, help="endereço HTTPS da API (Integrações)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    products = [
        p
        for p in c.get("/products", params={"limit": 1000}).json()
        if p["category"] == args.categoria and p["status"] == "ativo"
    ]
    print(f"{len(products)} produtos em {args.categoria}")
    brand = c.get("/brand").json()["name"]
    # BRAND/MODEL a API já preenche; estes saem da marca e do material da peça
    auto = {"MANUFACTURER": brand, "MATERIAL": "Plástico PLA"}
    ok = 0
    for p in products:
        try:
            if c.get("/mercadolivre/listings", params={"product_id": p["id"]}).json():
                print(f"= {p['title']}: já anunciado")
                continue
            variants = c.get(f"/products/{p['id']}").json()["variants"]
            variant = next(
                (v for v in variants if str(v.get("size_label") or "").startswith("M")), variants[0]
            )
            quote = c.get(f"/products/{p['id']}/variants/{variant['id']}/quote").json()
            site = next(Decimal(q["price"]) for q in quote["quotes"] if q["channel"] == "site_pix")
            price = site
            for _ in range(3):  # a tarifa depende do preço: converge em 2-3 voltas
                pv = c.post(
                    "/mercadolivre/preview", json={"variant_id": variant["id"], "price": str(price)}
                )
                pv.raise_for_status()
                prev = pv.json()
                price = ends_90(site + Decimal(prev["fee"]))
            missing = [
                a for a in prev["required_attributes"] if a["id"] not in ("BRAND", "MODEL", *auto)
            ]
            if missing:
                print(f"! {p['title']}: o ML pede {[a['name'] for a in missing]} — pulei")
                continue
            extra = {a["id"]: auto[a["id"]] for a in prev["required_attributes"] if a["id"] in auto}
            line = (
                f"{p['title']} | {variant.get('size_label')} | site R$ {site} → ML R$ {price}"
                f" | {prev['category']['name']}"
            )
            if args.dry_run:
                print(f"~ {line}")
                continue
            body = {"variant_id": variant["id"], "price": str(price), "attributes": extra}
            r = c.post("/mercadolivre/listings", json=body)
            r.raise_for_status()
            listing = r.json()
            if listing["status"] == "publicado":
                ok += 1
                print(f"+ {line} | {listing['permalink']}")
            else:
                print(f"x {line} | {listing['last_error']}")
            time.sleep(3)
        except Exception as exc:  # um produto com erro não para os outros
            print(f"x {p['title']}: {exc}")
    print(f"publicados: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
