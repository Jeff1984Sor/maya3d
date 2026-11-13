"""Robô do dono: publica no Mercado Livre os produtos ativos de uma categoria.

Uma variante por produto (a "M", senão a primeira). O preço no ML é o do Pix do site mais a
tarifa REAL que o ML informa (prévia), arredondado para ,90 — o dono recebe o mesmo líquido.
Pula produtos que já têm anúncio. Uso:

    python tools/robo_ml_publicar.py <categoria> --api https://api.<dominio> [--dry-run]

Trocou de conta no ML? --conta-nova-desde N ignora os anúncios de id <= N (os da conta antiga).
Categoria pede dado que falta? --atributo PRODUCT_TYPE=Vaso (repetível). A altura (HEIGHT) sai
da medida da peça. Categoria errada? --so-produto 165 --forcar-categoria MLB1234.

Token do robô em ~/Downloads/robo-token.txt (painel → Integrações → Robô).
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
import time
from decimal import Decimal
from typing import Any

import httpx


def ends_90(value: Decimal) -> Decimal:
    return Decimal(math.ceil(value + Decimal("0.10"))) - Decimal("0.10")


def attempt(
    c: httpx.Client, variant_id: int, site: Decimal, category_id: str | None, auto: dict[str, str]
) -> tuple[Decimal, dict[str, Any], str | None, list[str]] | None:
    """Preço (site + tarifa real) e o que falta na categoria; None se o ML recusar."""
    price = site
    prev: dict[str, Any] = {}
    for _ in range(3):  # a tarifa depende do preço: converge em 2-3 voltas
        body: dict[str, Any] = {"variant_id": variant_id, "price": str(price)}
        if category_id:
            body["category_id"] = category_id
        pv = c.post("/mercadolivre/preview", json=body)
        if pv.status_code == 422:
            return None
        pv.raise_for_status()
        prev = pv.json()
        price = ends_90(site + Decimal(prev["fee"]))
    missing = [
        a["name"] for a in prev["required_attributes"] if a["id"] not in ("BRAND", "MODEL", *auto)
    ]
    return price, prev, category_id, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("categoria")
    ap.add_argument("--api", required=True, help="endereço HTTPS da API (Integrações)")
    ap.add_argument(
        "--categoria-reserva",
        help="categoria do ML (ex.: MLB1234) quando a sugerida pede dados que não temos",
    )
    ap.add_argument(
        "--conta-nova-desde",
        type=int,
        default=0,
        help="anúncios com id até este número são da conta antiga: não contam como publicados",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--atributo", action="append", default=[], help="ID=valor (repetível)")
    ap.add_argument("--so-produto", action="append", type=int, default=[], help="id do produto")
    ap.add_argument("--forcar-categoria", help="categoria do ML usada direto (ex.: MLB1234)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    products = [
        p
        for p in c.get("/products", params={"limit": 1000}).json()
        if p["category"] == args.categoria
        and p["status"] == "ativo"
        and (not args.so_produto or p["id"] in args.so_produto)
    ]
    print(f"{len(products)} produtos em {args.categoria}")
    brand = c.get("/brand").json()["name"]
    # BRAND/MODEL a API já preenche; estes saem da marca e do material da peça
    auto = {"MANUFACTURER": brand, "MATERIAL": "Plástico PLA"}
    for item in args.atributo:
        key, _, value = item.partition("=")
        auto[key.strip()] = value.strip()
    ok = 0
    for p in products:
        try:
            listings = c.get("/mercadolivre/listings", params={"product_id": p["id"]}).json()
            current = [x for x in listings if x["id"] > args.conta_nova_desde]
            if any(x["status"] == "publicado" for x in current):  # tentativa com erro: refaz
                print(f"= {p['title']}: já anunciado")
                continue
            variants = c.get(f"/products/{p['id']}").json()["variants"]
            if not variants:
                print(f"! {p['title']}: sem variante (tamanho) cadastrada — pulei")
                continue
            variant = next(
                (v for v in variants if str(v.get("size_label") or "").startswith("M")), variants[0]
            )
            dims = variant.get("dims_mm") or []
            item_auto = dict(auto)
            if len(dims) == 3:  # altura da peça em pé (medida da malha)
                item_auto.setdefault("HEIGHT", f"{max(1, round(dims[2] / 10))} cm")
            quote = c.get(f"/products/{p['id']}/variants/{variant['id']}/quote").json()
            site = next(Decimal(q["price"]) for q in quote["quotes"] if q["channel"] == "site_pix")
            # 1º a categoria sugerida pelo ML; se ela pedir o que não sabemos (ex.: ISBN de
            # livro), a categoria reserva (--categoria-reserva)
            found = None
            choices = (
                (args.forcar_categoria,)
                if args.forcar_categoria
                else (None, args.categoria_reserva)
            )
            for category_id in choices:
                found = attempt(c, variant["id"], site, category_id, item_auto)
                if found and not found[3]:
                    break
            if found is None or found[3]:
                why = found[3] if found else "o ML não sugeriu categoria"
                print(f"! {p['title']}: o ML pede {why} — pulei")
                continue
            price, prev, category_id, _ = found
            extra = {
                a["id"]: item_auto[a["id"]]
                for a in prev["required_attributes"]
                if a["id"] in item_auto
            }
            line = (
                f"{p['title']} | {variant.get('size_label')} | site R$ {site} → ML R$ {price}"
                f" | {prev['category']['name']}"
            )
            if args.dry_run:
                print(f"~ {line}")
                continue
            body = {"variant_id": variant["id"], "price": str(price), "attributes": extra}
            if category_id:
                body["category_id"] = category_id
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
