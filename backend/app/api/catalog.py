from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CatalogItem, Estimacion, ItemMapping, Project
from app.services.excel_io import ExcelFormatError, read_catalog
from app.services.matching import suggest
from app.services.project_data import item_index, project_takeoff

router = APIRouter(tags=["catalog"])


def _project(db: Session, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _suggest_links(db: Session, project_id: int, only_unconfirmed: bool = True) -> int:
    items = project_takeoff(db, project_id)
    made = 0
    for c in db.scalars(select(CatalogItem).where(CatalogItem.project_id == project_id)):
        if c.mapping and (c.mapping.confirmed or not only_unconfirmed):
            continue
        best, sc = suggest(c.descripcion, c.unidad, items)
        if c.mapping and not c.mapping.confirmed:
            db.delete(c.mapping)
            db.flush()
        if best:
            db.add(ItemMapping(catalog_item_id=c.id, drawing_name=best["drawing_name"], sheet=best["sheet"],
                               takeoff_key=best["key"], confirmed=False, score=round(sc, 3)))
            made += 1
    db.commit()
    return made


def _catalog_view(db: Session, project_id: int) -> dict:
    items = project_takeoff(db, project_id)
    idx = item_index(items)
    rows = []
    for c in db.scalars(select(CatalogItem).where(CatalogItem.project_id == project_id).order_by(CatalogItem.row)):
        m = c.mapping
        linked = idx.get((m.drawing_name, m.sheet, m.takeoff_key)) if m else None
        dq = linked["quantity"] if linked else None
        diff = round(dq - c.cantidad, 2) if dq is not None else None
        if m is None:
            status = "not_linked"
        elif linked is None:
            status = "link_missing"
        elif abs(diff) < 0.005:
            status = "matches"
        elif diff > 0:
            status = "drawing_more"
        else:
            status = "drawing_less"
        rows.append({
            "id": c.id, "clave": c.clave, "descripcion": c.descripcion, "unidad": c.unidad,
            "cantidad": c.cantidad, "precio_unitario": c.precio_unitario,
            "importe": round(c.cantidad * c.precio_unitario, 2), "partida": c.partida,
            "link": None if m is None else {
                "drawing_name": m.drawing_name, "sheet": m.sheet, "takeoff_key": m.takeoff_key,
                "confirmed": m.confirmed, "score": m.score,
                "description": linked["description"] if linked else None,
                "layer": linked["layer"] if linked else None,
                "method": linked["method"] if linked else None,
            },
            "drawing_quantity": dq,
            "difference": diff,
            "difference_amount": round(diff * c.precio_unitario, 2) if diff is not None else None,
            "status": status,
        })
    return {
        "items": rows,
        "takeoff_items": items,
        "totals": {
            "items": len(rows),
            "contract_amount": round(sum(r["importe"] for r in rows), 2),
            "linked": sum(1 for r in rows if r["link"]),
            "confirmed": sum(1 for r in rows if r["link"] and r["link"]["confirmed"]),
            "mismatches": sum(1 for r in rows if r["status"] in ("drawing_more", "drawing_less")),
        },
    }


@router.get("/projects/{project_id}/catalog")
def get_catalog(project_id: int, db: Session = Depends(get_db)) -> dict:
    _project(db, project_id)
    return _catalog_view(db, project_id)


@router.post("/projects/{project_id}/catalog")
async def upload_catalog(project_id: int, file: UploadFile, db: Session = Depends(get_db)) -> dict:
    """Replace the project's contract catalog with an Excel file, then suggest drawing links."""
    _project(db, project_id)
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Upload the catalog as an Excel file (.xlsx)")
    if db.scalar(select(Estimacion.id).where(Estimacion.project_id == project_id).limit(1)):
        raise HTTPException(409, "This project already has estimaciones; replacing the catalog would change their checks.")
    try:
        rows = read_catalog(await file.read())
    except ExcelFormatError as exc:
        raise HTTPException(400, str(exc)) from exc
    dupes = sorted({r["clave"] for r in rows if sum(1 for x in rows if x["clave"] == r["clave"]) > 1})
    if dupes:
        raise HTTPException(400, f"Repeated item codes in the catalog: {', '.join(dupes[:10])}")

    old = [c.id for c in db.scalars(select(CatalogItem).where(CatalogItem.project_id == project_id))]
    if old:
        db.execute(delete(ItemMapping).where(ItemMapping.catalog_item_id.in_(old)))
        db.execute(delete(CatalogItem).where(CatalogItem.id.in_(old)))
    for r in rows:
        db.add(CatalogItem(project_id=project_id, **r))
    db.commit()
    _suggest_links(db, project_id)
    return _catalog_view(db, project_id)


@router.post("/projects/{project_id}/catalog/suggest")
def resuggest(project_id: int, db: Session = Depends(get_db)) -> dict:
    """Re-run link suggestions for items that are not confirmed yet (e.g. after uploading more drawings)."""
    _project(db, project_id)
    _suggest_links(db, project_id)
    return _catalog_view(db, project_id)


class LinkIn(BaseModel):
    drawing_name: str
    sheet: str
    takeoff_key: str
    confirmed: bool = True


@router.put("/catalog-items/{item_id}/link")
def set_link(item_id: int, body: LinkIn, db: Session = Depends(get_db)) -> dict:
    c = db.get(CatalogItem, item_id)
    if not c:
        raise HTTPException(404, "Catalog item not found")
    if (body.drawing_name, body.sheet, body.takeoff_key) not in item_index(project_takeoff(db, c.project_id)):
        raise HTTPException(400, "That drawing item does not exist in the latest drawings")
    if c.mapping:
        db.delete(c.mapping)
        db.flush()
    db.add(ItemMapping(catalog_item_id=c.id, drawing_name=body.drawing_name, sheet=body.sheet,
                       takeoff_key=body.takeoff_key, confirmed=body.confirmed, score=1.0))
    db.commit()
    return _catalog_view(db, c.project_id)


@router.post("/catalog-items/{item_id}/confirm")
def confirm_link(item_id: int, db: Session = Depends(get_db)) -> dict:
    c = db.get(CatalogItem, item_id)
    if not c or not c.mapping:
        raise HTTPException(404, "No suggested link to confirm")
    c.mapping.confirmed = True
    db.commit()
    return _catalog_view(db, c.project_id)


@router.delete("/catalog-items/{item_id}/link")
def remove_link(item_id: int, db: Session = Depends(get_db)) -> dict:
    c = db.get(CatalogItem, item_id)
    if not c:
        raise HTTPException(404, "Catalog item not found")
    if c.mapping:
        db.delete(c.mapping)
        db.commit()
    return _catalog_view(db, c.project_id)
