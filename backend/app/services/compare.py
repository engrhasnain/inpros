"""What changed between two versions of the same drawing, and what it costs."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogItem, DrawingVersion
from app.services.drawing_processing import load_analysis, load_takeoff


def compare_versions(db: Session, old: DrawingVersion, new: DrawingVersion) -> dict:
    t_old = {(i["sheet"], i["key"]): i for i in load_takeoff(Path(old.file_path))["items"]}
    t_new = {(i["sheet"], i["key"]): i for i in load_takeoff(Path(new.file_path))["items"]}

    # catalog prices for items that are linked to this drawing
    prices: dict[tuple[str, str], CatalogItem] = {}
    for c in db.scalars(select(CatalogItem).where(CatalogItem.project_id == old.drawing.project_id)):
        if c.mapping and c.mapping.drawing_name == old.drawing.name:
            prices[(c.mapping.sheet, c.mapping.takeoff_key)] = c

    changes = []
    for k in sorted(set(t_old) | set(t_new)):
        a, b = t_old.get(k), t_new.get(k)
        qa = a["quantity"] if a else 0.0
        qb = b["quantity"] if b else 0.0
        if abs(qb - qa) < 0.005:
            continue
        ref = b or a
        cat = prices.get(k)
        delta = round(qb - qa, 2)
        changes.append({
            "sheet": k[0],
            "key": k[1],
            "description": ref["description"],
            "layer": ref["layer"],
            "unit": ref["unit"],
            "old": qa,
            "new": qb,
            "delta": delta,
            "status": "added" if a is None else "removed" if b is None else "changed",
            "catalog_clave": cat.clave if cat else None,
            "unit_price": cat.precio_unitario if cat else None,
            "cost_impact": round(delta * cat.precio_unitario, 2) if cat else None,
        })
    changes.sort(key=lambda c: -abs(c["cost_impact"] or 0) - abs(c["delta"]) * 1e-6)

    a_old = load_analysis(Path(old.file_path))
    a_new = load_analysis(Path(new.file_path))
    lo, ln = {r["text"] for r in a_old["labels"]}, {r["text"] for r in a_new["labels"]}
    layers_o, layers_n = {r["name"] for r in a_old["layers"]}, {r["name"] for r in a_new["layers"]}

    return {
        "drawing_name": old.drawing.name,
        "old": {"id": old.id, "version": old.version, "filename": old.original_filename, "uploaded_at": old.uploaded_at.isoformat()},
        "new": {"id": new.id, "version": new.version, "filename": new.original_filename, "uploaded_at": new.uploaded_at.isoformat()},
        "quantity_changes": changes,
        "cost_impact_total": round(sum(c["cost_impact"] or 0 for c in changes), 2),
        "unpriced_changes": sum(1 for c in changes if c["cost_impact"] is None),
        "objects": {"old": a_old["totals"]["objects"], "new": a_new["totals"]["objects"]},
        "labels_added": sorted(ln - lo)[:200],
        "labels_removed": sorted(lo - ln)[:200],
        "layers_added": sorted(layers_n - layers_o),
        "layers_removed": sorted(layers_o - layers_n),
    }
