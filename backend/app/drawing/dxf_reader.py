"""DXF -> Drawing using ezdxf (for users who export DXF from AutoCAD)."""

from collections import Counter
from importlib.metadata import version as pkg_version
from pathlib import Path

import ezdxf

from app.drawing.model import Drawing, Entity

TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB"}


def _xy(p) -> tuple[float, float]:
    return (float(p[0]), float(p[1]))


def _convert(e) -> tuple[str, dict] | None:
    t = e.dxftype()
    dx = e.dxf
    if t == "LINE":
        return t, {"start": _xy(dx.start), "end": _xy(dx.end)}
    if t == "ARC":
        return t, {
            "center": _xy(dx.center),
            "radius": float(dx.radius),
            "start_angle": float(dx.start_angle),
            "end_angle": float(dx.end_angle),
        }
    if t == "CIRCLE":
        return t, {"center": _xy(dx.center), "radius": float(dx.radius)}
    if t == "ELLIPSE":
        return t, {
            "center": _xy(dx.center),
            "major_axis": _xy(dx.major_axis),
            "axis_ratio": float(dx.ratio),
            "start_param": float(dx.start_param),
            "end_param": float(dx.end_param),
        }
    if t == "LWPOLYLINE":
        rows = list(e.get_points("xyb"))
        return t, {
            "points": [(r[0], r[1]) for r in rows],
            "bulges": [r[2] for r in rows],
            "closed": bool(e.closed),
        }
    if t == "POLYLINE" and e.is_2d_polyline:
        verts = list(e.vertices)
        return "LWPOLYLINE", {
            "points": [_xy(v.dxf.location) for v in verts],
            "bulges": [float(v.dxf.get("bulge", 0.0)) for v in verts],
            "closed": bool(e.is_closed),
        }
    if t == "SOLID":
        return t, {"points": [_xy(e[i]) for i in range(4)]}
    if t == "HATCH":
        paths = []
        for p in e.paths:
            if hasattr(p, "vertices"):
                paths.append([_xy(v) for v in p.vertices])
        return t, {"paths": [p for p in paths if len(p) > 1], "solid": bool(e.dxf.solid_fill)}
    if t in TEXT_TYPES:
        text = e.plain_text() if t == "MTEXT" else (dx.get("text") or "")
        height = dx.get("char_height") if t == "MTEXT" else dx.get("height")
        return t, {
            "text": text,
            "insert": _xy(dx.insert),
            "height": float(height or 0.2),
            "rotation": float(dx.get("rotation", 0.0) or 0.0),
            "tag": dx.get("tag") if t == "ATTRIB" else None,
        }
    if t == "DIMENSION":
        pts = [dx.get(k) for k in ("defpoint2", "defpoint3")]
        return t, {"points": [_xy(p) for p in pts if p is not None]}
    if t == "INSERT":
        return t, {
            "name": dx.name,
            "insert": _xy(dx.insert),
            "xscale": float(dx.get("xscale", 1.0)),
            "yscale": float(dx.get("yscale", 1.0)),
            "rotation": float(dx.get("rotation", 0.0)),
            "attribs": {a.dxf.tag: a.dxf.text for a in e.attribs},
        }
    return None


def _entity(e, skipped: Counter) -> Entity | None:
    converted = _convert(e)
    if converted is None:
        # still counted as an object, just not measured or drawn
        skipped[e.dxftype()] += 1
        converted = (e.dxftype(), {})
    etype, data = converted
    ent = Entity(type=etype, layer=e.dxf.get("layer", "0"), color=int(e.dxf.get("color", 256)), data=data)
    if etype == "INSERT":
        atts = [_entity(a, skipped) for a in e.attribs]
        data["attrib_entities"] = [a for a in atts if a]
    return ent


def read_dxf(path: Path) -> Drawing:
    doc = ezdxf.readfile(path)
    skipped: Counter[str] = Counter()
    modelspace = [x for x in (_entity(e, skipped) for e in doc.modelspace()) if x]
    blocks = {}
    for blk in doc.blocks:
        if blk.name.lower().startswith(("*model_space", "*paper_space")):
            continue
        blocks[blk.name] = [x for x in (_entity(e, skipped) for e in blk) if x]
    layers = {lay.dxf.name: abs(int(lay.dxf.get("color", 7))) for lay in doc.layers}
    return Drawing(
        source_format="dxf",
        version=doc.dxfversion,
        reader=f"ezdxf {pkg_version('ezdxf')}",
        modelspace=modelspace,
        blocks=blocks,
        layers=layers,
        insunits=doc.header.get("$INSUNITS"),
        notes=[f"{n} {t} objects counted but not measured or drawn" for t, n in skipped.most_common()],
    )
