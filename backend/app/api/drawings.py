import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import files
from app.config import settings
from app.db import get_db
from app.drawing.reader import DrawingReadError
from app.models import Drawing, DrawingVersion, ProcessingStatus, Project
from app.schemas import DrawingOut, DrawingVersionDetail, UploadResult
from app.services.compare import compare_versions
from app.services.drawing_processing import analysis_path, load_takeoff, preview_path, process_drawing
from app.services.project_data import latest_ready_versions, project_takeoff

router = APIRouter(tags=["drawings"])
logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED = {".dwg", ".dxf"}


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _version_or_404(db: Session, version_id: int) -> DrawingVersion:
    version = db.get(DrawingVersion, version_id)
    if not version:
        raise HTTPException(404, "Drawing version not found")
    return version


def _looks_valid(suffix: str, content: bytes) -> bool:
    if suffix == ".dwg":
        return content.startswith(b"AC10")
    head = content[:2048].lstrip()
    return head.startswith((b"0", b"999")) and b"SECTION" in head


@router.get("/projects/{project_id}/drawings", response_model=list[DrawingOut])
def list_drawings(project_id: int, db: Session = Depends(get_db)) -> list[Drawing]:
    _project_or_404(db, project_id)
    return list(db.scalars(select(Drawing).where(Drawing.project_id == project_id).order_by(Drawing.name)))


@router.post("/projects/{project_id}/drawings", response_model=UploadResult, status_code=201)
async def upload_drawing(project_id: int, file: UploadFile, db: Session = Depends(get_db)) -> UploadResult:
    _project_or_404(db, project_id)
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "Only .dwg and .dxf files are accepted")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large")
    if not _looks_valid(suffix, content):
        raise HTTPException(400, f"This does not look like a valid {suffix} file")
    sha = hashlib.sha256(content).hexdigest()
    name = Path(filename).stem

    drawing = db.scalar(select(Drawing).where(Drawing.project_id == project_id, Drawing.name == name))
    if drawing is None:
        drawing = Drawing(project_id=project_id, name=name)
        db.add(drawing)
        db.flush()
    else:
        # Same bytes already uploaded -> don't create a fake new revision.
        for v in drawing.versions:
            if v.sha256 == sha:
                return UploadResult(drawing=name, version=v, duplicate=True)

    next_version = (
        db.scalar(select(func.max(DrawingVersion.version)).where(DrawingVersion.drawing_id == drawing.id)) or 0
    ) + 1
    folder = settings.storage_dir / f"project_{project_id}" / f"drawing_{drawing.id}" / f"v{next_version}"
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"original{suffix}"
    files.write(stored, content, db)

    version = DrawingVersion(
        drawing_id=drawing.id,
        version=next_version,
        original_filename=filename,
        file_format=suffix.lstrip("."),
        sha256=sha,
        size_bytes=len(content),
        file_path=str(stored),
    )

    # Synchronous for the pilot (about 0.1-2 s per sheet); move to a worker for large batches.
    try:
        analysis = process_drawing(stored, db)
        totals = analysis["totals"]
        version.status = ProcessingStatus.ready
        version.reader = analysis["reader"]
        version.cad_version = analysis["dwg_version"]
        version.object_count = totals["objects"]
        version.layer_count = totals["layers"]
        version.symbol_count = totals["symbols_placed"]
        version.label_count = totals["labels"]
    except (DrawingReadError, OSError, ValueError) as exc:
        version.status = ProcessingStatus.failed
        version.error = str(exc)[:2000]
    except Exception as exc:  # never lose the upload over an unexpected drawing feature
        logger.exception("Processing failed for %s", filename)
        version.status = ProcessingStatus.failed
        version.error = f"Unexpected error while processing the drawing: {exc}"[:2000]

    db.add(version)
    db.commit()
    return UploadResult(drawing=name, version=version, duplicate=False)


@router.get("/drawing-versions/{version_id}", response_model=DrawingVersionDetail)
def get_version(version_id: int, db: Session = Depends(get_db)) -> DrawingVersionDetail:
    v = _version_or_404(db, version_id)
    base = DrawingVersionDetail.model_validate(
        {
            **{k: getattr(v, k) for k in DrawingVersionDetail.model_fields if hasattr(v, k)},
            "drawing_id": v.drawing.id,
            "drawing_name": v.drawing.name,
            "project_id": v.drawing.project_id,
            "total_versions": len(v.drawing.versions),
        }
    )
    return base


@router.get("/drawing-versions/{version_id}/analysis")
def get_analysis(version_id: int, db: Session = Depends(get_db)) -> FileResponse:
    v = _version_or_404(db, version_id)
    path = analysis_path(Path(v.file_path))
    if v.status != ProcessingStatus.ready or not files.ensure(path):
        raise HTTPException(409, "This drawing has no analysis (processing failed or pending)")
    return FileResponse(path, media_type="application/json")


@router.get("/drawing-versions/{version_id}/takeoff")
def get_takeoff(version_id: int, db: Session = Depends(get_db)) -> dict:
    v = _version_or_404(db, version_id)
    if v.status != ProcessingStatus.ready:
        raise HTTPException(409, "This drawing could not be read, so it has no quantities")
    return load_takeoff(Path(v.file_path))


@router.get("/projects/{project_id}/takeoff")
def get_project_takeoff(project_id: int, db: Session = Depends(get_db)) -> list[dict]:
    """Quantities from the latest version of every drawing in the project."""
    _project_or_404(db, project_id)
    return project_takeoff(db, project_id)


@router.delete("/drawings/{drawing_id}", status_code=204)
def delete_drawing(drawing_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a drawing with all its versions and files. Catalog links to it show 'Linked item gone'."""
    drawing = db.get(Drawing, drawing_id)
    if not drawing:
        raise HTTPException(404, "Drawing not found")
    files.delete_prefix(db, f"project_{drawing.project_id}/drawing_{drawing.id}/")
    db.delete(drawing)
    db.commit()


@router.get("/projects/{project_id}/takeoff-summary")
def get_takeoff_summary(project_id: int, db: Session = Depends(get_db)) -> list[dict]:
    """Per drawing (latest version): sheets, exclusions, zones and items."""
    _project_or_404(db, project_id)
    out = []
    for v in latest_ready_versions(db, project_id):
        t = load_takeoff(Path(v.file_path))
        out.append({"drawing_id": v.drawing.id, "drawing_name": v.drawing.name, "version_id": v.id,
                    "version": v.version, **t})
    return out


@router.get("/drawings/{drawing_id}/compare")
def compare(drawing_id: int, old: int, new: int, db: Session = Depends(get_db)) -> dict:
    """Compare two versions (by version number) of the same drawing."""
    drawing = db.get(Drawing, drawing_id)
    if not drawing:
        raise HTTPException(404, "Drawing not found")
    by_number = {v.version: v for v in drawing.versions}
    a, b = by_number.get(old), by_number.get(new)
    if not a or not b:
        raise HTTPException(404, "Version not found")
    if a.status != ProcessingStatus.ready or b.status != ProcessingStatus.ready:
        raise HTTPException(409, "Both versions must have been read successfully")
    return compare_versions(db, a, b)


@router.get("/drawing-versions/{version_id}/preview.svg")
def get_preview(version_id: int, db: Session = Depends(get_db)) -> FileResponse:
    v = _version_or_404(db, version_id)
    path = preview_path(Path(v.file_path))
    if v.status != ProcessingStatus.ready or not files.ensure(path):
        raise HTTPException(409, "This drawing has no preview (processing failed or pending)")
    return FileResponse(path, media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=3600"})
