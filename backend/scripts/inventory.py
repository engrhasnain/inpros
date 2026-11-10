"""Drawing inventory: summarise what is inside each DXF so we know what can be taken off.

Usage:  uv run python scripts/inventory.py ../data/dxf ../data/inventory
"""

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
import ezdxf.path
from ezdxf.document import Drawing

LINEAR_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE"}
TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB"}


def entity_length(e) -> float:
    # Note: LWPOLYLINE has no .flattening(); an earlier version called it inside a
    # bare except and silently measured every polyline as 0 m. Use ezdxf.path.
    t = e.dxftype()
    if t == "LINE":
        return e.dxf.start.distance(e.dxf.end)
    if t == "ARC":
        span = (e.dxf.end_angle - e.dxf.start_angle) % 360 or 360
        return math.radians(span) * e.dxf.radius
    if t in {"LWPOLYLINE", "POLYLINE", "SPLINE"}:
        if t == "POLYLINE" and not e.is_2d_polyline:
            return 0.0
        pts = list(ezdxf.path.make_path(e).flattening(0.001))
        return sum(pts[i].distance(pts[i + 1]) for i in range(len(pts) - 1))
    return 0.0


def text_of(e) -> str:
    t = e.dxftype()
    if t == "MTEXT":
        return e.plain_text().strip()
    return (e.dxf.get("text") or "").strip()


def inventory(path: Path) -> dict:
    doc: Drawing = ezdxf.readfile(path)
    msp = doc.modelspace()

    types = Counter()
    layers = defaultdict(lambda: {"entities": Counter(), "length": 0.0, "blocks": Counter()})
    blocks = Counter()
    block_attribs: dict[str, Counter] = defaultdict(Counter)
    texts = Counter()

    for e in msp:
        t = e.dxftype()
        types[t] += 1
        lay = layers[e.dxf.get("layer", "0")]
        lay["entities"][t] += 1
        if t in LINEAR_TYPES:
            lay["length"] += entity_length(e)
        elif t == "INSERT":
            name = e.dxf.name
            blocks[name] += 1
            lay["blocks"][name] += 1
            for a in e.attribs:
                block_attribs[name][f"{a.dxf.tag}={a.dxf.text}"] += 1
        elif t in TEXT_TYPES:
            s = text_of(e)
            if s:
                texts[s] += 1

    # layouts (paper space) can hold title blocks / tables
    layouts = {}
    for lo in doc.layouts:
        if lo.name == "Model":
            continue
        layouts[lo.name] = len(lo)

    return {
        "file": path.name,
        "dxf_version": doc.dxfversion,
        "insunits": doc.header.get("$INSUNITS"),
        "extmin": list(doc.header.get("$EXTMIN", (0, 0, 0)))[:2],
        "extmax": list(doc.header.get("$EXTMAX", (0, 0, 0)))[:2],
        "modelspace_entities": sum(types.values()),
        "entity_types": dict(types.most_common()),
        "layouts": layouts,
        "layers": {
            name: {
                "entities": dict(v["entities"].most_common()),
                "length": round(v["length"], 2),
                "blocks": dict(v["blocks"].most_common()),
            }
            for name, v in sorted(layers.items(), key=lambda kv: -sum(kv[1]["entities"].values()))
        },
        "blocks": dict(blocks.most_common()),
        "block_attribs": {k: dict(v.most_common(30)) for k, v in block_attribs.items()},
        "texts": dict(texts.most_common()),
    }


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "../data/dxf")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "../data/inventory")
    out.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.dxf")):
        inv = inventory(f)
        (out / f"{f.stem}.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"{f.name:42} ents={inv['modelspace_entities']:6} layers={len(inv['layers']):3} "
            f"block_types={len(inv['blocks']):3} inserts={sum(inv['blocks'].values()):5} "
            f"texts={len(inv['texts']):5} units={inv['insunits']} layouts={inv['layouts']}"
        )


if __name__ == "__main__":
    main()
