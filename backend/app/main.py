from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import files, models  # noqa: F401  (registers tables)
from app.api import catalog, drawings, estimaciones, projects, reports
from app.config import ON_VERCEL, settings
from app.db import engine
from app.migrate import migrate


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    migrate(engine)  # additive only; replace with Alembic migrations before production
    yield


class StripApiPrefix:
    """On Vercel the backend service receives the public path (/api/projects ...).
    Locally the frontend calls the backend directly (/projects ...). Accept both."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope, path=path[4:] or "/", raw_path=(path[4:] or "/").encode())
        await self.app(scope, receive, send)


app = FastAPI(title="INPROS Estimations API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(drawings.router)
app.include_router(catalog.router)
app.include_router(estimaciones.router)
app.include_router(reports.router)


@app.get("/health")
def health() -> dict:
    turso = settings.engine_url.startswith("sqlite+libsql://")
    return {
        "status": "ok",
        "dwg_reader": f"ezdwg {pkg_version('ezdwg')}",
        "dxf_reader": f"ezdxf {pkg_version('ezdxf')}",
        "database": "sqlite (turso)" if turso else "sqlite (local file)",
        "files_in_database": settings.files_in_database,
        "warning": ("Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN: a local SQLite file in /tmp is wiped "
                    "between Vercel instances." if ON_VERCEL and not turso else None),
    }


# outermost middleware: rewrites the path before routing
app.add_middleware(StripApiPrefix)
