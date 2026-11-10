"""Quantity takeoff engine.

Rules (deliberately simple and visible to the user):
- Only electrical layers are taken off (layer name patterns below); furniture, walls, dimensions,
  grid and text layers are ignored.
- Objects are assigned to a sheet by location; objects outside every sheet frame are excluded.
- Symbols inside the legend box are excluded (they are samples, not installed items).
- Exact duplicates (same symbol, same layer, same point / same line twice) are counted once.
- Symbols -> "count" items (pza). Lines/arcs/polylines -> "length" items (m) per layer.
  Tray layers are drawn as two parallel edges, so their run length is estimated as half of
  the long edges (marked as an estimate).
"""

import math
import re
from collections import Counter, defaultdict

from app.drawing.geometry import length
from app.drawing.model import Drawing, Entity
from app.takeoff.regions import find_legend_boxes, find_sheets, find_zones, point_of, zone_of

ELECTRICAL_LAYER = re.compile(
    r"^(IE|LUMIN|TUB|CHAR|CONT|ALIM|MOTOR|TABLER|TERMOST|DUCTO|CAJA|ELEC|SALIDA|BAJADA)", re.I
)
NOT_MEASURED_LAYER = re.compile(r"^(IETX|TEX)", re.I)  # text layers: never lengths
TRAY_LAYER = re.compile(r"CHAR|BANDEJA", re.I)
TRAY_MIN_EDGE = 0.6  # m; shorter segments are cross-ticks of the tray symbol
LINEAR = {"LINE", "ARC", "LWPOLYLINE"}

# Friendly names for symbols seen in these drawings; anything else shows its block name.
SYMBOL_NAMES = {
    "LAM-A": "Luminaire type A",
    "LAM-B": "Luminaire type B",
    "LAM-C": "Luminaire type C",
    "LAM-02": "Luminaire type 02",
    "CA": "Junction box (caja)",
    "AP": "Outlet / device AP",
    "RE": "Device RE",
    "TAB": "Electrical panel (tablero)",
    "TAB-E": "Electrical panel (tablero)",
    "MOTOR": "Motor",
}
LAYER_NAMES = {
    "TUBERIA": "Conduit run",
    "TUBERÍAS": "Conduit run",
    "TUBERIA ELEVADA": "Conduit run, elevated",
    "CONTN-R": "Outlet circuits, normal/regulated",
    "CHAROLA": "Cable tray run",
    "IETU1150": "Electrical conduit (IETU)",
    "MOTORES": "Motor feeders",
}


def is_electrical(layer: str) -> bool:
    return bool(ELECTRICAL_LAYER.match(layer.strip()))


def _line_key(e: Entity) -> tuple | None:
    d = e.data
    if e.type == "LINE":
        a = (round(d["start"][0], 3), round(d["start"][1], 3))
        b = (round(d["end"][0], 3), round(d["end"][1], 3))
        return ("L", e.layer, *sorted([a, b]))
    if e.type == "LWPOLYLINE":
        return ("P", e.layer, tuple((round(x, 3), round(y, 3)) for x, y in d["points"]))
    if e.type == "ARC":
        return ("A", e.layer, round(d["center"][0], 3), round(d["center"][1], 3), round(d["radius"], 3),
                round(d["start_angle"], 2), round(d["end_angle"], 2))
    return None


def _segments(e: Entity) -> list[float]:
    """Lengths of the individual straight pieces (used to drop tray cross-ticks)."""
    if e.type == "LWPOLYLINE":
        pts = e.data["points"]
        n = len(pts) if e.data.get("closed") else len(pts) - 1
        return [math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(max(n, 0))]
    return [length(e)]


def symbol_description(name: str) -> str:
    if name in SYMBOL_NAMES:
        return SYMBOL_NAMES[name]
    if name.startswith("A$C"):
        return f"Symbol {name} (unnamed copy)"
    return f"Symbol {name}"


def layer_description(layer: str) -> str:
    return LAYER_NAMES.get(layer.upper(), LAYER_NAMES.get(layer, f"Run length on layer {layer}"))


def compute_takeoff(drawing: Drawing) -> dict:
    sheets = find_sheets(drawing)
    legends = find_legend_boxes(drawing)
    zones = find_zones(drawing)

    def sheet_of(p) -> str | None:
        if not sheets:
            return "A"
        for s in sheets:
            if s.box.contains(p):
                return s.id
        return None

    excluded = Counter()  # reason -> objects
    seen_inserts: set = set()
    seen_lines: set = set()

    counts: dict[tuple, int] = Counter()  # (sheet, layer, block) -> n
    zone_counts: dict[tuple, Counter] = defaultdict(Counter)
    lengths: dict[tuple, float] = defaultdict(float)  # (sheet, layer) -> m
    tray_layers: set[str] = set()

    for e in drawing.modelspace:
        if not is_electrical(e.layer):
            continue
        p = point_of(e)
        if p is None:
            continue
        sheet = sheet_of(p)
        if sheet is None:
            excluded["outside every sheet"] += 1
            continue
        if any(b.contains(p) for b in legends):
            excluded["inside the legend box"] += 1
            continue

        if e.type == "INSERT":
            key = (e.data["name"], e.layer, round(p[0], 2), round(p[1], 2))
            if key in seen_inserts:
                excluded["exact duplicate"] += 1
                continue
            seen_inserts.add(key)
            ck = (sheet, e.layer, e.data["name"])
            counts[ck] += 1
            z = zone_of(p, zones) if zones else None
            if z:
                zone_counts[ck][z] += 1
        elif e.type in LINEAR and not NOT_MEASURED_LAYER.match(e.layer):
            lk = _line_key(e)
            if lk in seen_lines:
                excluded["exact duplicate"] += 1
                continue
            seen_lines.add(lk)
            if TRAY_LAYER.search(e.layer):
                tray_layers.add(e.layer)
                lengths[(sheet, e.layer)] += sum(s for s in _segments(e) if s >= TRAY_MIN_EDGE) / 2.0
            else:
                lengths[(sheet, e.layer)] += length(e)

    items = []
    for (sheet, layer, block), n in counts.items():
        items.append({
            "key": f"count|{layer}|{block}",
            "sheet": sheet,
            "kind": "count",
            "description": symbol_description(block),
            "symbol": block,
            "layer": layer,
            "unit": "pza",
            "quantity": n,
            "method": "symbols counted",
            "zones": dict(zone_counts[(sheet, layer, block)].most_common()),
        })
    for (sheet, layer), total in lengths.items():
        if total < 0.01:
            continue
        tray = layer in tray_layers
        items.append({
            "key": f"length|{layer}",
            "sheet": sheet,
            "kind": "length",
            "description": layer_description(layer),
            "symbol": None,
            "layer": layer,
            "unit": "m",
            "quantity": round(total, 2),
            "method": "estimated: half of the tray's two edges" if tray else "lines measured",
            "zones": {},
        })
    items.sort(key=lambda i: (i["sheet"], i["kind"], -i["quantity"]))

    return {
        "sheets": [{"id": s.id, "box": s.box.as_list()} for s in sheets] or [{"id": "A", "box": None}],
        "zones": [z.name for z in zones],
        "legend_boxes": len(legends),
        "excluded": dict(excluded),
        "rules": {
            "layers": "electrical layers only (names starting IE, LUMIN, TUB, CHAR, CONT, ALIM, MOTOR, TABLER, …)",
            "tray": f"trays: half of edges longer than {TRAY_MIN_EDGE} m",
        },
        "items": items,
    }
