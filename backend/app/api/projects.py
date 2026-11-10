from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.report_data import report_readiness

router = APIRouter(prefix="/projects", tags=["projects"])


def _get(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    return _get(db, project_id)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = _get(db, project_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "name" and not (v or "").strip():
            raise HTTPException(400, "Project name cannot be empty")
        setattr(project, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return project


@router.get("/{project_id}/report-readiness")
def readiness(project_id: int, db: Session = Depends(get_db)) -> dict:
    """Which report fields are missing — reports refuse to generate until they are filled."""
    return report_readiness(_get(db, project_id))
