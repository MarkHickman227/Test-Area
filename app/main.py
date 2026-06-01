import logging

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import auth, posts

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="LinkedIn Post Scheduler",
    description="Schedule and publish LinkedIn posts via OAuth 2.0",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(posts.router)


@app.on_event("startup")
async def startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logging.warning("Could not connect to database: %s", e)


@app.get("/")
async def root():
    return {
        "app": "LinkedIn Post Scheduler",
        "status": "running",
        "environment": settings.app_env,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
