import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.environ.get("VERCEL"))
# Vercel functions can only write to /tmp, and /tmp is not shared between instances.
_DEFAULT_DATA_DIR = Path("/tmp/inpros") if ON_VERCEL else BACKEND_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # SQLite everywhere.
    # - Locally: a SQLite file (default below).
    # - On Vercel: a remote SQLite database on Turso (libSQL), because Vercel keeps no files:
    #   set TURSO_DATABASE_URL=libsql://<db>-<org>.turso.io and TURSO_AUTH_TOKEN=<token>.
    database_url: str = f"sqlite:///{(_DEFAULT_DATA_DIR / 'inpros.db').as_posix()}"
    turso_database_url: str | None = None
    turso_auth_token: str | None = None

    # Working folder for uploaded drawings and their analysis / takeoff / preview files.
    storage_dir: Path = _DEFAULT_DATA_DIR / "storage"

    # Keep a copy of every stored file in the database, so any server instance can serve it.
    # On by default on Vercel; locally files simply live in storage_dir.
    files_in_database: bool = ON_VERCEL

    cors_origins: list[str] = ["http://localhost:3100", "http://localhost:3000"]

    @property
    def engine_url(self) -> str:
        """SQLAlchemy URL: Turso when configured, otherwise the local SQLite file."""
        url = self.turso_database_url or (self.database_url if self.database_url.startswith("libsql://") else None)
        if url:
            host = url.split("://", 1)[1].rstrip("/")
            return f"sqlite+libsql://{host}?secure=true"
        return self.database_url

    @property
    def engine_connect_args(self) -> dict:
        if self.engine_url.startswith("sqlite+libsql://"):
            return {"auth_token": self.turso_auth_token} if self.turso_auth_token else {}
        if self.engine_url.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}


settings = Settings()
