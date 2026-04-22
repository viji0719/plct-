"""FastAPI entry point for the PLCT backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.db.database import DatabaseManager
from app.services.control_tower import PredictiveLogisticsControlTower


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = DatabaseManager(settings.absolute_sqlite_path)
    app.state.control_tower = PredictiveLogisticsControlTower(settings, database)
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI-powered demo for predictive delay monitoring and dynamic route control.",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "message": "Welcome to the Predictive Logistics Control Tower backend.",
        "docs": "/docs",
    }
