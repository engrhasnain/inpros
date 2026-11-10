from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    client: str | None = None
    location: str | None = None
    contract_number: str | None = None
    contractor: str | None = None
    scope: str | None = None
    supervisor_name: str | None = None
    supervisor_title: str | None = None
    approver_name: str | None = None
    approver_title: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    location: str | None = None
    contract_number: str | None = None
    contractor: str | None = None
    scope: str | None = None
    supervisor_name: str | None = None
    supervisor_title: str | None = None
    approver_name: str | None = None
    approver_title: str | None = None


class ProjectOut(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class DrawingVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version: int
    original_filename: str
    file_format: str
    sha256: str
    size_bytes: int
    status: str
    error: str | None
    reader: str | None
    cad_version: str | None
    object_count: int | None
    layer_count: int | None
    symbol_count: int | None
    label_count: int | None
    uploaded_at: datetime


class DrawingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    versions: list[DrawingVersionOut]


class DrawingVersionDetail(DrawingVersionOut):
    drawing_id: int
    drawing_name: str
    project_id: int
    total_versions: int


class UploadResult(BaseModel):
    drawing: str
    version: DrawingVersionOut
    duplicate: bool  # True when the exact same file was already uploaded
