from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bid, BidLine, CatalogItem, Estimacion, FieldEntry, Project
from app.services.bids import evaluate_bids
from app.services.estimacion_check import check_estimacion
from app.services.excel_io import ExcelFormatError, read_bid, read_field
from app.services.report_data import header, report_readiness
from app.services.reports_pdf import dictamen_estimacion, evaluacion_propuestas, reporte_avance

router = APIRouter(tags=["reports"])
PDF = "application/pdf"


def _project(db: Session, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _catalog(db: Session, project_id: int) -> list[CatalogItem]:
    items = list(db.scalars(select(CatalogItem).where(CatalogItem.project_id == project_id).order_by(CatalogItem.row)))
    if not items:
        raise HTTPException(409, "Upload the contract catalog first.")
    return items


def _require_ready(p: Project) -> None:
    r = report_readiness(p)
    if not r["ready"]:
        detail = "Complete the project details before generating reports: " + "; ".join(r["missing"] + r["problems"])
        raise HTTPException(409, detail)


def _pdf(data: bytes, filename: str) -> Response:
    return Response(data, media_type=PDF, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ------------------------------------------------------------------ reports
@router.get("/estimaciones/{est_id}/dictamen.pdf")
def estimacion_report(est_id: int, db: Session = Depends(get_db)) -> Response:
    e = db.get(Estimacion, est_id)
    if not e:
        raise HTTPException(404, "Estimación not found")
    p = _project(db, e.project_id)
    _require_ready(p)
    return _pdf(dictamen_estimacion(header(p), check_estimacion(db, e)), f"dictamen_estimacion_{e.numero:02d}.pdf")


# ------------------------------------------------------------------ bids
@router.post("/projects/{project_id}/bids", status_code=201)
async def upload_bid(project_id: int, file: UploadFile, bidder: str = Form(...), db: Session = Depends(get_db)) -> dict:
    _project(db, project_id)
    _catalog(db, project_id)
    bidder = bidder.strip()
    if not bidder:
        raise HTTPException(400, "Bidder name is required")
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Upload the bid as an Excel file (.xlsx)")
    try:
        rows = read_bid(await file.read())
    except ExcelFormatError as exc:
        raise HTTPException(400, str(exc)) from exc
    old = db.scalar(select(Bid).where(Bid.project_id == project_id, Bid.bidder == bidder))
    if old:
        db.delete(old)
        db.flush()
    seen = set()
    lines = []
    for r in rows:
        if r["clave"] in seen:
            continue  # first price per item counts
        seen.add(r["clave"])
        lines.append(BidLine(**r))
    db.add(Bid(project_id=project_id, bidder=bidder, source_filename=file.filename or "bid.xlsx", lines=lines))
    db.commit()
    return evaluate_bids(db, project_id)


@router.get("/projects/{project_id}/bids")
def get_bid_evaluation(project_id: int, db: Session = Depends(get_db)) -> dict:
    _project(db, project_id)
    return evaluate_bids(db, project_id)


@router.delete("/bids/{bid_id}")
def delete_bid(bid_id: int, db: Session = Depends(get_db)) -> dict:
    b = db.get(Bid, bid_id)
    if not b:
        raise HTTPException(404, "Bid not found")
    pid = b.project_id
    db.delete(b)
    db.commit()
    return evaluate_bids(db, pid)


@router.get("/projects/{project_id}/bids/report.pdf")
def bids_report(project_id: int, db: Session = Depends(get_db)) -> Response:
    p = _project(db, project_id)
    _require_ready(p)
    ev = evaluate_bids(db, project_id)
    if not ev["bidders"]:
        raise HTTPException(409, "Upload at least one bid first.")
    return _pdf(evaluacion_propuestas(header(p), ev), "evaluacion_propuestas.pdf")


# ------------------------------------------------------------------ field progress
class FieldIn(BaseModel):
    fecha: str
    clave: str
    cantidad: float
    zona: str | None = None
    nota: str | None = None
    reportado_por: str | None = None

    @field_validator("fecha")
    @classmethod
    def _iso(cls, v: str) -> str:
        date.fromisoformat(v)
        return v


def _field_view(db: Session, project_id: int) -> dict:
    entries = list(db.scalars(select(FieldEntry).where(FieldEntry.project_id == project_id)
                              .order_by(FieldEntry.fecha.desc(), FieldEntry.id.desc())))
    catalog = list(db.scalars(select(CatalogItem).where(CatalogItem.project_id == project_id).order_by(CatalogItem.row)))
    done: dict[str, float] = {}
    for e in entries:
        done[e.clave] = done.get(e.clave, 0.0) + e.cantidad
    progress = [{
        "clave": c.clave, "descripcion": c.descripcion, "unidad": c.unidad, "contract": c.cantidad,
        "installed": round(done.get(c.clave, 0.0), 4),
        "percent": round(done.get(c.clave, 0.0) / c.cantidad * 100, 1) if c.cantidad else None,
    } for c in catalog]
    known = {c.clave for c in catalog}
    return {
        "entries": [{"id": e.id, "fecha": e.fecha, "clave": e.clave, "cantidad": e.cantidad, "zona": e.zona,
                     "nota": e.nota, "reportado_por": e.reportado_por, "in_catalog": e.clave in known} for e in entries],
        "progress": progress,
    }


@router.get("/projects/{project_id}/field")
def get_field(project_id: int, db: Session = Depends(get_db)) -> dict:
    _project(db, project_id)
    return _field_view(db, project_id)


@router.post("/projects/{project_id}/field", status_code=201)
def add_field_entry(project_id: int, body: FieldIn, db: Session = Depends(get_db)) -> dict:
    _project(db, project_id)
    if body.cantidad <= 0:
        raise HTTPException(400, "Quantity must be greater than zero")
    db.add(FieldEntry(project_id=project_id, **body.model_dump()))
    db.commit()
    return _field_view(db, project_id)


@router.post("/projects/{project_id}/field/upload", status_code=201)
async def upload_field(project_id: int, file: UploadFile, db: Session = Depends(get_db)) -> dict:
    """Upload a site progress Excel (Fecha, Clave, Cantidad, Zona, Nota, Reportado por)."""
    _project(db, project_id)
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Upload the progress report as an Excel file (.xlsx)")
    try:
        rows = read_field(await file.read())
    except ExcelFormatError as exc:
        raise HTTPException(400, str(exc)) from exc
    for r in rows:
        db.add(FieldEntry(project_id=project_id, **r))
    db.commit()
    return _field_view(db, project_id)


@router.delete("/field-entries/{entry_id}")
def delete_field_entry(entry_id: int, db: Session = Depends(get_db)) -> dict:
    e = db.get(FieldEntry, entry_id)
    if not e:
        raise HTTPException(404, "Entry not found")
    pid = e.project_id
    db.delete(e)
    db.commit()
    return _field_view(db, pid)


@router.delete("/projects/{project_id}/field")
def clear_field(project_id: int, db: Session = Depends(get_db)) -> dict:
    _project(db, project_id)
    db.execute(delete(FieldEntry).where(FieldEntry.project_id == project_id))
    db.commit()
    return _field_view(db, project_id)


@router.get("/projects/{project_id}/field/report.pdf")
def field_report(project_id: int, db: Session = Depends(get_db)) -> Response:
    p = _project(db, project_id)
    _require_ready(p)
    catalog = _catalog(db, project_id)
    entries = list(db.scalars(select(FieldEntry).where(FieldEntry.project_id == project_id)))
    return _pdf(reporte_avance(header(p), catalog, entries), "reporte_avance.pdf")
