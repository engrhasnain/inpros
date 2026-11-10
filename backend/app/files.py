"""Stored files (uploaded drawings, analysis, takeoff, previews).

Files always live in settings.storage_dir. When settings.files_in_database is on (Vercel),
every write is also saved in the database and a missing local file is restored from it, so
any serverless instance can serve any project.

Database copies are zlib-compressed and split into small parts: remote SQLite (Turso)
limits the size of a single statement, and a drawing plus its preview can be several MB.
"""

import zlib
from pathlib import Path

from sqlalchemy import Integer, LargeBinary, String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import settings
from app.db import Base, SessionLocal

PART_BYTES = 256 * 1024


class StoredFilePart(Base):
    __tablename__ = "stored_file_parts"

    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    part: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


def _key(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(settings.storage_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _save(db: Session, key: str, data: bytes) -> None:
    packed = zlib.compress(data, 6)
    db.execute(delete(StoredFilePart).where(StoredFilePart.key == key))
    for i in range(0, max(len(packed), 1), PART_BYTES):
        db.add(StoredFilePart(key=key, part=i // PART_BYTES, data=packed[i:i + PART_BYTES]))
        db.flush()  # one small INSERT per part


def write(path: Path, data: bytes, db: Session | None = None) -> None:
    """Write a file. Pass the request's ``db`` session when inside a transaction, so the
    database copy is saved in that same transaction (and committed with it)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if not settings.files_in_database:
        return
    if db is not None:
        _save(db, _key(path), data)
        return
    with SessionLocal() as own:
        _save(own, _key(path), data)
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
        parts = db.scalars(
            select(StoredFilePart.data).where(StoredFilePart.key == _key(path)).order_by(StoredFilePart.part)
        ).all()
    if not parts:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zlib.decompress(b"".join(parts)))
    return True
