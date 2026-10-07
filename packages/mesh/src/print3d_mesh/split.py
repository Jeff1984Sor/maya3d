"""Divide uma peça grande em pedaços que cabem na mesa, com furos para pinos de encaixe.

1. Plano: escolhe quantos cortes por eixo (menos pedaços possível) para que cada célula caiba
   na mesa em alguma orientação, com folga de borda.
2. Furos: em cada plano de corte interno, acha onde EXISTE material naquele plano (seção da
   malha) e abre furos cilíndricos atravessando o corte — metade em cada pedaço vizinho.
3. Corte: interseção booleana (manifold3d) da peça furada com cada célula → pedaços fechados.
4. Pinos: cilindros soltos (um por furo), um pouco menores que o furo, para imprimir e colar.
"""

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import numpy as np
import trimesh
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from print3d_mesh.analysis import fits_build_volume

# Eixos do plano de corte em ordem cíclica (mantém a transformação sem espelhamento).
_PLANE_AXES = {0: (1, 2), 1: (2, 0), 2: (0, 1)}
_MAX_CUTS_PER_AXIS = 12


class SplitError(Exception):
    pass


@dataclass(frozen=True)
class SplitOptions:
    bed_mm: tuple[float, float, float]
    margin_mm: float = 3.0  # folga de borda da mesa
    pin_diameter_mm: float = 4.0
    pin_depth_mm: float = 8.0  # profundidade de cada lado do corte
    clearance_mm: float = 0.25  # furo maior que o pino (encaixe)
    pin_spacing_mm: float = 30.0
    max_pins_per_face: int = 4
    smart_cuts: bool = True  # corta onde a emenda é menor (pescoços, vãos), não no meio
    protect_top_pct: float = 0.0  # 0-60: não cortar no topo (ex.: rosto/cabeça de imagem)
    min_segment_mm: float = 15.0
    label_joints: bool = True  # letra gravada nas duas faces de cada junção (A com A)
    label_size_mm: float = 5.0
    label_depth_mm: float = 0.6


@dataclass(frozen=True)
class SplitPlan:
    counts: tuple[int, int, int]
    cell_mm: tuple[float, float, float]

    @property
    def pieces(self) -> int:
        return self.counts[0] * self.counts[1] * self.counts[2]


@dataclass
class Piece:
    name: str
    index: tuple[int, int, int]
    mesh: trimesh.Trimesh
    fits: bool


@dataclass
class SplitResult:
    plan: SplitPlan
    pieces: list[Piece]
    pins: list[trimesh.Trimesh] = field(default_factory=list)
    faces_without_pins: int = 0
    cuts: dict[int, list[float]] = field(default_factory=dict)  # eixo → posições de corte
    seam_area_mm2: float = 0.0
    labels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def plan_split(extents: tuple[float, float, float], options: SplitOptions) -> SplitPlan:
    """Menor número de pedaços cujas células cabem na mesa (qualquer orientação)."""
    bed = tuple(b - options.margin_mm for b in options.bed_mm)
    if min(bed) <= 0:
        raise SplitError("mesa menor que a folga de borda")
    best: tuple[int, int, int, tuple[int, ...]] | None = None
    for counts in itertools.product(range(1, _MAX_CUTS_PER_AXIS + 1), repeat=3):
        cell = tuple(e / n for e, n in zip(extents, counts, strict=True))
        if not fits_build_volume(cell, bed, margin_mm=0):  # type: ignore[arg-type]
            continue
        key = (math.prod(counts), sum(counts), max(counts), counts)
        if best is None or key < best:
            best = key
    if best is None:
        raise SplitError("peça grande demais mesmo com o máximo de cortes")
    counts = best[3]
    cell = tuple(round(e / n, 2) for e, n in zip(extents, counts, strict=True))
    return SplitPlan(
        counts=cast(tuple[int, int, int], counts), cell_mm=cast(tuple[float, float, float], cell)
    )


def _section_polygon(mesh: trimesh.Trimesh, axis: int, coord: float) -> BaseGeometry | None:
    """Seção da malha no plano axis=coord, em coordenadas (u, v) do plano."""
    normal = np.zeros(3)
    normal[axis] = 1.0
    origin = np.zeros(3)
    origin[axis] = coord
    section = mesh.section(plane_origin=origin, plane_normal=normal)
    if section is None:
        return None
    u, v = _PLANE_AXES[axis]
    to_2d = np.zeros((4, 4))
    to_2d[0, u] = 1.0
    to_2d[1, v] = 1.0
    to_2d[2, axis] = 1.0
    to_2d[2, 3] = -coord
    to_2d[3, 3] = 1.0
    planar, _ = section.to_2D(to_2D=to_2d, check=False)
    polygons = [p for p in planar.polygons_full if p is not None and p.area > 0]
    return unary_union(polygons) if polygons else None


def _pin_points(area: BaseGeometry, options: SplitOptions) -> list[tuple[float, float]]:
    """Pontos para pinos dentro do material, longe das bordas."""
    safe = area.buffer(-(options.pin_diameter_mm / 2 + 2.0))
    if safe.is_empty:
        return []
    minx, miny, maxx, maxy = safe.bounds
    step = options.pin_spacing_mm
    candidates = [
        (x, y)
        for x in np.arange(minx + step / 2, maxx, step)
        for y in np.arange(miny + step / 2, maxy, step)
        if safe.contains(Point(x, y))
    ]
    if not candidates:
        p = safe.representative_point()
        candidates = [(p.x, p.y)]
    if len(candidates) > options.max_pins_per_face:
        # espalha: pega os mais distantes entre si, começando pelo mais central
        center = safe.centroid
        chosen = [min(candidates, key=lambda c: Point(c).distance(center))]
        while len(chosen) < options.max_pins_per_face:
            chosen.append(
                max(candidates, key=lambda c: min(Point(c).distance(Point(o)) for o in chosen))
            )
        candidates = chosen
    return [(float(x), float(y)) for x, y in candidates]


def _cylinder(axis: int, center: np.ndarray, radius: float, length: float) -> trimesh.Trimesh:
    cyl = trimesh.creation.cylinder(radius=radius, height=length, sections=32)
    if axis == 0:
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))  # type: ignore[no-untyped-call]
    elif axis == 1:
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))  # type: ignore[no-untyped-call]
    cyl.apply_translation(center)
    return cast(trimesh.Trimesh, cyl)


type TextFactory = Callable[[str], trimesh.Trimesh]


def _axis_limits(cell: tuple[float, ...], options: SplitOptions) -> list[float]:
    """Comprimento máximo de pedaço em cada eixo, na orientação de mesa com mais folga."""
    bed = [b - options.margin_mm for b in options.bed_mm]
    best: tuple[float, list[float]] | None = None
    for perm in itertools.permutations(range(3)):
        limits = [bed[perm[a]] for a in range(3)]
        if all(cell[a] <= limits[a] + 1e-6 for a in range(3)):
            slack = sum(limits[a] - cell[a] for a in range(3))
            if best is None or slack > best[0]:
                best = (slack, limits)
    return best[1] if best else list(cell)


def _section_area(mesh: trimesh.Trimesh, axis: int, coord: float) -> float:
    section = _section_polygon(mesh, axis, coord)
    return float(section.area) if section is not None else 0.0


def _best_cuts(
    mesh: trimesh.Trimesh,
    axis: int,
    bounds: tuple[float, float],
    count: int,
    limit: float,
    options: SplitOptions,
    warnings: list[str],
) -> list[float]:
    """Posições de corte com a menor área de emenda total, respeitando o tamanho da mesa.

    Programação dinâmica sobre posições candidatas. Empate de área (peça uniforme) →
    prefere pedaços equilibrados.
    """
    lo, hi = bounds
    equal = [float(c) for c in np.linspace(lo, hi, count + 1)[1:-1]]
    if count <= 1 or not options.smart_cuts:
        return equal
    length = hi - lo
    ideal = length / count
    step = max(2.0, length / 300)
    candidates = [
        float(c)
        for c in np.arange(lo + options.min_segment_mm, hi - options.min_segment_mm + 1e-9, step)
    ]
    areas: dict[float, float] = {}

    def cost(c: float, segment: float) -> float:
        if c not in areas:
            areas[c] = _section_area(mesh, axis, c)
        return areas[c] + 1e-3 * (segment - ideal) ** 2

    def ok(segment: float) -> bool:
        return options.min_segment_mm <= segment <= limit + 1e-6

    def solve(cands: list[float]) -> list[float] | None:
        k, inf = count - 1, float("inf")
        best = [[inf] * len(cands) for _ in range(k)]
        back = [[-1] * len(cands) for _ in range(k)]
        for i, c in enumerate(cands):
            if ok(c - lo):
                best[0][i] = cost(c, c - lo)
        for j in range(1, k):
            for i, c in enumerate(cands):
                for i2 in range(i):
                    seg = c - cands[i2]
                    if best[j - 1][i2] < inf and ok(seg):
                        value = best[j - 1][i2] + cost(c, seg)
                        if value < best[j][i]:
                            best[j][i], back[j][i] = value, i2
        last = [
            (best[k - 1][i] + 1e-3 * (hi - c - ideal) ** 2, i)
            for i, c in enumerate(cands)
            if best[k - 1][i] < inf and ok(hi - c)
        ]
        if not last:
            return None
        _, i = min(last)
        chosen: list[float] = []
        for j in range(k - 1, -1, -1):
            chosen.append(cands[i])
            i = back[j][i]
        return sorted(chosen)

    protected_from = (
        hi - length * options.protect_top_pct / 100
        if axis == 2 and options.protect_top_pct > 0
        else None
    )
    if protected_from is not None:
        protected = solve([c for c in candidates if c <= protected_from])
        if protected is not None:
            return protected
        warnings.append(
            f"não deu para preservar os {options.protect_top_pct:.0f}% do topo sem cortar: "
            "a peça é alta demais para a mesa"
        )
    return solve(candidates) or equal


def _label_name(n: int) -> str:
    """A, B, ..., Z, AA, AB..."""
    name = ""
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def _plane_transform(axis: int, coord: float, pu: float, pv: float, *, mirror: bool) -> np.ndarray:
    """Local (x, y, z) → mundo: x→u (espelhado no lado de cima), y→v, z→normal do corte."""
    u, v = _PLANE_AXES[axis]
    m = np.eye(4)
    m[:3, :3] = 0.0
    m[u, 0] = -1.0 if mirror else 1.0
    m[v, 1] = 1.0
    m[axis, 2] = 1.0
    m[axis, 3], m[u, 3], m[v, 3] = coord, pu, pv
    return m


def _label_point(
    area: BaseGeometry, pins: list[tuple[float, float]], options: SplitOptions
) -> tuple[float, float] | None:
    safe = area.buffer(-(options.label_size_mm * 1.2))
    if safe.is_empty:
        return None
    minx, miny, maxx, maxy = safe.bounds
    step = max(options.label_size_mm, 3.0)
    rep = safe.representative_point()
    points = [
        (float(x), float(y))
        for x in np.arange(minx, maxx + 1e-9, step)
        for y in np.arange(miny, maxy + 1e-9, step)
        if safe.contains(Point(x, y))
    ] or [(float(rep.x), float(rep.y))]
    min_gap = options.pin_diameter_mm / 2 + options.label_size_mm
    far = [p for p in points if all(math.dist(p, q) >= min_gap for q in pins)]
    if not far:
        return None
    return max(far, key=lambda p: min((math.dist(p, q) for q in pins), default=0.0))


def split_mesh(
    mesh: trimesh.Trimesh, options: SplitOptions, text_factory: TextFactory | None = None
) -> SplitResult:
    if not mesh.is_watertight:
        raise SplitError("malha aberta: repare a peça antes de dividir")
    lo, hi = mesh.bounds
    plan = plan_split(tuple(float(e) for e in hi - lo), options)  # type: ignore[arg-type]
    limits = _axis_limits(plan.cell_mm, options)
    warnings: list[str] = []
    cuts = {
        a: _best_cuts(
            mesh, a, (float(lo[a]), float(hi[a])), plan.counts[a], limits[a], options, warnings
        )
        for a in range(3)
    }
    edges = [[float(lo[a]), *cuts[a], float(hi[a])] for a in range(3)]

    cutters: list[trimesh.Trimesh] = []
    pins: list[trimesh.Trimesh] = []
    labels: list[str] = []
    faces_without_pins = 0
    seam_area = 0.0
    hole_r = options.pin_diameter_mm / 2 + options.clearance_mm
    hole_len = options.pin_depth_mm * 2
    pin_len = options.pin_depth_mm * 2 - 1.0  # 0,5 mm de folga no fundo de cada furo
    if options.label_joints and text_factory is None:
        warnings.append("etiquetas de montagem indisponíveis aqui (sem OpenSCAD)")

    for axis in range(3):
        u, v = _PLANE_AXES[axis]
        for coord in cuts[axis]:  # só planos internos
            section = _section_polygon(mesh, axis, coord)
            if section is None:
                continue
            # cada face compartilhada entre duas células vizinhas recebe pinos e etiqueta
            for iu, iv in itertools.product(range(len(edges[u]) - 1), range(len(edges[v]) - 1)):
                face = box(edges[u][iu], edges[v][iv], edges[u][iu + 1], edges[v][iv + 1])
                material = section.intersection(face)
                if material.is_empty or material.area < 1.0:
                    continue
                seam_area += float(material.area)
                points = _pin_points(material, options)
                if not points:
                    faces_without_pins += 1
                for pu, pv in points:
                    center = np.zeros(3)
                    center[axis], center[u], center[v] = coord, pu, pv
                    cutters.append(_cylinder(axis, center, hole_r, hole_len))
                    pins.append(
                        trimesh.creation.cylinder(
                            radius=options.pin_diameter_mm / 2, height=pin_len, sections=32
                        )
                    )
                if not options.label_joints or text_factory is None:
                    continue
                spot = _label_point(material, points, options)
                if spot is None:
                    continue
                name = _label_name(len(labels))
                text = text_factory(name)
                depth = options.label_depth_mm
                lower = text.copy()  # gravada no pedaço de baixo, lida de fora (+normal)
                lower.apply_translation([0, 0, -depth])
                lower.apply_transform(_plane_transform(axis, coord + 0.01, *spot, mirror=False))
                upper = text.copy()  # no pedaço de cima, espelhada para ler do outro lado
                upper.apply_transform(_plane_transform(axis, coord - 0.01, *spot, mirror=True))
                cutters += [lower, upper]
                labels.append(name)

    drilled = (
        mesh.difference(cast(trimesh.Trimesh, trimesh.util.concatenate(cutters)), engine="manifold")
        if cutters
        else mesh
    )

    pieces: list[Piece] = []
    bed = options.bed_mm
    for idx in itertools.product(*(range(n) for n in plan.counts)):
        cell_lo = np.array([edges[a][idx[a]] for a in range(3)])
        cell_hi = np.array([edges[a][idx[a] + 1] for a in range(3)])
        cell = trimesh.creation.box(bounds=[cell_lo - 1e-3, cell_hi + 1e-3])
        part = drilled.intersection(cell, engine="manifold")
        if part.is_empty or part.volume <= 1e-6:
            continue  # célula vazia (ex.: peça em L)
        name = "peca_" + "_".join(str(i + 1) for i in idx)
        extents = tuple(float(e) for e in part.extents)
        pieces.append(
            Piece(
                name=name,
                index=cast(tuple[int, int, int], idx),
                mesh=part,
                fits=fits_build_volume(extents, bed, margin_mm=options.margin_mm / 2),  # type: ignore[arg-type]
            )
        )

    # pinos lado a lado, em pé, prontos para imprimir
    for i, pin in enumerate(pins):
        pin.apply_translation([i * (options.pin_diameter_mm + 3), 0, pin_len / 2])
    return SplitResult(
        plan=plan,
        pieces=pieces,
        pins=pins,
        faces_without_pins=faces_without_pins,
        cuts={a: [round(c, 1) for c in cuts[a]] for a in range(3)},
        seam_area_mm2=round(seam_area, 1),
        labels=labels,
        warnings=warnings,
    )
