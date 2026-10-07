"""Foto vira peça (spec 3, IA voltada ao cliente, item 5): quatro modos determinísticos.

- litofania: espessura proporcional ao escuro (contra a luz, a foto aparece)
- placa multicor: quantização em 2-4 cores → faixas de altura (uma cor por faixa)
- cortador de biscoito: contorno da silhueta vira parede de corte com aba
- chaveiro de silhueta: contorno extrudado com furo para argola

Sem IA externa. A análise visual de direitos (Guardião visual) é etapa separada.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import trimesh
from PIL import Image, ImageFilter, ImageOps
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

MAX_SIDE_PX = 700  # limita a malha (desempenho) sem perder detalhe útil para impressão


class PhotoError(Exception):
    pass


@dataclass
class PhotoResult:
    parts: dict[str, trimesh.Trimesh]  # nome → malha (uma por cor quando multicor)
    combined: trimesh.Trimesh
    info: dict[str, object] = field(default_factory=dict)


def load_image(data: bytes) -> Image.Image:
    try:
        opened = Image.open(io.BytesIO(data))
        rotated = ImageOps.exif_transpose(opened)  # respeita a rotação da câmera do celular
        return (rotated or opened).convert("RGB")
    except Exception as exc:
        raise PhotoError(f"imagem ilegível: {exc}") from exc


def _resize_for(img: Image.Image, width_mm: float, pitch_mm: float) -> Image.Image:
    cols = int(min(MAX_SIDE_PX, max(10, round(width_mm / pitch_mm))))
    rows = max(10, round(cols * img.height / img.width))
    if rows > MAX_SIDE_PX:
        rows = MAX_SIDE_PX
        cols = max(10, round(rows * img.width / img.height))
    return img.resize((cols, rows), Image.Resampling.LANCZOS)


def heightfield_mesh(heights: np.ndarray, pitch_mm: float) -> trimesh.Trimesh:
    """Sólido fechado: topo = mapa de alturas (linha 0 = topo da imagem), fundo plano em z=0."""
    rows, cols = heights.shape
    if rows < 2 or cols < 2:
        raise PhotoError("imagem pequena demais")
    jj, ii = np.meshgrid(np.arange(cols), np.arange(rows))
    x = jj * pitch_mm
    y = (rows - 1 - ii) * pitch_mm
    top = np.column_stack([x.ravel(), y.ravel(), heights.ravel()])
    bottom = np.column_stack([x.ravel(), y.ravel(), np.zeros(rows * cols)])
    vertices = np.vstack([top, bottom])
    n = rows * cols

    idx = np.arange(n).reshape(rows, cols)
    a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    c, d = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    # topo visto de cima (z+) em sentido anti-horário; y diminui quando a linha aumenta
    top_faces = np.vstack([np.column_stack([a, c, b]), np.column_stack([b, c, d])])
    bottom_faces = top_faces[:, ::-1] + n

    def wall(edge: np.ndarray) -> np.ndarray:
        t0, t1 = edge[:-1], edge[1:]
        return np.vstack([np.column_stack([t0, t1, t1 + n]), np.column_stack([t0, t1 + n, t0 + n])])

    # contorno percorrido no sentido horário visto de cima → normais das paredes para fora
    walls = np.vstack(
        [
            wall(idx[0, :]),  # topo da imagem (y máximo), esquerda → direita
            wall(idx[:, -1]),  # direita, de cima para baixo
            wall(idx[-1, ::-1]),  # base, direita → esquerda
            wall(idx[::-1, 0]),  # esquerda, de baixo para cima
        ]
    )
    faces = np.vstack([top_faces, bottom_faces, walls])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    mesh.fix_normals()
    return mesh


def lithophane(
    img: Image.Image,
    *,
    width_mm: float = 100.0,
    min_mm: float = 0.8,
    max_mm: float = 3.0,
    pitch_mm: float = 0.25,
    frame_mm: float = 3.0,
) -> PhotoResult:
    if not 0.4 <= min_mm < max_mm <= 8:
        raise PhotoError("espessuras inválidas (mín. 0,4 mm e máx. maior que o mínimo)")
    gray = ImageOps.autocontrast(_resize_for(img, width_mm, pitch_mm).convert("L"))
    lum = np.asarray(gray, dtype=float) / 255.0
    heights = min_mm + (1.0 - lum) * (max_mm - min_mm)  # escuro = mais grosso
    if frame_mm > 0:
        k = max(1, round(frame_mm / pitch_mm))
        heights[:k, :] = heights[-k:, :] = max_mm + 0.5
        heights[:, :k] = heights[:, -k:] = max_mm + 0.5
    mesh = heightfield_mesh(heights, pitch_mm)
    return PhotoResult(
        parts={"litofania": mesh},
        combined=mesh,
        info={"dica": "imprima em pé, 100% de preenchimento, filamento branco"},
    )


def multicolor_plate(
    img: Image.Image,
    *,
    width_mm: float = 100.0,
    colors: int = 4,
    base_mm: float = 1.0,
    layer_mm: float = 0.6,
    pitch_mm: float = 0.3,
) -> PhotoResult:
    """Cada cor vira uma faixa de altura; a cor visível é a do topo. Clara embaixo, escura em cima.

    Partes = faixas horizontais (uma por cor) para AMS; sem AMS, trocar o filamento nas alturas.
    """
    if not 2 <= colors <= 4:
        raise PhotoError("use de 2 a 4 cores")
    small = _resize_for(img, width_mm, pitch_mm).filter(ImageFilter.MedianFilter(3))
    quantized = small.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    labels = np.asarray(quantized)
    pixels = np.asarray(small, dtype=float)
    used = sorted(set(labels.ravel().tolist()))
    # cor real de cada região = mediana dos pixels originais (a paleta da quantização é média)
    palette = {i: np.median(pixels[labels == i], axis=0) for i in used}
    luminance = {
        i: 0.299 * palette[i][0] + 0.587 * palette[i][1] + 0.114 * palette[i][2] for i in used
    }
    order = sorted(used, key=lambda i: -luminance[i])  # mais clara primeiro (base)
    rank = {label: r for r, label in enumerate(order)}
    heights = base_mm + np.vectorize(rank.get)(labels).astype(float) * layer_mm
    combined = heightfield_mesh(heights, pitch_mm)

    parts: dict[str, trimesh.Trimesh] = {}
    bands: list[dict[str, object]] = []
    lo, hi = combined.bounds
    for r, label in enumerate(order):
        z0 = 0.0 if r == 0 else base_mm + (r - 1) * layer_mm
        z1 = base_mm + r * layer_mm
        band = trimesh.creation.box(bounds=[[lo[0] - 1, lo[1] - 1, z0], [hi[0] + 1, hi[1] + 1, z1]])
        slab = combined.intersection(band, engine="manifold")
        hex_color = "#{:02X}{:02X}{:02X}".format(*(int(v) for v in palette[label]))
        name = f"cor_{r + 1}"
        if not slab.is_empty:
            parts[name] = slab
        bands.append(
            {"parte": name, "cor": hex_color, "de_mm": round(z0, 2), "ate_mm": round(z1, 2)}
        )
    return PhotoResult(
        parts=parts,
        combined=combined,
        info={
            "faixas": bands,
            "trocar_filamento_em_mm": [b["de_mm"] for b in bands[1:]],
            "dica": "com AMS: uma cor por parte; sem AMS: pausa e troca nas alturas indicadas",
        },
    )


def _otsu(gray: np.ndarray) -> float:
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_all = float(np.dot(np.arange(256), hist))
    weight_b = sum_b = 0.0
    best, threshold = -1.0, 128.0
    for t in range(256):
        weight_b += hist[t]
        if weight_b == 0 or weight_b == total:
            continue
        sum_b += t * hist[t]
        mean_b = sum_b / weight_b
        mean_f = (sum_all - sum_b) / (total - weight_b)
        between = weight_b * (total - weight_b) * (mean_b - mean_f) ** 2
        if between > best:
            best, threshold = between, float(t)
    return threshold


def silhouette(img: Image.Image, *, size_mm: float, invert: bool = False) -> Polygon:
    """Contorno do objeto principal (escuro sobre fundo claro; `invert` para o contrário)."""
    pitch = 0.4
    small = _resize_for(img, size_mm, pitch).convert("L").filter(ImageFilter.MedianFilter(5))
    gray = np.asarray(small, dtype=float)
    if gray.max() - gray.min() < 30:
        raise PhotoError("imagem sem contraste: use um desenho escuro sobre fundo claro")
    mask = gray > _otsu(gray) if invert else gray <= _otsu(gray)
    coverage = float(mask.mean())
    if not 0.005 <= coverage <= 0.95:
        raise PhotoError("não achei uma forma separada do fundo (tente inverter)")
    rows = mask.shape[0]
    runs: list[BaseGeometry] = []
    for i in range(rows):
        line = np.concatenate([[False], mask[i], [False]]).astype(np.int8)
        starts = np.flatnonzero(np.diff(line) == 1)
        ends = np.flatnonzero(np.diff(line) == -1)
        y = (rows - 1 - i) * pitch
        runs += [box(s * pitch, y, e * pitch, y + pitch) for s, e in zip(starts, ends, strict=True)]
    if not runs:
        raise PhotoError("não achei nenhuma forma na imagem (tente inverter)")
    merged = unary_union(runs).buffer(0.2).buffer(-0.2)
    shapes = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]
    shape = max(shapes, key=lambda g: g.area)
    if shape.area < 25:
        raise PhotoError("forma pequena demais")
    outline = Polygon(shape.exterior).simplify(0.2)  # silhueta cheia (sem furos)
    minx, miny, maxx, maxy = outline.bounds
    scale = size_mm / max(maxx - minx, maxy - miny)
    from shapely import affinity

    scaled = affinity.scale(outline, scale, scale, origin=(minx, miny))
    if not isinstance(scaled, Polygon):
        raise PhotoError("contorno inválido")
    return scaled


def _extrude(poly: BaseGeometry, height: float) -> trimesh.Trimesh:
    shapes = list(poly.geoms) if hasattr(poly, "geoms") else [poly]
    meshes = [
        trimesh.creation.extrude_polygon(p, height)
        for p in shapes
        if isinstance(p, Polygon) and p.area > 0.01
    ]
    if not meshes:
        raise PhotoError("forma vazia após o processamento")
    result = trimesh.util.concatenate(meshes)
    return result if isinstance(result, trimesh.Trimesh) else meshes[0]


def cookie_cutter(
    img: Image.Image,
    *,
    size_mm: float = 80.0,
    wall_mm: float = 1.2,
    height_mm: float = 12.0,
    flange_mm: float = 3.0,
    flange_height_mm: float = 1.6,
    invert: bool = False,
) -> PhotoResult:
    shape = silhouette(img, size_mm=size_mm, invert=invert)
    blade = shape.buffer(wall_mm, join_style="round").difference(shape)
    flange = shape.buffer(wall_mm + flange_mm, join_style="round").difference(shape)
    mesh = _extrude(blade, height_mm).union(_extrude(flange, flange_height_mm), engine="manifold")
    return PhotoResult(
        parts={"cortador": mesh},
        combined=mesh,
        info={"aviso": "uso rápido; lave após o uso; não para contato prolongado com alimento"},
    )


def silhouette_keychain(
    img: Image.Image,
    *,
    size_mm: float = 50.0,
    thickness_mm: float = 4.0,
    hole_mm: float = 4.5,
    invert: bool = False,
) -> PhotoResult:
    shape = silhouette(img, size_mm=size_mm, invert=invert)
    minx, _, maxx, maxy = shape.bounds
    ring_r = hole_mm / 2 + 2.5
    center = Point((minx + maxx) / 2, maxy + ring_r * 0.6)
    tab = center.buffer(ring_r).union(
        box(center.x - ring_r * 0.7, maxy - 3, center.x + ring_r * 0.7, center.y)
    )
    outline = shape.union(tab).difference(center.buffer(hole_mm / 2))
    mesh = _extrude(outline, thickness_mm)
    return PhotoResult(parts={"chaveiro": mesh}, combined=mesh, info={})


MODES: dict[str, Callable[..., PhotoResult]] = {
    "litofania": lithophane,
    "placa_multicor": multicolor_plate,
    "cortador": cookie_cutter,
    "chaveiro_silhueta": silhouette_keychain,
}
