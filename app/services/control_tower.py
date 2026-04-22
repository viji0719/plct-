"""Top-level orchestration for the Predictive Logistics Control Tower."""

from __future__ import annotations

from app.core.config import Settings
from app.db.database import DatabaseManager
from app.models.schemas import DashboardState
from app.services.decision import DecisionEngine
from app.services.ors_client import OpenRouteServiceClient
from app.services.prediction import HybridDelayPredictor
from app.services.routing import RoutingEngine
from app.services.simulator import TruckSimulator


class PredictiveLogisticsControlTower:
    def __init__(self, settings: Settings, database: DatabaseManager) -> None:
        self.settings = settings
        self.database = database
        self.database.init_db()
        self.routing_engine = RoutingEngine(settings, OpenRouteServiceClient(settings.ors_api_key))
        self.predictor = HybridDelayPredictor()
        self.decision_engine = DecisionEngine(settings)
        self.simulator = TruckSimulator(settings, self.routing_engine, self.predictor, self.decision_engine)
        self.auto_optimize = True
        self.state = self.simulator.advance(auto_optimize=self.auto_optimize)
        self._persist_state(self.state)

    def _persist_state(self, state: DashboardState) -> None:
        for truck in state.trucks:
            self.database.save_telemetry(truck)
        for alert in state.alerts:
            self.database.save_alert(alert)

    def get_state(self) -> DashboardState:
        latest_alerts = self.database.fetch_recent_alerts(limit=20)
        return self.state.model_copy(update={"alerts": latest_alerts})

    def tick(self) -> DashboardState:
        self.state = self.simulator.advance(auto_optimize=self.auto_optimize)
        self._persist_state(self.state)
        latest_alerts = self.database.fetch_recent_alerts(limit=20)
        self.state = self.state.model_copy(update={"alerts": latest_alerts})
        return self.state

    def reset(self) -> DashboardState:
        self.database.clear_demo_data()
        self.simulator.reset()
        self.state = self.simulator.advance(auto_optimize=self.auto_optimize)
        self._persist_state(self.state)
        latest_alerts = self.database.fetch_recent_alerts(limit=20)
        self.state = self.state.model_copy(update={"alerts": latest_alerts})
        return self.state

    def get_control_mode(self) -> bool:
        return self.auto_optimize

    def set_control_mode(self, auto_optimize: bool) -> bool:
        self.auto_optimize = auto_optimize
        return self.auto_optimize

    def get_truck_telemetry(self, truck_id: str, limit: int = 20) -> list[dict]:
        return self.database.fetch_truck_telemetry(truck_id=truck_id, limit=limit)
