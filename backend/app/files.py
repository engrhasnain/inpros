"""Stored files (uploaded drawings, analysis, takeoff, previews).

Files always live in settings.storage_dir. When settings.files_in_database is on (Vercel),
every write is also saved in the database and a missing local file is restored from it, so
any serverless instance can serve any project.
"""

from pathlib import Path

from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import settings
from app.db import Base, SessionLocal


class StoredFile(Base):
    __tablename__ = "stored_files"

    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


def _key(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(settings.storage_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def write(path: Path, data: bytes, db: Session | None = None) -> None:
    """Write a file. Pass the request's ``db`` session when inside a transaction, so the
    database copy is saved in that same transaction (and committed with it)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if not settings.files_in_database:
        return
    if db is not None:
        db.merge(StoredFile(key=_key(path), data=data))
        return
    with SessionLocal() as own:
        own.merge(StoredFile(key=_key(path), data=data))
        own.commit()


def write_text(path: Path, text: str, db: Session | None = None) -> None:
    write(path, text.encode("utf-8"), db)


def ensure(path: Path) -> bool:
    """Make sure the file exists locally (restoring it from the database if needed)."""
    path = Path(path)
    if path.exists():
        return True
    if not settings.files_in_database:
        return False
    with SessionLocal() as db:
        row = db.get(StoredFile, _key(path))
        if row is None:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row.data)
    return True
