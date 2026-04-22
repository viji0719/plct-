"""Pydantic schemas shared by the API and the dashboard."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RouteOption(BaseModel):
    route_id: str
    name: str
    distance_km: float
    travel_time_minutes: float
    traffic_factor: float
    cost_factor: float
    risk_factor: float
    score: float
    geometry: list[dict]


class PredictionResult(BaseModel):
    delay_risk: float
    predicted_delay_minutes: float
    eta_minutes: float
    model_name: str
    risk_breakdown: dict[str, float] = Field(default_factory=dict)


class DecisionResult(BaseModel):
    action: str
    should_reroute: bool
    reason: str
    recommended_route_id: str | None = None
    recommended_route_name: str | None = None
    alert_message: str | None = None
    severity: str = "info"


class AlertItem(BaseModel):
    truck_id: str
    severity: str
    message: str
    created_at: datetime


class TruckStatus(BaseModel):
    truck_id: str
    driver_name: str
    cargo_type: str
    origin_name: str
    destination_name: str
    current_position: dict
    destination_position: dict
    current_speed_kmph: float
    distance_remaining_km: float
    status: str
    active_route_id: str
    active_route_name: str
    delay_prediction: PredictionResult
    decision: DecisionResult
    route_options: list[RouteOption] = Field(default_factory=list)
    last_updated: datetime


class DashboardState(BaseModel):
    tick: int
    generated_at: datetime
    trucks: list[TruckStatus]
    alerts: list[AlertItem]


class ControlModeState(BaseModel):
    auto_optimize: bool = True
