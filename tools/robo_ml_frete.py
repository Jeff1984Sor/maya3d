"""Robô do dono: liga (ou desliga) o frete grátis nos anúncios publicados no Mercado Livre.

Frete grátis = o ML cobra o frete do vendedor em cada venda. Teste antes com --so-um.

    python tools/robo_ml_frete.py --api https://api.<dominio> [--so-um] [--desligar]
        [--conta-nova-desde N]

Token em ~/Downloads/robo-token.txt (painel → Integrações → Robô).
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="endereço HTTPS da API (Integrações)")
    ap.add_argument("--so-um", action="store_true", help="só o primeiro anúncio (teste)")
    ap.add_argument("--desligar", action="store_true", help="tira o frete grátis")
    ap.add_argument(
        "--conta-nova-desde",
        type=int,
        default=0,
        help="anúncios com id até este número são da conta antiga: ficam de fora",
    )
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    listings = [
        x
        for x in c.get("/mercadolivre/listings").json()
        if x["status"] == "publicado" and x["id"] > args.conta_nova_desde
    ]
    if args.so_um:
        listings = listings[:1]
    enabled = not args.desligar
    print(f"{len(listings)} anúncio(s) | frete grátis: {'liga' if enabled else 'desliga'}")
    ok = 0
    for x in listings:
        r = c.put(f"/mercadolivre/listings/{x['id']}/free-shipping", json={"enabled": enabled})
        if r.status_code == 200 and r.json()["free_shipping"] == enabled:
            ok += 1
            print(f"+ {x['external_id']} | {x['permalink']}")
        else:
            print(f"x {x['external_id']}: {r.status_code} {r.text[:300]}")
        time.sleep(1)
    print(f"alterados: {ok} de {len(listings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
