"""Robô de ativação (carga inicial do acervo): deixa os produtos importados à venda.

O que faz (idempotente — pode rodar de novo quando o robô do acervo terminar mais coleções):
1. Cadastra o que falta para ter preço: impressora (Bambu Lab A1 + AMS lite), cores de PLA e
   tarifas do site (Pix/cartão do Mercado Pago) — valores PROVISÓRIOS, ajustáveis no painel.
2. Preenche a licença das coleções do acervo (declarada pelo dono, que assume a responsabilidade).
3. Para cada produto do acervo sem variante: estima gramas e tempo pelo VOLUME REAL medido da
   malha (não é IA): gramas = volume x densidade x fração de preenchimento; tempo = gramas /
   vazão típica + preparo. Marca a variante como estimativa (o fatiador substitui depois).
4. Ativa o produto (se o Guardião aprovar).

Uso: python tools/robo_ativar.py --api http://<servidor>:39000 [--acervo <pasta>] [--dry-run]
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import httpx

LICENSE = (
    "Licença comercial declarada pelo dono para a carga inicial do acervo comprado "
    "(07/10/2026); o dono assume a responsabilidade"
)
PRINTER = {
    "name": "Bambu Lab A1",
    "model": "A1 + AMS lite (aberta)",
    "bed_x_mm": 256,
    "bed_y_mm": 256,
    "bed_z_mm": 256,
    "avg_watts": 110,
    "hourly_wear": "0.50",
    "enclosed": False,
    "has_ams": True,
    "supported_materials": ["PLA", "PETG", "TPU"],
    "status": "ativa",
}
COLORS = [  # PLA provisório: R$ 120/kg, 1 kg em estoque (ajuste no painel)
    ("Branco", "#FFFFFF"),
    ("Preto", "#1E1E1E"),
    ("Dourado", "#C9A227"),
    ("Azul bebê", "#9CC9F0"),
    ("Rosa bebê", "#F4B6C2"),
]
FEES = [  # Mercado Pago, provisório até o print das taxas reais
    {
        "channel": "site_pix",
        "commission_rate": "0.0099",
        "notes": "provisório: confirmar no Mercado Pago",
    },
    {
        "channel": "site_card",
        "commission_rate": "0.0498",
        "notes": "provisório: confirmar no Mercado Pago",
    },
]
PLA_DENSITY = 1.24  # g/cm³
FLOW_G_PER_H = 14.0  # vazão típica da A1 em qualidade padrão
SETUP_S = 600  # aquecimento, calibração, troca


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# Tamanho padrão (maior medida, mm) quando o arquivo vem sem escala real (ex.: cubo de 1 mm)
SIZE_RULES = [
    (("chaveiro", "pingente", "marcador", "medalh", "terço", "terco"), 50),
    (("infantil", "kids", "bebê", "bebe", "criança", "crianca"), 100),
]
DEFAULT_SIZE_MM = 150


def target_size(text: str) -> int:
    low = text.lower()
    for words, size in SIZE_RULES:
        if any(w in low for w in words):
            return size
    return DEFAULT_SIZE_MM


def local_volume(path: Path, size_mm: int) -> tuple[float, list[float]]:
    """Volume (cm³) e medidas (mm) da peça escalada; malha aberta é fechada por voxels."""
    import trimesh  # só aqui: o robô 1 não precisa

    mesh = trimesh.load(path, force="mesh")
    mesh.apply_scale(size_mm / float(max(mesh.extents)))
    try:
        volume = float(mesh.voxelized(pitch=size_mm / 80).fill().volume)
    except Exception:
        volume = float(mesh.convex_hull.volume) * 0.5
    return volume / 1000, [round(float(v), 1) for v in mesh.extents]


def estimate(volume_cm3: float) -> tuple[float, int]:
    """(gramas, segundos). Peças pequenas saem quase maciças (paredes); grandes, ~30-40%."""
    side = volume_cm3 ** (1 / 3) if volume_cm3 > 0 else 1
    fill = min(1.0, max(0.25, 0.2 + 2.0 / side))
    grams = max(3.0, round(volume_cm3 * PLA_DENSITY * fill, 1))
    seconds = max(1200, int(grams / FLOW_G_PER_H * 3600) + SETUP_S)
    return grams, seconds


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--api", required=True)
    ap.add_argument("--acervo", type=Path, default=Path.home() / "Projetos" / "acervo-catolico-3d")
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
        timeout=60,
    )

    def request(method: str, path: str, **kw: Any) -> httpx.Response:
        for attempt in range(5):
            try:
                res = http.request(method, path, **kw)
            except httpx.HTTPError:
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))
                continue
            if res.status_code >= 500 and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            return res
        raise RuntimeError("sem resposta")

    def call(method: str, path: str, **kw: Any) -> Any:
        res = request(method, path, **kw)
        if res.status_code == 401:
            sys.exit("Token de robô recusado: gere outro no painel.")
        if res.status_code >= 400:
            raise RuntimeError(f"{method} {path} → {res.status_code}: {res.text[:300]}")
        return res.json() if res.content else None

    # 1) Base para ter preço
    if not call("GET", "/printers"):
        log("cadastrando impressora Bambu Lab A1")
        if not args.dry_run:
            call("POST", "/printers", json=PRINTER)
    existing = {(m["kind"], m["color_name"]) for m in call("GET", "/materials")}
    for name, hexa in COLORS:
        if ("PLA", name) not in existing:
            log(f"cadastrando PLA {name}")
            if not args.dry_run:
                call(
                    "POST",
                    "/materials",
                    json={
                        "kind": "PLA",
                        "color_name": name,
                        "color_hex": hexa,
                        "price_per_kg": "120",
                        "stock_grams": 1000,
                        "supplier": "provisório",
                    },
                )
    have_fees = {b["channel"] for b in call("GET", "/channel-fees")}
    for fee in FEES:
        if fee["channel"] not in have_fees:
            log(f"cadastrando tarifa {fee['channel']} ({fee['commission_rate']})")
            if not args.dry_run:
                call("POST", "/channel-fees", json=fee)
    white = next(
        (
            m["id"]
            for m in call("GET", "/materials")
            if m["kind"] == "PLA" and m["color_name"] == "Branco"
        ),
        None,
    )

    # 2) Licença das coleções do acervo
    collections = [
        c for c in call("GET", "/library/collections") if c["slug"].startswith("acervo-catolico")
    ]
    for col in collections:
        if not col.get("license_text"):
            log(f"licença: {col['title']}")
            if not args.dry_run:
                call(
                    "PUT",
                    f"/library/collections/{col['slug']}/license",
                    json={"license_text": LICENSE},
                )

    # índice dos arquivos locais (nome original → caminho) para medir quem veio sem escala
    local_index: dict[str, Path] = {}
    for path in args.acervo.rglob("*"):
        if path.suffix.lower() in (".stl", ".obj", ".3mf"):
            local_index.setdefault(path.name, path)
    # STL antes de 3MF quando o modelo tem os dois (3MF costuma repetir a mesma peça)

    # 3+4) Variante estimada e ativação
    done = skipped = blocked = 0
    for col in collections:
        for model in call("GET", f"/library/collections/{col['slug']}/models"):
            pid = model.get("product_id")
            if model["status"] != "produto" or not pid:
                continue
            product = call("GET", f"/products/{pid}")
            if product["variants"]:
                continue
            mesh_files = [
                f for f in model["files"] if f["name"].rsplit(".", 1)[-1] in ("stl", "obj", "3mf")
            ]
            main = next((f for f in mesh_files if not f["name"].endswith(".3mf")), None) or (
                mesh_files[0] if mesh_files else None
            )
            if main is None:
                skipped += 1
                log(f"  pulado: {product['title']} — sem malha")
                continue
            real_scale = (main.get("bbox_mm") and max(main["bbox_mm"]) >= 5) and main.get(
                "volume_cm3"
            )
            note = "volume da malha"
            if real_scale:
                volume, bbox = (
                    float(main["volume_cm3"]),
                    [round(float(v), 1) for v in main["bbox_mm"]],
                )
                if model.get("fits") is False:
                    skipped += 1
                    log(f"  pulado: {product['title']} — maior que a mesa (dividir)")
                    continue
            else:
                local = local_index.get(main.get("original", ""))
                if local is None:
                    skipped += 1
                    log(f"  pulado: {product['title']} — arquivo local não encontrado")
                    continue
                size = target_size(f"{product['title']} {col['title']}")
                try:
                    volume, bbox = local_volume(local, size)
                except Exception as exc:
                    skipped += 1
                    log(f"  pulado: {product['title']} — arquivo não abriu ({type(exc).__name__})")
                    continue
                note = f"sem escala no arquivo: padrão {size} mm, volume fechado por voxels"
            grams, seconds = estimate(volume)
            if args.dry_run:
                log(f"  {product['title']}: {grams} g, {seconds // 60} min")
                continue
            call(
                "POST",
                f"/products/{pid}/variants",
                json={
                    "size_label": f"{round(max(bbox) / 10)} cm" if bbox else None,
                    "dims_mm": bbox or None,
                    "grams_by_material": {str(white): grams},
                    "print_seconds": seconds,
                    "post_minutes": 5,
                    "params": {"estimativa": True, "origem": note},
                },
            )
            res = request("PATCH", f"/products/{pid}", json={"status": "ativo"})
            if res.status_code >= 400 or res.json().get("guardian_status") != "aprovado":
                blocked += 1
                log(f"  ativação barrada: {product['title']} — {res.text[:160]}")
            else:
                done += 1
                log(f"  ✓ {product['title']}: {grams} g, {seconds // 60} min")
    log(f"Fim: {done} ativados, {blocked} barrados pelo Guardião, {skipped} pulados.")


if __name__ == "__main__":
    main()
