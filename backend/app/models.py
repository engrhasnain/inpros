"""Core data model.

Project ─┬─ Drawing (a logical sheet, e.g. "3erNLUMI") ── DrawingVersion (each uploaded file / revision)
         └─ (next steps) CatalogItem, Estimacion, TakeoffItem
"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(300))
    contract_number: Mapped[str | None] = mapped_column(String(100))
    # Report data: entered once per project, used by every generated report (no copy-paste)
    contractor: Mapped[str | None] = mapped_column(String(200))
    scope: Mapped[str | None] = mapped_column(String(2000))
    supervisor_name: Mapped[str | None] = mapped_column(String(200))
    supervisor_title: Mapped[str | None] = mapped_column(String(200))
    approver_name: Mapped[str | None] = mapped_column(String(200))
    approver_title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=_now)

    drawings: Mapped[list["Drawing"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Drawing(Base):
    __tablename__ = "drawings"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200))  # file stem, identifies the sheet across revisions
    created_at: Mapped[datetime] = mapped_column(default=_now)

    project: Mapped[Project] = relationship(back_populates="drawings")
    versions: Mapped[list["DrawingVersion"]] = relationship(
        back_populates="drawing", cascade="all, delete-orphan", order_by="DrawingVersion.version"
    )


class DrawingVersion(Base):
    __tablename__ = "drawing_versions"
    __table_args__ = (UniqueConstraint("drawing_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    drawing_id: Mapped[int] = mapped_column(ForeignKey("drawings.id"))
    version: Mapped[int]
    original_filename: Mapped[str] = mapped_column(String(300))
    file_format: Mapped[str] = mapped_column(String(10))  # dwg | dxf
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int]
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[ProcessingStatus] = mapped_column(String(20), default=ProcessingStatus.pending)
    error: Mapped[str | None] = mapped_column(String(2000))
    reader: Mapped[str | None] = mapped_column(String(100))
    cad_version: Mapped[str | None] = mapped_column(String(20))
    # headline numbers, so lists don't need to open the analysis file
    object_count: Mapped[int | None]
    layer_count: Mapped[int | None]
    symbol_count: Mapped[int | None]
    label_count: Mapped[int | None]
    uploaded_at: Mapped[datetime] = mapped_column(default=_now)

    drawing: Mapped[Drawing] = relationship(back_populates="versions")


class CatalogItem(Base):
    """One line of the contract catalog (catálogo de conceptos)."""

    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("project_id", "clave"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    clave: Mapped[str] = mapped_column(String(50))
    descripcion: Mapped[str] = mapped_column(String(1000))
    unidad: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[float]  # contracted quantity
    precio_unitario: Mapped[float]
    partida: Mapped[str | None] = mapped_column(String(200))
    row: Mapped[int]  # order in the source file

    mapping: Mapped["ItemMapping | None"] = relationship(back_populates="catalog_item", cascade="all, delete-orphan")


class ItemMapping(Base):
    """Links a catalog item to the drawing quantity that measures it (which drawing, sheet and item)."""

    __tablename__ = "item_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"), unique=True)
    drawing_name: Mapped[str] = mapped_column(String(200))
    sheet: Mapped[str] = mapped_column(String(5))
    takeoff_key: Mapped[str] = mapped_column(String(300))
    confirmed: Mapped[bool] = mapped_column(default=False)
    score: Mapped[float] = mapped_column(default=0.0)

    catalog_item: Mapped[CatalogItem] = relationship(back_populates="mapping")


class EstimacionStatus(StrEnum):
    checked = "checked"
    approved = "approved"


class Estimacion(Base):
    """A contractor's progress billing for one period."""

    __tablename__ = "estimaciones"
    __table_args__ = (UniqueConstraint("project_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    numero: Mapped[int]
    periodo: Mapped[str | None] = mapped_column(String(100))
    source_filename: Mapped[str] = mapped_column(String(300))
    status: Mapped[EstimacionStatus] = mapped_column(String(20), default=EstimacionStatus.checked)
    uploaded_at: Mapped[datetime] = mapped_column(default=_now)
    approved_at: Mapped[datetime | None]

    lines: Mapped[list["EstimacionLine"]] = relationship(
        back_populates="estimacion", cascade="all, delete-orphan", order_by="EstimacionLine.row"
    )


class EstimacionLine(Base):
    __tablename__ = "estimacion_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimacion_id: Mapped[int] = mapped_column(ForeignKey("estimaciones.id"), index=True)
    row: Mapped[int]
    clave: Mapped[str] = mapped_column(String(50))
    descripcion: Mapped[str | None] = mapped_column(String(1000))
    unidad: Mapped[str | None] = mapped_column(String(20))
    cantidad: Mapped[float]  # claimed this period
    cantidad_anterior: Mapped[float | None]  # what the contractor says was paid before
    precio_unitario: Mapped[float | None]  # price the contractor used
    approved_quantity: Mapped[float | None]  # set when the estimación is approved

    estimacion: Mapped[Estimacion] = relationship(back_populates="lines")


class Bid(Base):
    """One bidder's unit prices for the project catalog (bid evaluation)."""

    __tablename__ = "bids"
    __table_args__ = (UniqueConstraint("project_id", "bidder"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    bidder: Mapped[str] = mapped_column(String(200))
    source_filename: Mapped[str] = mapped_column(String(300))
    uploaded_at: Mapped[datetime] = mapped_column(default=_now)

    lines: Mapped[list["BidLine"]] = relationship(back_populates="bid", cascade="all, delete-orphan")


class BidLine(Base):
    __tablename__ = "bid_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"), index=True)
    clave: Mapped[str] = mapped_column(String(50))
    precio_unitario: Mapped[float]

    bid: Mapped[Bid] = relationship(back_populates="lines")


class FieldEntry(Base):
    """Progress reported from site: quantity installed for a catalog item on a date."""

    __tablename__ = "field_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    fecha: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    clave: Mapped[str] = mapped_column(String(50))
    cantidad: Mapped[float]
    zona: Mapped[str | None] = mapped_column(String(200))
    nota: Mapped[str | None] = mapped_column(String(1000))
    reportado_por: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=_now)
