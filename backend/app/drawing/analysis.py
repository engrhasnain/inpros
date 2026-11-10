"""Summary of what is inside a drawing: layers, symbols (blocks) and text labels."""

from collections import Counter, defaultdict

from app.drawing.geometry import length
from app.drawing.model import Drawing

LINEAR_TYPES = {"LINE", "ARC", "LWPOLYLINE"}
TEXT_TYPES = {"TEXT", "MTEXT"}

# $INSUNITS codes -> label. Many older plans are "unitless" (0) but drawn in metres.
UNITS = {0: "unitless", 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}


def _clean(text: str) -> str:
    return " ".join(text.replace("%%c", "Ø").replace("%%C", "Ø").replace("%%d", "°").split())


def analyse(drawing: Drawing) -> dict:
    types: Counter[str] = Counter()
    layers: dict[str, dict] = defaultdict(lambda: {"objects": 0, "length": 0.0, "symbols": Counter(), "labels": 0})
    symbols: dict[str, dict] = defaultdict(lambda: {"count": 0, "layers": Counter(), "attribs": Counter()})
    labels: Counter[str] = Counter()
    label_layers: dict[str, Counter] = defaultdict(Counter)

    for e in drawing.modelspace:
        types[e.type] += 1
        lay = layers[e.layer]
        lay["objects"] += 1
        if e.type in LINEAR_TYPES:
            lay["length"] += length(e)
        elif e.type == "INSERT":
            name = e.data["name"]
            s = symbols[name]
            s["count"] += 1
            s["layers"][e.layer] += 1
            for tag, value in e.data.get("attribs", {}).items():
                if value:
                    s["attribs"][f"{tag}={value}"] += 1
            lay["symbols"][name] += 1
        elif e.type in TEXT_TYPES:
            t = _clean(e.data.get("text", ""))
            if t:
                labels[t] += 1
                label_layers[t][e.layer] += 1
                lay["labels"] += 1

    layer_rows = [
        {
            "name": name,
            "objects": v["objects"],
            "length": round(v["length"], 2),
            "labels": v["labels"],
            "symbols": [{"name": n, "count": c} for n, c in v["symbols"].most_common(5)],
            "symbol_count": sum(v["symbols"].values()),
        }
        for name, v in layers.items()
    ]
    layer_rows.sort(key=lambda r: -r["objects"])

    symbol_rows = [
        {
            "name": name,
            "count": v["count"],
            "anonymous": name.startswith("*") or name.startswith("A$C"),
            "layers": [{"name": n, "count": c} for n, c in v["layers"].most_common(3)],
            "attribs": [{"value": a, "count": c} for a, c in v["attribs"].most_common(5)],
        }
        for name, v in symbols.items()
    ]
    symbol_rows.sort(key=lambda r: -r["count"])

    label_rows = [
        {"text": t, "count": c, "layers": [n for n, _ in label_layers[t].most_common(2)]}
        for t, c in labels.most_common()
    ]

    return {
        "source_format": drawing.source_format,
        "dwg_version": drawing.version,
        "reader": drawing.reader,
        "units": UNITS.get(drawing.insunits or 0, f"code {drawing.insunits}"),
        "totals": {
            "objects": sum(types.values()),
            "layers": len(layer_rows),
            "symbols_placed": sum(r["count"] for r in symbol_rows),
            "symbol_types": len(symbol_rows),
            "labels": sum(labels.values()),
            "unique_labels": len(labels),
        },
        "object_types": dict(types.most_common()),
        "layers": layer_rows,
        "symbols": symbol_rows,
        "labels": label_rows,
        "notes": drawing.notes,
    }
