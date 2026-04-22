"""Environment-driven application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    app_name: str = "Predictive Logistics Control Tower"
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/plct.db")
    ors_api_key: str | None = os.getenv("ORS_API_KEY")
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    delay_threshold: float = float(os.getenv("DELAY_THRESHOLD", "0.65"))
    route_weight_time: float = float(os.getenv("ROUTE_WEIGHT_TIME", "0.40"))
    route_weight_traffic: float = float(os.getenv("ROUTE_WEIGHT_TRAFFIC", "0.25"))
    route_weight_cost: float = float(os.getenv("ROUTE_WEIGHT_COST", "0.15"))
    route_weight_risk: float = float(os.getenv("ROUTE_WEIGHT_RISK", "0.20"))
    simulation_tick_minutes: int = 5

    @property
    def absolute_sqlite_path(self) -> Path:
        return Path(self.sqlite_path).resolve()


def get_settings() -> Settings:
    return Settings()
