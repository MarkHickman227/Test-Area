import logging
from pathlib import Path

from fastapi import FastAPI, Request
from sqlalchemy import text
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import auth, posts

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.DEBUG if settings.debug else settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="LinkedIn Post Scheduler",
    description="Schedule and publish LinkedIn posts via OAuth 2.0",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(auth.router)
app.include_router(posts.router)


@app.on_event("startup")
async def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logging.warning("Could not connect to database: %s", e)


@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"linkedin_configured": settings.linkedin_configured},
    )


@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/health")
async def health():
    database_ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    return {
        "status": "healthy" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "linkedin_configured": settings.linkedin_configured,
    }
