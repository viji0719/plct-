"""Route generation, scoring, and best-route selection."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas import RouteOption
from app.services.ors_client import OpenRouteServiceClient
from app.utils import midpoint, path_distance_km


class RoutingEngine:
    def __init__(self, settings: Settings, ors_client: OpenRouteServiceClient) -> None:
        self.settings = settings
        self.ors_client = ors_client

    def _score_route(self, travel_time_minutes: float, max_time: float, traffic: float, cost: float, risk: float) -> float:
        time_component = travel_time_minutes / max(max_time, 1)
        score = (
            self.settings.route_weight_time * time_component
            + self.settings.route_weight_traffic * traffic
            + self.settings.route_weight_cost * cost
            + self.settings.route_weight_risk * risk
        )
        return round(score, 3)

    def _fallback_routes(self, origin: dict, destination: dict) -> list[dict]:
        direct_mid = midpoint(origin, destination)
        safe_mid = midpoint(origin, destination, offset_lat=0.45, offset_lon=-0.30)
        fast_mid = midpoint(origin, destination, offset_lat=-0.22, offset_lon=0.24)
        return [
            {
                "route_id": "highway-express",
                "name": "Highway Express",
                "distance_km": 0.0,
                "travel_time_minutes": 0.0,
                "traffic_factor": 0.70,
                "cost_factor": 0.82,
                "risk_factor": 0.58,
                "geometry": [origin, fast_mid, destination],
            },
            {
                "route_id": "balanced-corridor",
                "name": "Balanced Corridor",
                "distance_km": 0.0,
                "travel_time_minutes": 0.0,
                "traffic_factor": 0.48,
                "cost_factor": 0.55,
                "risk_factor": 0.42,
                "geometry": [origin, direct_mid, destination],
            },
            {
                "route_id": "safe-bypass",
                "name": "Safe Bypass",
                "distance_km": 0.0,
                "travel_time_minutes": 0.0,
                "traffic_factor": 0.35,
                "cost_factor": 0.62,
                "risk_factor": 0.25,
                "geometry": [origin, safe_mid, destination],
            },
        ]

    def generate_routes(self, origin: dict, destination: dict, traffic_multiplier: float) -> list[RouteOption]:
        ors_routes = self.ors_client.get_alternative_routes(origin, destination)
        raw_routes = ors_routes or self._fallback_routes(origin, destination)

        for route in raw_routes:
            if route.get("distance_km", 0) == 0:
                route["distance_km"] = round(path_distance_km(route["geometry"]), 1)
            if route.get("travel_time_minutes", 0) == 0:
                avg_speed = 58 if "Express" in route["name"] else 46
                route["travel_time_minutes"] = round((route["distance_km"] / avg_speed) * 60, 1)
            if "traffic_factor" not in route:
                route["traffic_factor"] = min(1.0, 0.32 + 0.5 * traffic_multiplier)
            if "cost_factor" not in route:
                route["cost_factor"] = 0.40 + (route["distance_km"] / max(route["distance_km"] + 100, 1))
            if "risk_factor" not in route:
                route["risk_factor"] = 0.30 + (0.40 * traffic_multiplier)

        max_time = max(route["travel_time_minutes"] for route in raw_routes)
        route_options: list[RouteOption] = []
        for route in raw_routes:
            score = self._score_route(
                travel_time_minutes=route["travel_time_minutes"],
                max_time=max_time,
                traffic=min(1.0, route["traffic_factor"] * traffic_multiplier),
                cost=min(1.0, route["cost_factor"]),
                risk=min(1.0, route["risk_factor"]),
            )
            route_options.append(
                RouteOption(
                    route_id=route["route_id"],
                    name=route["name"],
                    distance_km=round(route["distance_km"], 1),
                    travel_time_minutes=round(route["travel_time_minutes"], 1),
                    traffic_factor=round(min(1.0, route["traffic_factor"] * traffic_multiplier), 2),
                    cost_factor=round(min(1.0, route["cost_factor"]), 2),
                    risk_factor=round(min(1.0, route["risk_factor"]), 2),
                    score=score,
                    geometry=route["geometry"],
                )
            )
        return sorted(route_options, key=lambda item: item.score)
