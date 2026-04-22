"""Simulated truck movement and orchestration of the control tower engines."""

from __future__ import annotations

import copy
from datetime import datetime

import numpy as np

from app.core.config import Settings
from app.models.schemas import AlertItem, DashboardState, TruckStatus
from app.services.decision import DecisionEngine
from app.services.prediction import HybridDelayPredictor, PredictionFeatures
from app.services.routing import RoutingEngine
from app.utils import clamp, haversine_km, move_along_path


class TruckSimulator:
    def __init__(self, settings: Settings, routing_engine: RoutingEngine, predictor: HybridDelayPredictor, decision_engine: DecisionEngine) -> None:
        self.settings = settings
        self.routing_engine = routing_engine
        self.predictor = predictor
        self.decision_engine = decision_engine
        self.rng = np.random.default_rng(7)
        self.tick = 0
        self.last_alert_signature: dict[str, str] = {}
        self.seed_trucks = self._build_seed_trucks()
        self.trucks = copy.deepcopy(self.seed_trucks)

    def reset(self) -> None:
        self.tick = 0
        self.last_alert_signature = {}
        self.trucks = copy.deepcopy(self.seed_trucks)

    def _build_seed_trucks(self) -> list[dict]:
        return [
            {
                "truck_id": "TRK-101",
                "driver_name": "Aisha Khan",
                "cargo_type": "Electronics",
                "origin_name": "Bengaluru Hub",
                "destination_name": "Chennai Port",
                "origin_position": {"lat": 12.9716, "lon": 77.5946},
                "destination_position": {"lat": 13.0827, "lon": 80.2707},
                "current_position": {"lat": 12.9716, "lon": 77.5946},
                "base_speed_kmph": 58,
                "status": "In Transit",
                "active_route_id": "balanced-corridor",
                "active_route_name": "Balanced Corridor",
            },
            {
                "truck_id": "TRK-204",
                "driver_name": "Rohan Mehta",
                "cargo_type": "Pharmaceuticals",
                "origin_name": "Hyderabad DC",
                "destination_name": "Pune Cross-Dock",
                "origin_position": {"lat": 17.3850, "lon": 78.4867},
                "destination_position": {"lat": 18.5204, "lon": 73.8567},
                "current_position": {"lat": 17.3850, "lon": 78.4867},
                "base_speed_kmph": 54,
                "status": "In Transit",
                "active_route_id": "balanced-corridor",
                "active_route_name": "Balanced Corridor",
            },
            {
                "truck_id": "TRK-309",
                "driver_name": "Neha Iyer",
                "cargo_type": "Retail Goods",
                "origin_name": "Mumbai Yard",
                "destination_name": "Ahmedabad Hub",
                "origin_position": {"lat": 19.0760, "lon": 72.8777},
                "destination_position": {"lat": 23.0225, "lon": 72.5714},
                "current_position": {"lat": 19.0760, "lon": 72.8777},
                "base_speed_kmph": 50,
                "status": "In Transit",
                "active_route_id": "balanced-corridor",
                "active_route_name": "Balanced Corridor",
            },
        ]

    def _traffic_factor(self, truck_index: int) -> float:
        wave = 0.45 + 0.25 * np.sin((self.tick + truck_index * 2) / 2)
        jitter = self.rng.uniform(-0.08, 0.10)
        return round(clamp(wave + jitter), 2)

    def _time_pressure(self) -> float:
        rush_window = 0.75 if 8 <= datetime.now().hour <= 11 or 17 <= datetime.now().hour <= 20 else 0.35
        return round(clamp(rush_window + self.rng.uniform(-0.05, 0.08)), 2)

    def _current_route(self, route_options: list, active_route_id: str):
        for route in route_options:
            if route.route_id == active_route_id:
                return route
        return route_options[0]

    def _append_alert_if_changed(self, truck_id: str, severity: str, message: str | None, alerts: list[AlertItem], now: datetime) -> None:
        if not message:
            self.last_alert_signature.pop(truck_id, None)
            return
        signature = f"{severity}:{message}"
        if self.last_alert_signature.get(truck_id) == signature:
            return
        self.last_alert_signature[truck_id] = signature
        alerts.append(
            AlertItem(
                truck_id=truck_id,
                severity=severity,
                message=message,
                created_at=now,
            )
        )

    def advance(self, auto_optimize: bool = True) -> DashboardState:
        self.tick += 1
        now = datetime.now()
        alerts: list[AlertItem] = []
        truck_states: list[TruckStatus] = []

        for index, truck in enumerate(self.trucks):
            if truck["status"] == "Delivered":
                completed_routes = self.routing_engine.generate_routes(
                    truck["current_position"],
                    truck["destination_position"],
                    traffic_multiplier=0.15,
                )
                chosen_route = completed_routes[0]
                prediction_bundle = self.predictor.predict(
                    PredictionFeatures(
                        distance_km=0.1,
                        traffic_factor=0.05,
                        avg_speed_kmph=10,
                        route_risk=0.05,
                        time_pressure=0.10,
                    )
                )
                truck_states.append(
                    TruckStatus(
                        truck_id=truck["truck_id"],
                        driver_name=truck["driver_name"],
                        cargo_type=truck["cargo_type"],
                        origin_name=truck["origin_name"],
                        destination_name=truck["destination_name"],
                        current_position=truck["current_position"],
                        destination_position=truck["destination_position"],
                        current_speed_kmph=0.0,
                        distance_remaining_km=0.0,
                        status="Delivered",
                        active_route_id=chosen_route.route_id,
                        active_route_name=chosen_route.name,
                        delay_prediction=prediction_bundle["selected"],
                        decision=self.decision_engine.decide(
                            chosen_route,
                            chosen_route,
                            prediction_bundle["selected"],
                            auto_optimize=auto_optimize,
                        ),
                        route_options=completed_routes,
                        last_updated=now,
                    )
                )
                continue

            traffic_factor = self._traffic_factor(index)
            routes = self.routing_engine.generate_routes(
                truck["current_position"],
                truck["destination_position"],
                traffic_multiplier=max(0.25, traffic_factor),
            )
            active_route = self._current_route(routes, truck["active_route_id"])
            best_route = routes[0]
            speed = max(22.0, truck["base_speed_kmph"] * (1.05 - traffic_factor * 0.35))
            time_pressure = self._time_pressure()

            prediction_bundle = self.predictor.predict(
                PredictionFeatures(
                    distance_km=active_route.distance_km,
                    traffic_factor=active_route.traffic_factor,
                    avg_speed_kmph=speed,
                    route_risk=active_route.risk_factor,
                    time_pressure=time_pressure,
                )
            )
            selected_prediction = prediction_bundle["selected"]
            decision = self.decision_engine.decide(
                active_route,
                best_route,
                selected_prediction,
                auto_optimize=auto_optimize,
            )

            route_for_motion = best_route if decision.should_reroute else active_route
            if decision.should_reroute:
                truck["active_route_id"] = route_for_motion.route_id
                truck["active_route_name"] = route_for_motion.name

            distance_step = speed * (self.settings.simulation_tick_minutes / 60)
            new_position = move_along_path(route_for_motion.geometry, distance_step)
            distance_remaining = haversine_km(new_position, truck["destination_position"])

            if distance_remaining <= 7:
                new_position = truck["destination_position"]
                distance_remaining = 0.0
                truck["status"] = "Delivered"
                decision = decision.model_copy(
                    update={
                        "action": "complete",
                        "should_reroute": False,
                        "reason": "Shipment delivered successfully.",
                        "alert_message": f"{truck['truck_id']} reached {truck['destination_name']}.",
                        "severity": "info",
                    }
                )

            truck["current_position"] = new_position

            self._append_alert_if_changed(
                truck_id=truck["truck_id"],
                severity=decision.severity,
                message=decision.alert_message,
                alerts=alerts,
                now=now,
            )

            truck_states.append(
                TruckStatus(
                    truck_id=truck["truck_id"],
                    driver_name=truck["driver_name"],
                    cargo_type=truck["cargo_type"],
                    origin_name=truck["origin_name"],
                    destination_name=truck["destination_name"],
                    current_position=new_position,
                    destination_position=truck["destination_position"],
                    current_speed_kmph=round(speed, 1),
                    distance_remaining_km=round(distance_remaining, 1),
                    status=truck["status"],
                    active_route_id=truck["active_route_id"],
                    active_route_name=truck["active_route_name"],
                    delay_prediction=selected_prediction,
                    decision=decision,
                    route_options=routes,
                    last_updated=now,
                )
            )

        return DashboardState(
            tick=self.tick,
            generated_at=now,
            trucks=truck_states,
            alerts=alerts,
        )
