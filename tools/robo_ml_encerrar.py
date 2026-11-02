"""Robô do dono: ENCERRA e apaga todos os anúncios publicados no Mercado Livre (sem volta).

Usa a conta do ML conectada agora no painel — rode ANTES de trocar de conta. Depois disso
os produtos podem ser anunciados de novo (robo_ml_publicar.py) na conta nova.

    python tools/robo_ml_encerrar.py --api https://api.<dominio> [--dry-run]

Pede para digitar ENCERRAR antes de começar. Token em ~/Downloads/robo-token.txt.
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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    token = (pathlib.Path.home() / "Downloads" / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    account = c.get("/mercadolivre/status").json()
    listings = [x for x in c.get("/mercadolivre/listings").json() if x["status"] == "publicado"]
    print(f"conta conectada: {account.get('nickname')} | anúncios publicados: {len(listings)}")
    if args.dry_run or not listings:
        return 0
    if input("Isto apaga os anúncios no Mercado Livre. Digite ENCERRAR: ").strip() != "ENCERRAR":
        print("cancelado")
        return 1
    ok = 0
    for x in listings:
        r = c.delete(f"/mercadolivre/listings/{x['id']}")
        if r.status_code == 200:
            ok += 1
            print(f"- {x['external_id']} encerrado")
        else:
            print(f"x {x['external_id']}: {r.text[:300]}")
        time.sleep(1)
    print(f"encerrados: {ok} de {len(listings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
