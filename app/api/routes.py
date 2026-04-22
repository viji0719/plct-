"""FastAPI routes for PLCT."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.schemas import ControlModeState, DashboardState


router = APIRouter(prefix="/api", tags=["PLCT"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "PLCT Backend"}


@router.get("/dashboard/state", response_model=DashboardState)
def get_dashboard_state(request: Request) -> DashboardState:
    return request.app.state.control_tower.get_state()


@router.post("/simulation/tick", response_model=DashboardState)
def simulation_tick(request: Request) -> DashboardState:
    return request.app.state.control_tower.tick()


@router.post("/simulation/reset", response_model=DashboardState)
def simulation_reset(request: Request) -> DashboardState:
    return request.app.state.control_tower.reset()


@router.get("/control-mode", response_model=ControlModeState)
def get_control_mode(request: Request) -> ControlModeState:
    return ControlModeState(auto_optimize=request.app.state.control_tower.get_control_mode())


@router.post("/control-mode", response_model=ControlModeState)
def update_control_mode(mode: ControlModeState, request: Request) -> ControlModeState:
    updated = request.app.state.control_tower.set_control_mode(mode.auto_optimize)
    return ControlModeState(auto_optimize=updated)


@router.get("/trucks/{truck_id}/telemetry")
def get_truck_telemetry(truck_id: str, request: Request, limit: int = 20) -> list[dict]:
    return request.app.state.control_tower.get_truck_telemetry(truck_id=truck_id, limit=limit)
