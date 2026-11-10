"""Project-level views over drawings: latest takeoff per drawing, and drawing quantities by mapping."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Drawing, DrawingVersion, ProcessingStatus
from app.services.drawing_processing import load_takeoff


def latest_ready_versions(db: Session, project_id: int) -> list[DrawingVersion]:
    out = []
    for d in db.scalars(select(Drawing).where(Drawing.project_id == project_id).order_by(Drawing.name)):
        ready = [v for v in d.versions if v.status == ProcessingStatus.ready]
        if ready:
            out.append(ready[-1])
    return out


def project_takeoff(db: Session, project_id: int) -> list[dict]:
    """All takeoff items of the latest version of every drawing, each tagged with its drawing."""
    rows = []
    for v in latest_ready_versions(db, project_id):
        t = load_takeoff(Path(v.file_path))
        for item in t["items"]:
            rows.append({**item, "drawing_name": v.drawing.name, "version_id": v.id, "version": v.version})
    return rows


def item_index(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    return {(r["drawing_name"], r["sheet"], r["key"]): r for r in rows}
