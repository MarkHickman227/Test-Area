import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import auth, posts

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
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
    return templates.TemplateResponse(request, "login.html")


@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/health")
async def health():
    return {"status": "healthy"}
