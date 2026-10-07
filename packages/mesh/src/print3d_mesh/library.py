"""Biblioteca de modelos: organiza uma pasta baixada (acervo comprado, pacote de STL) em
modelos prontos para virar produto.

1. Extrai ZIPs com segurança (sem sair da pasta, com limite de tamanho, sem ZIP dentro de ZIP).
2. Agrupa: cada pasta com malha vira um modelo; malhas soltas na raiz viram um modelo cada.
3. Copia para nomes seguros (`a-z0-9._-`) e analisa cada malha (medidas, volume, fechamento).
4. Escolhe a capa (imagem da pasta) e devolve um manifesto JSON.

Nada aqui fala com a internet: os arquivos são os que o dono enviou pelo painel.
"""

import re
import shutil
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import trimesh

from print3d_mesh.analysis import mesh_report

MESH_EXT = {".stl", ".3mf", ".obj"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
MAX_UNZIPPED_BYTES = 3 * 1024**3  # por ZIP
MAX_ANALYZE_BYTES = 400 * 1024**2  # malha maior que isso: registra sem analisar


class LibraryError(Exception):
    pass


def safe_name(name: str) -> str:
    """Nome de arquivo seguro para URL e disco, preservando a extensão."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]  # nunca um caminho
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:
        stem, ext = name, ""
    ext = re.sub(r"[^a-z0-9]", "", ext.lower())[:5]
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode().lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem.replace("+", " ")).strip("-")[:80] or "arquivo"
    return f"{stem}.{ext.lower()}" if ext else stem


def pretty_title(name: str) -> str:
    """'gold+heart keychain 3d model' → 'Gold heart keychain'."""
    text = re.sub(r"[_+\-]+", " ", Path(name).stem)
    text = re.sub(r"\b(3d|model|stl|3mf|obj|final|v\d+)\b", " ", text, flags=re.IGNORECASE)
    text = " ".join(text.split())
    return text[:1].upper() + text[1:] if text else name


def extract_zips(root: Path) -> list[str]:
    """Extrai cada .zip para uma pasta irmã com o mesmo nome. Devolve avisos."""
    warnings: list[str] = []
    for archive in sorted(root.rglob("*.zip")):
        target = archive.with_suffix("")
        try:
            with zipfile.ZipFile(archive) as zf:
                total = sum(i.file_size for i in zf.infolist())
                if total > MAX_UNZIPPED_BYTES:
                    warnings.append(f"{archive.name}: grande demais para extrair ({total} bytes)")
                    continue
                for info in zf.infolist():
                    rel = PurePosixPath(info.filename)
                    if info.is_dir() or rel.suffix.lower() == ".zip":
                        continue
                    if rel.is_absolute() or ".." in rel.parts:
                        warnings.append(f"{archive.name}: caminho perigoso ignorado ({rel})")
                        continue
                    dest = target.joinpath(*rel.parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, dest.open("wb") as out:
                        shutil.copyfileobj(src, out)
        except zipfile.BadZipFile:
            warnings.append(f"{archive.name}: ZIP corrompido")
    return warnings


def _analyze(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    info: dict[str, Any] = {"bytes": size}
    if size > MAX_ANALYZE_BYTES:
        info["issues"] = ["arquivo muito grande: analisar no fatiador"]
        return info
    try:
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:  # arquivo ilegível não derruba o acervo inteiro
        info["issues"] = [f"não abriu: {type(exc).__name__}"]
        return info
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        info["issues"] = ["arquivo sem malha"]
        return info
    report = mesh_report(mesh)
    info.update(
        bbox_mm=list(report.bbox_mm),
        volume_cm3=round(report.volume_mm3 / 1000, 1),
        triangles=report.triangles,
        watertight=report.watertight,
        issues=report.issues,
    )
    return info


def fits(bbox: list[float] | None, bed: tuple[float, float, float]) -> bool | None:
    """Cabe na mesa em alguma orientação (girando os eixos)."""
    if not bbox:
        return None
    return all(a <= b for a, b in zip(sorted(bbox), sorted(bed), strict=True))


def organize(raw: Path, out: Path, bed: tuple[float, float, float]) -> dict[str, Any]:
    """Pasta baixada (`raw`) → modelos organizados em `out/<chave>/` + manifesto."""
    warnings = extract_zips(raw)
    groups: dict[Path, list[Path]] = {}
    for path in sorted(raw.rglob("*")):
        if path.is_file() and path.suffix.lower() in MESH_EXT:
            groups.setdefault(path.parent, []).append(path)

    models: list[dict[str, Any]] = []
    # envios novos somam aos modelos que já existem: nunca sobrescreve uma pasta
    used: set[str] = {p.name for p in out.iterdir()} if out.is_dir() else set()
    for folder, meshes in groups.items():
        # malhas soltas na raiz: um modelo por arquivo; em subpasta: a pasta é o modelo
        units = [[m] for m in meshes] if folder == raw else [meshes]
        for unit in units:
            base = unit[0].stem if folder == raw else folder.name
            if base.isdigit() or len(base) < 3:  # pastas "1", "2": usa o nome do arquivo
                base = unit[0].stem
            key = safe_name(base)
            while key in used:
                key = f"{key}-{len(used)}"
            used.add(key)
            dest = out / key
            dest.mkdir(parents=True, exist_ok=True)
            files = []
            for mesh_path in unit:
                name = safe_name(mesh_path.name)
                shutil.copy2(mesh_path, dest / name)
                files.append({"name": name, "original": mesh_path.name, **_analyze(dest / name)})
            images = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT]
            cover = None
            if images:
                best = max(images, key=lambda p: p.stat().st_size)
                cover = safe_name(best.name)
                shutil.copy2(best, dest / cover)
            # STL/OBJ primeiro (3MF costuma repetir a mesma peça com cores/perfil)
            analyzed = [f for f in files if "bbox_mm" in f]
            main = next((f for f in analyzed if not f["name"].endswith(".3mf")), None) or (
                analyzed[0] if analyzed else None
            )
            bbox = main["bbox_mm"] if main else None
            models.append(
                {
                    "key": key,
                    "title": pretty_title(base),
                    "files": files,
                    "cover": cover,
                    "bbox_mm": bbox,
                    "fits": fits(bbox, bed),
                    "issues": sorted({i for f in files for i in f.get("issues", [])}),
                }
            )
    return {"models": models, "warnings": warnings}
