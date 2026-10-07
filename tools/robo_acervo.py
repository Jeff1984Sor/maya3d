"""Robô do acervo: sobe pastas de modelos 3D para a Biblioteca e cria produtos enriquecidos
pela IA. Roda no computador do dono (onde estão os arquivos) e fala com a API de produção.

Uso:
  python tools/robo_acervo.py --acervo <pasta> --api http://<servidor>:39000 \
      [--token-file <arquivo>] [--dry-run] [--so-categoria "Cruzes e Crucifixos"]

- Token de robô: painel → Integrações → Robô → Gerar token (vale 7 dias). O navegador baixa
  robo-token.txt e o robô pega o mais recente em Downloads; nunca imprime o token.
- Retoma de onde parou: o progresso fica em <acervo>/robo-estado.json.
- Coleções por categoria do manifesto; cada pasta vai zipada (mantém a organização).
- Produtos nascem em RASCUNHO e bloqueados pelo Guardião até a licença da coleção ser
  preenchida no painel (o direito de vender é decisão do dono).
- Títulos repetidos ganham " 2", " 3"... no final.
"""

import argparse
import json
import re
import sys
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import httpx

SKIP_CATEGORIES = {"Mockups e Divulgação"}  # imagens de divulgação, não são peças
MESH_EXT = {".stl", ".3mf", ".obj", ".zip"}
NICHE = "religioso"


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Api:
    def __init__(self, base: str, token: str) -> None:
        self.http = httpx.Client(
            base_url=f"{base.rstrip('/')}/v1/admin",
            headers={"x-robot-token": token, "accept": "application/json"},
            timeout=httpx.Timeout(60, read=900, write=900),
        )

    def call(self, method: str, path: str, **kw: Any) -> Any:
        for attempt in range(4):
            try:
                res = self.http.request(method, path, **kw)
            except httpx.HTTPError as exc:
                if attempt == 3:
                    raise
                log(f"  rede falhou ({type(exc).__name__}), tentando de novo…")
                time.sleep(10 * (attempt + 1))
                continue
            if res.status_code == 401:
                sys.exit("Token de robô recusado: gere outro no painel (Integrações → Robô).")
            if res.status_code >= 500 and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            if res.status_code >= 400:
                raise RuntimeError(f"{method} {path} → {res.status_code}: {res.text[:300]}")
            return res.json() if res.content else None
        return None


def zip_folder(folder: Path, out: Path) -> Path:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())
    return out


def has_meshes(folder: Path) -> bool:
    return any(p.suffix.lower() in MESH_EXT for p in folder.rglob("*") if p.is_file())


def newest_token_file() -> Path | None:
    downloads = Path.home() / "Downloads"
    files = sorted(downloads.glob("robo-token*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def unique_title(title: str, used: set[str]) -> str:
    base = " ".join(title.split())[:190] or "Peça"
    candidate, n = base, 2
    while candidate.lower() in used:
        candidate, n = f"{base} {n}", n + 1
    used.add(candidate.lower())
    return candidate


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--acervo", required=True, type=Path)
    ap.add_argument("--api", required=True)
    ap.add_argument(
        "--token-file",
        type=Path,
        default=None,
        help="padrão: o robo-token*.txt mais recente na pasta Downloads",
    )
    ap.add_argument("--dry-run", action="store_true", help="só mostra o plano, não envia nada")
    ap.add_argument("--so-categoria", default=None)
    ap.add_argument("--sem-ia", action="store_true", help="cria os produtos sem enriquecer")
    args = ap.parse_args()

    root: Path = args.acervo
    manifest = json.loads((root / "manifesto.json").read_text(encoding="utf-8"))
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in manifest:
        folder = root / item["id"]
        if item["category"] in SKIP_CATEGORIES or not folder.is_dir() or not has_meshes(folder):
            continue
        if args.so_categoria and item["category"] != args.so_categoria:
            continue
        by_category.setdefault(item["category"], []).append(item)

    log(f"Plano: {sum(len(v) for v in by_category.values())} pastas em {len(by_category)} coleções")
    for cat, items in by_category.items():
        size = sum(
            f.stat().st_size for i in items for f in (root / i["id"]).rglob("*") if f.is_file()
        )
        log(f"  {cat}: {len(items)} pastas, {size / 1e6:.0f} MB")
    if args.dry_run:
        return

    token_file = args.token_file or newest_token_file()
    if token_file is None:
        sys.exit(
            "Token não encontrado: no painel, Integrações → Robô → Gerar token (baixa o arquivo)."
        )
    token = token_file.read_text(encoding="utf-8").strip()
    if not token.startswith("rb_"):
        sys.exit("O arquivo do token não parece um token de robô (começa com rb_).")
    api = Api(args.api, token)
    state_path = root / "robo-estado.json"
    state: dict[str, Any] = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"collections": {}, "uploaded": [], "processed": [], "models_done": {}}
    )

    def save() -> None:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    ai_on = not args.sem_ia
    if ai_on:
        st = api.call("GET", "/ai/status")
        if not st.get("configured") or not (st.get("models") or {}).get("default"):
            log("IA sem chave ou sem modelo 'dia a dia' escolhido: produtos sem enriquecimento.")
            ai_on = False

    used = {p["title"].lower() for p in api.call("GET", "/products") or []}

    for category, items in by_category.items():
        cslug = state["collections"].get(category)
        if not cslug:
            cslug = api.call(
                "POST",
                "/library/collections",
                json={
                    "title": f"Acervo Católico — {category}",
                    "niche": NICHE,
                    "category": slug(category),
                    "description": "Importado pelo robô a partir do acervo comprado.",
                },
            )["slug"]
            state["collections"][category] = cslug
            save()
            log(f"Coleção criada: {cslug}")

        for item in items:
            if item["id"] in state["uploaded"]:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                z = zip_folder(root / item["id"], Path(tmp) / f"{item['id']}.zip")
                log(f"  enviando {item['id']} ({z.stat().st_size / 1e6:.0f} MB)…")
                with z.open("rb") as fh:
                    api.call(
                        "POST",
                        f"/library/collections/{cslug}/files",
                        files={"file": (z.name, fh, "application/zip")},
                    )
            state["uploaded"].append(item["id"])
            save()

        if category not in state["processed"]:
            log(f"  organizando e analisando {category}…")
            try:
                api.call("POST", f"/library/collections/{cslug}/process")
            except RuntimeError as exc:
                if "envie arquivos" not in str(exc) and "já está processando" not in str(exc):
                    raise
            for _ in range(180):  # até 1 h
                cols = {c["slug"]: c for c in api.call("GET", "/library/collections")}
                status = cols[cslug]["status"]
                if status in ("pronto", "erro"):
                    break
                time.sleep(20)
            if status == "erro":
                log(f"  ⚠ erro ao processar {category}: {cols[cslug].get('error')}")
                continue
            state["processed"].append(category)
            save()

        hints = " / ".join(i["title"] for i in items)[:200]
        models = api.call("GET", f"/library/collections/{cslug}/models")
        for model in models:
            key = f"{cslug}:{model['id']}"
            if model["status"] != "novo" or key in state["models_done"]:
                continue
            suggestion: dict[str, Any] | None = None
            if ai_on:
                try:
                    res = api.call(
                        "POST",
                        "/ai/enrich-product",
                        json={
                            "hint": f"{model['title']} — peça religiosa impressa em 3D ({hints})"[
                                :480
                            ],
                            "niche": NICHE,
                            "category": slug(category),
                        },
                    )
                    suggestion = res["suggestion"]
                except RuntimeError as exc:
                    log(f"    IA falhou em '{model['title']}': {str(exc)[:120]}")
            title = unique_title((suggestion or {}).get("title") or model["title"], used)
            made = api.call("POST", f"/library/models/{model['id']}/product", json={"title": title})
            pid = made["product_id"]
            if suggestion:
                bullets = "\n".join(f"• {b}" for b in suggestion.get("bullets", []))
                api.call(
                    "PATCH",
                    f"/products/{pid}",
                    json={
                        "description": f"{suggestion.get('description', '')}\n\n{bullets}".strip(),
                        "tags": suggestion.get("tags", [])[:15],
                        "occasions": suggestion.get("occasions", [])[:6],
                        "subcategory": suggestion.get("subcategory"),
                    },
                )
            state["models_done"][key] = pid
            save()
            log(f"    ✓ {title} (produto {pid})")

    log(
        f"Fim: {len(state['models_done'])} produtos criados. "
        "Preencha a licença de cada coleção no painel."
    )


if __name__ == "__main__":
    main()
