from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CatalogItem, Estimacion, EstimacionLine, EstimacionStatus, Project
from app.services.estimacion_check import check_estimacion
from app.services.excel_io import ExcelFormatError, read_estimacion, write_validated_estimacion

router = APIRouter(tags=["estimaciones"])


def _est(db: Session, est_id: int) -> Estimacion:
    e = db.get(Estimacion, est_id)
    if not e:
        raise HTTPException(404, "Estimación not found")
    return e


@router.get("/projects/{project_id}/estimaciones")
def list_estimaciones(project_id: int, db: Session = Depends(get_db)) -> list[dict]:
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    out = []
    for e in db.scalars(select(Estimacion).where(Estimacion.project_id == project_id).order_by(Estimacion.numero)):
        r = check_estimacion(db, e)
        out.append({k: r[k] for k in ("id", "numero", "periodo", "source_filename", "status", "uploaded_at", "approved_at", "totals")})
    return out


@router.post("/projects/{project_id}/estimaciones", status_code=201)
async def upload_estimacion(
    project_id: int,
    file: UploadFile,
    numero: int = Form(...),
    periodo: str = Form(""),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    if not db.scalar(select(CatalogItem.id).where(CatalogItem.project_id == project_id).limit(1)):
        raise HTTPException(409, "Upload the contract catalog first — estimaciones are checked against it.")
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Upload the estimación as an Excel file (.xlsx)")
    if numero < 1:
        raise HTTPException(400, "Estimación number must be 1 or higher")
    existing = db.scalar(select(Estimacion).where(Estimacion.project_id == project_id, Estimacion.numero == numero))
    if existing and existing.status == EstimacionStatus.approved:
        raise HTTPException(409, f"Estimación {numero} is already approved and cannot be replaced.")
    later = db.scalar(select(Estimacion.id).where(
        Estimacion.project_id == project_id, Estimacion.numero > numero, Estimacion.status == EstimacionStatus.approved).limit(1))
    if later:
        raise HTTPException(409, "A later estimación is already approved; earlier periods cannot be changed.")
    try:
        rows = read_estimacion(await file.read())
    except ExcelFormatError as exc:
        raise HTTPException(400, str(exc)) from exc

    if existing:
        db.delete(existing)
        db.flush()
    est = Estimacion(project_id=project_id, numero=numero, periodo=periodo.strip() or None,
                     source_filename=file.filename or "estimacion.xlsx")
    est.lines = [EstimacionLine(**r) for r in rows]
    db.add(est)
    db.commit()
    return check_estimacion(db, est)


@router.get("/estimaciones/{est_id}")
def get_estimacion(est_id: int, db: Session = Depends(get_db)) -> dict:
    return check_estimacion(db, _est(db, est_id))


@router.post("/estimaciones/{est_id}/approve")
def approve(est_id: int, db: Session = Depends(get_db)) -> dict:
    """Approve with the quantities the check allows; they become 'previously paid' for later periods."""
    e = _est(db, est_id)
    if e.status == EstimacionStatus.approved:
        raise HTTPException(409, "Already approved")
    unapproved_earlier = db.scalar(select(Estimacion.numero).where(
        Estimacion.project_id == e.project_id, Estimacion.numero < e.numero,
        Estimacion.status != EstimacionStatus.approved).limit(1))
    if unapproved_earlier:
        raise HTTPException(409, f"Approve estimación {unapproved_earlier} first.")
    result = check_estimacion(db, e)
    by_id = {line["id"]: line for line in result["lines"]}
    for ln in e.lines:
        ln.approved_quantity = by_id[ln.id]["approvable"]
    e.status = EstimacionStatus.approved
    e.approved_at = datetime.now(timezone.utc)
    db.commit()
    return check_estimacion(db, e)


@router.delete("/estimaciones/{est_id}", status_code=204)
def delete_estimacion(est_id: int, db: Session = Depends(get_db)) -> None:
    e = _est(db, est_id)
    if e.status == EstimacionStatus.approved:
        raise HTTPException(409, "Approved estimaciones cannot be deleted")
    db.delete(e)
    db.commit()


@router.get("/estimaciones/{est_id}/export.xlsx")
def export(est_id: int, db: Session = Depends(get_db)) -> Response:
    e = _est(db, est_id)
    project = db.get(Project, e.project_id)
    data = write_validated_estimacion(project.name if project else "", check_estimacion(db, e))
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="estimacion_{e.numero:02d}_validada.xlsx"'},
    )
