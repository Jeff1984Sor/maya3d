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


def split_mesh(mesh: trimesh.Trimesh, options: SplitOptions) -> SplitResult:
    if not mesh.is_watertight:
        raise SplitError("malha aberta: repare a peça antes de dividir")
    lo, hi = mesh.bounds
    plan = plan_split(tuple(float(e) for e in hi - lo), options)  # type: ignore[arg-type]
    edges = [np.linspace(lo[a], hi[a], plan.counts[a] + 1) for a in range(3)]

    holes: list[trimesh.Trimesh] = []
    pins: list[trimesh.Trimesh] = []
    faces_without_pins = 0
    hole_r = options.pin_diameter_mm / 2 + options.clearance_mm
    hole_len = options.pin_depth_mm * 2
    pin_len = options.pin_depth_mm * 2 - 1.0  # 0,5 mm de folga no fundo de cada furo

    for axis in range(3):
        u, v = _PLANE_AXES[axis]
        for coord in edges[axis][1:-1]:  # só planos internos
            section = _section_polygon(mesh, axis, float(coord))
            if section is None:
                continue
            # cada face compartilhada entre duas células vizinhas recebe seus próprios pinos
            for iu, iv in itertools.product(range(plan.counts[u]), range(plan.counts[v])):
                face = box(edges[u][iu], edges[v][iv], edges[u][iu + 1], edges[v][iv + 1])
                material = section.intersection(face)
                if material.is_empty or material.area < 1.0:
                    continue
                points = _pin_points(material, options)
                if not points:
                    faces_without_pins += 1
                    continue
                for pu, pv in points:
                    center = np.zeros(3)
                    center[axis], center[u], center[v] = coord, pu, pv
                    holes.append(_cylinder(axis, center, hole_r, hole_len))
                    pins.append(
                        trimesh.creation.cylinder(
                            radius=options.pin_diameter_mm / 2, height=pin_len, sections=32
                        )
                    )

    drilled = (
        mesh.difference(cast(trimesh.Trimesh, trimesh.util.concatenate(holes)), engine="manifold")
        if holes
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
    return SplitResult(plan=plan, pieces=pieces, pins=pins, faces_without_pins=faces_without_pins)
