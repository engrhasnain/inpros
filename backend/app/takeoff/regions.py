"""Find sheets (title-block frames), legend boxes and quantity zones in a drawing."""

import re
from dataclasses import dataclass

from app.drawing.model import Drawing, Entity, Point

LEGEND_TEXT = re.compile(r"SIMBOLOG|NOMENCLATURA|LEYENDA", re.I)
ZONE_LAYER = re.compile(r"CUANTIFICACION", re.I)


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def contains(self, p: Point) -> bool:
        return self.x0 <= p[0] <= self.x1 and self.y0 <= p[1] <= self.y1

    def contains_box(self, b: "Box") -> bool:
        return self.x0 <= b.x0 and self.y0 <= b.y0 and self.x1 >= b.x1 and self.y1 >= b.y1

    def as_list(self) -> list[float]:
        return [round(self.x0, 3), round(self.y0, 3), round(self.x1, 3), round(self.y1, 3)]


@dataclass
class Sheet:
    id: str  # "A", "B", ...
    box: Box


@dataclass
class Zone:
    name: str
    polygon: list[Point]


def _rect(e: Entity) -> Box | None:
    """Axis-aligned closed rectangle drawn as a polyline (how frames and legend boxes are drawn)."""
    if e.type != "LWPOLYLINE":
        return None
    pts = e.data.get("points") or []
    if len(pts) not in (4, 5):
        return None
    closed = e.data.get("closed") or (len(pts) == 5 and pts[0] == pts[-1])
    if not closed:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    box = Box(min(xs), min(ys), max(xs), max(ys))
    # every corner must sit on the box edge (rejects rotated shapes); hand-drawn frames are
    # rarely exact, so allow 0.1 % of the rectangle's size
    tol = 1e-3 * max(box.x1 - box.x0, box.y1 - box.y0, 1.0)
    for x, y in pts:
        if not (abs(x - box.x0) < tol or abs(x - box.x1) < tol) or not (abs(y - box.y0) < tol or abs(y - box.y1) < tol):
            return None
    return box if box.area > 0 else None


def point_of(e: Entity) -> Point | None:
    """A representative location used to decide which sheet / zone an object belongs to."""
    d = e.data
    if "insert" in d:
        return d["insert"]
    if e.type == "LINE":
        return ((d["start"][0] + d["end"][0]) / 2, (d["start"][1] + d["end"][1]) / 2)
    if "center" in d:
        return d["center"]
    pts = d.get("points")
    if pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return None


def _main_extent(drawing: Drawing) -> Box | None:
    """Extent of the bulk of the drawing, ignoring the outer 2 % of objects (stray far-off lines)."""
    pts = [p for p in (point_of(e) for e in drawing.modelspace) if p]
    if len(pts) < 10:
        return None
    xs, ys = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
    lo, hi = int(len(xs) * 0.02), int(len(xs) * 0.98) - 1
    return Box(xs[lo], ys[lo], xs[hi], ys[hi])


def find_sheets(drawing: Drawing) -> list[Sheet]:
    rects = [b for b in (_rect(e) for e in drawing.modelspace) if b]
    extent = _main_extent(drawing)
    if not rects or extent is None or extent.area <= 0:
        return []
    # A sheet frame (title-block border) covers a large part of the drawing. Dimension boxes,
    # table cells and room outlines are far smaller and must not be mistaken for sheets.
    rects = [r for r in rects if r.area >= 0.15 * extent.area]
    if not rects:
        return []
    biggest = max(r.area for r in rects)
    # nested inner borders are dropped
    candidates = sorted((r for r in rects if r.area >= 0.3 * biggest), key=lambda r: -r.area)
    frames: list[Box] = []
    for r in candidates:
        if not any(f.contains_box(r) for f in frames):
            frames.append(r)
    # order top-to-bottom, then left-to-right
    frames.sort(key=lambda b: (-round(b.y1, 0), b.x0))
    return [Sheet(id=chr(ord("A") + i), box=b) for i, b in enumerate(frames)]


def find_legend_boxes(drawing: Drawing) -> list[Box]:
    rects = [b for b in (_rect(e) for e in drawing.modelspace) if b]
    boxes = []
    for e in drawing.modelspace:
        if e.type in ("TEXT", "MTEXT") and LEGEND_TEXT.search(e.data.get("text", "")):
            p = e.data["insert"]
            inside = [r for r in rects if r.contains(p)]
            if inside:
                small = min(inside, key=lambda r: r.area)
                # ignore when the "box" is a whole sheet frame
                if small.area < 0.25 * max(r.area for r in rects):
                    boxes.append(small)
    return boxes


def _point_in_polygon(p: Point, poly: list[Point]) -> bool:
    x, y = p
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def find_zones(drawing: Drawing) -> list[Zone]:
    """Department / billing zones: polylines on a CUANTIFICACION layer that outline an area,
    named by the text inside. Thin brackets that only mark a department's width (as on the
    sample drawings) do not outline an area and are ignored rather than guessed at."""
    extent = _main_extent(drawing)
    min_area = 0.01 * extent.area if extent else 0.0

    def outlines_area(e: Entity) -> bool:
        pts = e.data.get("points", [])
        if len(pts) < 3:
            return False
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (max(xs) - min(xs)) * (max(ys) - min(ys)) >= min_area

    polys = [e for e in drawing.modelspace if ZONE_LAYER.search(e.layer) and e.type == "LWPOLYLINE" and outlines_area(e)]
    texts = [e for e in drawing.modelspace if ZONE_LAYER.search(e.layer) and e.type in ("TEXT", "MTEXT")]
    zones = []
    for i, poly in enumerate(polys):
        pts = poly.data["points"]
        names = [" ".join(t.data["text"].split()) for t in texts if _point_in_polygon(t.data["insert"], pts)]
        zones.append(Zone(name=names[0] if names else f"Zone {i + 1}", polygon=pts))
    return zones


def zone_of(p: Point, zones: list[Zone]) -> str | None:
    for z in zones:
        if _point_in_polygon(p, z.polygon):
            return z.name
    return None
