from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.cv_routes import router as cv_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.scheduler import DiscoveryScheduler


def _find_frontend_dir() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[2] / "frontend",
        Path(__file__).resolve().parents[1].parent / "frontend",
        Path.cwd() / "frontend",
        Path.cwd().parent / "frontend",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").exists():
            return candidate
    return None


_FRONTEND_DIR = _find_frontend_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    scheduler = DiscoveryScheduler(settings)
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    await scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ApplyPilot API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(cv_router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    if _FRONTEND_DIR is not None:
        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(_FRONTEND_DIR / "index.html")

        app.mount("/", StaticFiles(directory=_FRONTEND_DIR), name="frontend")
        return

    @app.get("/", include_in_schema=False)
    async def redirect_to_gui(request: Request):
        host = (request.headers.get("host") or "127.0.0.1").split(":")[0]
        return RedirectResponse(url=f"http://{host}:8765/", status_code=302)


app = create_app()
