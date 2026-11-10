"""Geometry helpers: lengths, curve flattening and block placement transforms."""

import math
from collections.abc import Iterator

from app.drawing.model import Entity, Point

# 2D affine matrix (a, b, c, d, e, f):  x' = a*x + c*y + e ;  y' = b*x + d*y + f
Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

ARC_STEP_DEG = 10.0


def mul(m: Matrix, n: Matrix) -> Matrix:
    """m ∘ n  (apply n first, then m)."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + c * b2,
        b * a2 + d * b2,
        a * c2 + c * d2,
        b * c2 + d * d2,
        a * e2 + c * f2 + e,
        b * e2 + d * f2 + f,
    )


def apply(m: Matrix, p: Point) -> Point:
    a, b, c, d, e, f = m
    return (a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f)


def insert_matrix(data: dict) -> Matrix:
    """Block placement: scale, then rotate, then move to the insertion point."""
    r = math.radians(data.get("rotation", 0.0))
    sx, sy = data.get("xscale", 1.0), data.get("yscale", 1.0)
    cos, sin = math.cos(r), math.sin(r)
    x, y = data["insert"]
    return (cos * sx, sin * sx, -sin * sy, cos * sy, x, y)


def matrix_rotation_deg(m: Matrix) -> float:
    return math.degrees(math.atan2(m[1], m[0]))


def matrix_scale_y(m: Matrix) -> float:
    return math.hypot(m[2], m[3])


def _arc_points(cx: float, cy: float, r: float, start: float, end: float) -> list[Point]:
    sweep = (end - start) % 360.0 or 360.0
    n = max(2, int(math.ceil(sweep / ARC_STEP_DEG)))
    return [
        (cx + r * math.cos(math.radians(start + sweep * i / n)), cy + r * math.sin(math.radians(start + sweep * i / n)))
        for i in range(n + 1)
    ]


def _bulge_points(p1: Point, p2: Point, bulge: float) -> list[Point]:
    """Points along a polyline segment with a bulge (arc), excluding p1."""
    if abs(bulge) < 1e-9:
        return [p2]
    theta = 4.0 * math.atan(bulge)  # included angle, signed
    chord = math.dist(p1, p2)
    if chord < 1e-12:
        return [p2]
    r = chord / (2.0 * math.sin(abs(theta) / 2.0))
    mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    ux, uy = (p2[0] - p1[0]) / chord, (p2[1] - p1[1]) / chord
    # signed offset of the centre from the chord midpoint along the left normal
    s = chord * (1.0 - bulge * bulge) / (4.0 * bulge)
    cx, cy = mx - uy * s, my + ux * s
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)
    n = max(2, int(math.ceil(math.degrees(abs(theta)) / ARC_STEP_DEG)))
    return [(cx + r * math.cos(a1 + theta * i / n), cy + r * math.sin(a1 + theta * i / n)) for i in range(1, n + 1)]


def polyline_points(data: dict) -> list[Point]:
    pts = data["points"]
    if len(pts) < 2:
        return list(pts)
    bulges = data.get("bulges") or [0.0] * len(pts)
    closed = data.get("closed")
    out = [pts[0]]
    count = len(pts) if closed else len(pts) - 1
    for i in range(count):
        p1, p2 = pts[i], pts[(i + 1) % len(pts)]
        out.extend(_bulge_points(p1, p2, bulges[i] if i < len(bulges) else 0.0))
    return out


def outline_points(ent: Entity) -> list[Point] | None:
    """Flattened outline in the entity's own coordinates (None for texts/inserts and
    for objects kept only for counting, whose geometry was not converted)."""
    d, t = ent.data, ent.type
    if not d:
        return None
    if t == "LINE":
        return [d["start"], d["end"]]
    if t == "ARC":
        return _arc_points(*d["center"], d["radius"], d["start_angle"], d["end_angle"])
    if t == "CIRCLE":
        return _arc_points(*d["center"], d["radius"], 0.0, 360.0)
    if t == "ELLIPSE":
        cx, cy = d["center"]
        mx, my = d["major_axis"]
        ratio = d["axis_ratio"]
        s, e = d["start_param"], d["end_param"]
        span = (e - s) % (2 * math.pi) or 2 * math.pi
        n = max(8, int(math.degrees(span) / ARC_STEP_DEG))
        pts = []
        for i in range(n + 1):
            t_ = s + span * i / n
            ct, st = math.cos(t_), math.sin(t_)
            pts.append((cx + mx * ct - my * ratio * st, cy + my * ct + mx * ratio * st))
        return pts
    if t == "LWPOLYLINE":
        return polyline_points(d)
    if t == "SOLID":
        p = d["points"]
        return [p[0], p[1], p[3], p[2], p[0]] if len(p) == 4 else p
    if t == "DIMENSION":
        return d.get("points")
    return None


def length(ent: Entity) -> float:
    """Exact length for lines/arcs/circles, flattened length for curved polylines."""
    d, t = ent.data, ent.type
    if not d:
        return 0.0
    if t == "LINE":
        return math.dist(d["start"], d["end"])
    if t == "ARC":
        sweep = (d["end_angle"] - d["start_angle"]) % 360.0 or 360.0
        return math.radians(sweep) * d["radius"]
    if t == "LWPOLYLINE":
        pts = d["points"]
        if len(pts) < 2:
            return 0.0
        bulges = d.get("bulges") or [0.0] * len(pts)
        count = len(pts) if d.get("closed") else len(pts) - 1
        total = 0.0
        for i in range(count):
            p1, p2 = pts[i], pts[(i + 1) % len(pts)]
            chord = math.dist(p1, p2)
            b = bulges[i] if i < len(bulges) else 0.0
            if abs(b) < 1e-9:
                total += chord
            else:
                theta = 4.0 * math.atan(abs(b))
                total += chord * theta / (2.0 * math.sin(theta / 2.0))
        return total
    return 0.0


def iter_expanded(
    entities: list[Entity],
    blocks: dict[str, list[Entity]],
    m: Matrix = IDENTITY,
    parent_color: int = 7,
    depth: int = 0,
    max_depth: int = 6,
) -> Iterator[tuple[Entity, Matrix, int]]:
    """Yield (entity, world matrix, effective color) with block contents placed in the drawing."""
    for ent in entities:
        color = parent_color if ent.color == 0 else ent.color
        if ent.type == "INSERT":
            im = mul(m, insert_matrix(ent.data))
            if depth < max_depth:
                yield from iter_expanded(blocks.get(ent.data["name"], []), blocks, im, color, depth + 1, max_depth)
            for att in ent.data.get("attrib_entities", []):
                # attribute positions are stored in drawing coordinates already
                yield att, m, color
            continue
        yield ent, m, color
