"""DWG -> Drawing using ezdwg (MIT licensed, pure Python + Rust, no external program)."""

from collections import Counter, defaultdict
from importlib.metadata import version as pkg_version
from pathlib import Path

import ezdwg
from ezdwg import raw

from app.drawing.model import Drawing, Entity

MODEL_SPACE = 2  # ezdwg entity_placement mode
TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB"}


def _xy(p) -> tuple[float, float]:
    return (float(p[0]), float(p[1]))


def _color(d: dict) -> int:
    c = d.get("resolved_color_index")
    if c is None:
        c = d.get("color_index", 256)
    return int(c)


def _convert(t: str, d: dict) -> tuple[str, dict] | None:
    """Map an ezdwg entity to (type, data). Returns None for types we do not use."""
    if t == "LINE":
        return t, {"start": _xy(d["start"]), "end": _xy(d["end"])}
    if t == "ARC":
        return t, {
            "center": _xy(d["center"]),
            "radius": float(d["radius"]),
            "start_angle": float(d["start_angle"]),
            "end_angle": float(d["end_angle"]),
        }
    if t == "CIRCLE":
        return t, {"center": _xy(d["center"]), "radius": float(d["radius"])}
    if t == "ELLIPSE":
        return t, {
            "center": _xy(d["center"]),
            "major_axis": _xy(d["major_axis"]),
            "axis_ratio": float(d["axis_ratio"]),
            "start_param": float(d.get("start_angle", 0.0)),
            "end_param": float(d.get("end_angle", 6.283185307179586)),
        }
    if t in ("LWPOLYLINE", "POLYLINE_2D"):
        pts = [_xy(p) for p in d.get("points") or []]
        bulges = list(d.get("bulges") or [0.0] * len(pts))
        return "LWPOLYLINE", {"points": pts, "bulges": bulges, "closed": bool(d.get("closed"))}
    if t == "SOLID":
        return t, {"points": [_xy(p) for p in d.get("points") or []]}
    if t == "HATCH":
        paths = [[_xy(p) for p in path.get("points") or []] for path in d.get("paths") or []]
        return t, {"paths": [p for p in paths if len(p) > 1], "solid": bool(d.get("solid_fill"))}
    if t in TEXT_TYPES:
        text = d.get("text") or ""
        height = d.get("height") if t != "MTEXT" else d.get("char_height")
        return t, {
            "text": text,
            "insert": _xy(d.get("insert") or (0, 0)),
            "height": float(height or 0.2),
            "rotation": float(d.get("rotation") or 0.0),
            "tag": d.get("tag"),
        }
    if t == "INSERT":
        return t, {
            "name": d.get("name") or "",
            "insert": _xy(d["insert"]),
            "xscale": float(d.get("xscale") or 1.0),
            "yscale": float(d.get("yscale") or 1.0),
            "rotation": float(d.get("rotation") or 0.0),
            "attribs": {},
        }
    if t == "DIMENSION":
        return t, {"points": [_xy(p) for p in (d.get("defpoint2"), d.get("defpoint3")) if p]}
    return None


def read_dwg(path: Path) -> Drawing:
    path_s = str(path)
    doc = ezdwg.read(path_s)

    layer_table = doc.layers()
    layer_by_handle = {int(v["handle"]): name for name, v in layer_table.items()}
    layers = {name: int(v.get("color_index") or 7) for name, v in layer_table.items()}
    block_names = dict(raw.decode_block_header_names(path_s))

    modelspace: list[Entity] = []
    blocks: dict[str, list[Entity]] = defaultdict(list)
    attribs: list[tuple[int, Entity]] = []  # (owner insert handle, attrib)
    skipped: Counter[str] = Counter()

    for e in doc.entities().iter_entities():
        t = e.dxftype
        d = e.dxf
        converted = _convert(t, d)
        if converted is None:
            # still counted as an object, just not measured or drawn
            skipped[t] += 1
            converted = (t, {})
        etype, data = converted
        ent = Entity(
            type=etype,
            layer=layer_by_handle.get(d.get("layer_handle"), "0"),
            color=_color(d),
            data=data,
            handle=int(e.handle or 0),
        )
        placement = doc.entity_placement(e.handle) if e.handle else None
        mode, owner = placement if placement else (None, d.get("owner_handle"))

        if etype == "ATTRIB":
            attribs.append((int(owner or d.get("owner_handle") or 0), ent))
        elif mode == MODEL_SPACE:
            modelspace.append(ent)
        elif mode == 0 and owner in block_names:
            blocks[block_names[owner]].append(ent)
        # paper-space entities are not used for takeoff

    # Attach attribute values to their INSERT (e.g. SECRETARIA: A=BEATRIZ).
    inserts = {e.handle: e for e in modelspace if e.type == "INSERT"}
    for owner, att in attribs:
        ins = inserts.get(owner)
        if ins is None:
            continue
        tag = att.data.get("tag")
        if tag:
            ins.data["attribs"][tag] = att.data["text"]
        ins.data.setdefault("attrib_entities", []).append(att)

    notes = [f"{n} {t} objects counted but not measured or drawn" for t, n in skipped.most_common()]
    try:
        insunits = int(doc.insunits) if doc.insunits is not None else None
    except (TypeError, ValueError):
        insunits = None
    return Drawing(
        source_format="dwg",
        version=str(doc.version),
        reader=f"ezdwg {pkg_version('ezdwg')}",
        modelspace=modelspace,
        blocks=dict(blocks),
        layers=layers,
        insunits=insunits,
        notes=notes,
    )
