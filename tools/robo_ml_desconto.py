"""Robô do dono: desconto em todos os anúncios publicados no ML, sem vender abaixo do custo.

Preço novo = preço atual - N%, terminando em ,90. Trava: nunca abaixo de (custo da peça + tarifa
do ML) — com frete grátis o ML ainda desconta o frete, então a trava é o mínimo, não lucro.
Guarda o preço original em ~/Downloads/robo-desconto-precos.json para voltar com --desfazer.

    python tools/robo_ml_desconto.py --api https://api.<dominio> --pct 30 [--dry-run]
    python tools/robo_ml_desconto.py --api https://api.<dominio> --desfazer
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time
from decimal import Decimal

import httpx

STATE = pathlib.Path.home() / "Downloads" / "robo-desconto-precos.json"


def ends_90(value: Decimal) -> Decimal:
    return Decimal(math.ceil(value + Decimal("0.10"))) - Decimal("0.10")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--pct", type=int, default=30)
    ap.add_argument("--conta-nova-desde", type=int, default=157)
    ap.add_argument("--desfazer", action="store_true", help="volta os preços originais")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    originals: dict[str, str] = json.loads(STATE.read_text()) if STATE.exists() else {}
    listings = [
        x
        for x in c.get("/mercadolivre/listings").json()
        if x["status"] == "publicado" and x["id"] > args.conta_nova_desde
    ]
    print(f"{len(listings)} anúncio(s)")
    full = floor_hits = fails = 0
    for x in listings:
        key = str(x["id"])
        current = Decimal(str(x["price"]))
        if args.desfazer:
            if key not in originals:
                continue
            new = Decimal(originals[key])
        else:
            base = Decimal(originals.get(key, str(current)))  # desconto sempre sobre o original
            quote = c.get(f"/products/{x['product_id']}/variants/{x['variant_id']}/quote").json()
            cost = Decimal(str(quote.get("cost_total") or 0))
            fee_rate = (Decimal(str(x["fee"] or 0)) / current) if current else Decimal("0.12")
            fee_rate = min(max(fee_rate, Decimal("0.10")), Decimal("0.25"))
            floor = ends_90((cost + Decimal("6")) / (1 - fee_rate))  # + R$ 6 de tarifa fixa do ML
            wanted = ends_90(base * (100 - args.pct) / 100)
            new = min(max(wanted, floor), current)  # desconto nunca sobe o preço
            if new == floor and floor > wanted:
                floor_hits += 1
            else:
                full += 1
            originals.setdefault(key, str(current))
        if new == current:
            continue
        line = f"{x['external_id']} R$ {current} → R$ {new}"
        if args.dry_run:
            print("~", line)
            continue
        r = c.put(f"/mercadolivre/listings/{x['id']}/price", json={"price": str(new)})
        if r.status_code == 200:
            print("+", line)
        else:
            fails += 1
            print("x", line, r.text[:160])
        if not args.desfazer:
            STATE.write_text(json.dumps(originals))
        time.sleep(0.5)
    if args.desfazer and not args.dry_run:
        STATE.unlink(missing_ok=True)
    print(f"{args.pct}% cheio: {full} | no mínimo sem prejuízo: {floor_hits} | falhas: {fails}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
