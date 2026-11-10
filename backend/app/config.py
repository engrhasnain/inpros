import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.environ.get("VERCEL"))
# Vercel functions can only write to /tmp, and /tmp is not shared between instances.
_DEFAULT_DATA_DIR = Path("/tmp/inpros") if ON_VERCEL else BACKEND_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # SQLite locally. On Vercel set DATABASE_URL to a Postgres database (Neon / Vercel Postgres);
    # "postgres://..." and "postgresql://..." are accepted as given by those providers.
    database_url: str = f"sqlite:///{(_DEFAULT_DATA_DIR / 'inpros.db').as_posix()}"

    # Working folder for uploaded drawings and their analysis / takeoff / preview files.
    storage_dir: Path = _DEFAULT_DATA_DIR / "storage"

    # Keep a copy of every stored file in the database, so any server instance can serve it.
    # On by default on Vercel; locally files simply live in storage_dir.
    files_in_database: bool = ON_VERCEL

    cors_origins: list[str] = ["http://localhost:3100", "http://localhost:3000"]

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v


settings = Settings()
