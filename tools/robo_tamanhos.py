"""Robô de tamanhos e títulos (carga inicial do acervo).

Para cada produto do acervo:
1. A IA com visão olha a capa e diz o tipo da peça (medalha, imagem de santo, cruz...),
   com título curto e correto e descrição. A IA não dá medidas: o tipo escolhe P/M/G numa
   tabela fixa (product_from_photo.SIZES).
2. Recalcula gramas e tempo para cada tamanho pelo volume real da malha escalada (voxels),
   com a vazão da Bambu A1. A variante única vira P; M e G são criadas (a loja mostra P, M, G).

Idempotente: pula produto já marcado com params.tamanhos. Uso:
  python tools/robo_tamanhos.py --api http://<servidor>:39000 [--limite 3] [--dry-run]
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from robo_ativar import local_volume

FLOW_G_PER_H = 20.0  # Bambu A1, qualidade padrão, bico 0,4
SETUP_S = 600
PLA_DENSITY = 1.24
LABELS = ("P", "M", "G")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def estimate(volume_cm3: float) -> tuple[float, int]:
    side = volume_cm3 ** (1 / 3) if volume_cm3 > 0 else 1
    # paredes + 15% de preenchimento: peça pequena ~maciça, grande ~30%
    fill = min(1.0, max(0.15, 0.12 + 1.2 / side))
    grams = max(2.0, round(volume_cm3 * PLA_DENSITY * fill, 1))
    return grams, max(900, int(grams / FLOW_G_PER_H * 3600) + SETUP_S)


def unique(title: str, used: set[str]) -> str:
    base = " ".join(title.split())[:190] or "Peça"
    candidate, n = base, 2
    while candidate.lower() in used:
        candidate, n = f"{base} {n}", n + 1
    used.add(candidate.lower())
    return candidate


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--api", required=True)
    ap.add_argument("--acervo", type=Path, default=Path.home() / "Projetos" / "acervo-catolico-3d")
    ap.add_argument("--limite", type=int, default=0, help="só os N primeiros (teste)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(
        (Path.home() / "Downloads").glob("robo-token*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        sys.exit("Token não encontrado: painel → Integrações → Robô → Gerar token.")
    http = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin",
        headers={"x-robot-token": files[0].read_text(encoding="utf-8").strip()},
        timeout=httpx.Timeout(30, read=180),
    )

    def call(method: str, path: str, **kw: Any) -> Any:
        for attempt in range(5):
            try:
                res = http.request(method, path, **kw)
            except httpx.HTTPError:
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))
                continue
            if res.status_code == 401:
                sys.exit("Token de robô recusado: gere outro no painel.")
            if res.status_code >= 500 and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            if res.status_code >= 400:
                raise RuntimeError(f"{method} {path} → {res.status_code}: {res.text[:300]}")
            return res.json() if res.content else None
        return None

    local_index: dict[str, Path] = {}
    for path in args.acervo.rglob("*"):
        if path.suffix.lower() in (".stl", ".obj", ".3mf"):
            local_index.setdefault(path.name, path)

    used = {p["title"].lower() for p in call("GET", "/products")}
    done = failed = 0
    collections = [
        c for c in call("GET", "/library/collections") if c["slug"].startswith("acervo-catolico")
    ]
    for col in collections:
        for model in call("GET", f"/library/collections/{col['slug']}/models"):
            pid = model.get("product_id")
            if model["status"] != "produto" or not pid:
                continue
            if args.limite and done + failed >= args.limite:
                break
            product = call("GET", f"/products/{pid}")
            variants = product["variants"]
            if not variants or (variants[0].get("params") or {}).get("tamanhos"):
                continue
            mesh_files = [
                f for f in model["files"] if f["name"].rsplit(".", 1)[-1] in ("stl", "obj", "3mf")
            ]
            main = next((f for f in mesh_files if not f["name"].endswith(".3mf")), None) or (
                mesh_files[0] if mesh_files else None
            )
            local = local_index.get((main or {}).get("original", ""))
            if local is None:
                failed += 1
                log(f"  pulado: {product['title']} — arquivo local não encontrado")
                continue
            try:
                photo = call("POST", f"/ai/products/{pid}/from-photo")
            except RuntimeError as exc:
                failed += 1
                log(f"  IA falhou em {product['title']}: {str(exc)[:160]}")
                continue
            used.discard(product["title"].lower())
            title = unique(photo["title"], used)
            sizes = photo["sizes_mm"]
            plan = []
            try:
                for label, size in zip(LABELS, sizes, strict=True):
                    volume, dims = local_volume(local, int(size))
                    grams, seconds = estimate(volume)
                    plan.append((label, int(size), dims, grams, seconds))
            except Exception as exc:
                failed += 1
                log(f"  pulado: {product['title']} — malha não abriu ({type(exc).__name__})")
                continue
            summary = ", ".join(f"{lb} {s // 10} cm {g} g" for lb, s, _, g, _ in plan)
            log(f"  {product['title']} → {title} [{photo['kind']}] {summary}")
            if args.dry_run:
                done += 1
                continue
            try:
                call(
                    "PATCH",
                    f"/products/{pid}",
                    json={
                        "title": title,
                        "description": photo["description"],
                        "tags": photo["tags"][:10],
                    },
                )
                white = next(iter(variants[0]["grams_by_material"] or {}), None)
                for i, (label, size, dims, grams, seconds) in enumerate(plan):
                    body = {
                        "size_label": f"{label} · {size // 10} cm",
                        "dims_mm": dims,
                        "grams_by_material": {white: grams},
                        "print_seconds": seconds,
                        "post_minutes": 5,
                        "params": {
                            "estimativa": True,
                            "tamanhos": True,
                            "tipo": photo["kind"],
                            "altura_mm": size,
                        },
                    }
                    if i == 0:
                        call("PATCH", f"/products/{pid}/variants/{variants[0]['id']}", json=body)
                    else:
                        call("POST", f"/products/{pid}/variants", json=body)
            except RuntimeError as exc:  # um produto com erro não para o robô
                failed += 1
                log(f"  erro em {product['title']}: {str(exc)[:160]}")
                continue
            done += 1
    log(f"Fim: {done} produtos com P/M/G e título revisado; {failed} com problema.")


if __name__ == "__main__":
    main()
