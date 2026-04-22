"""OpenRouteService integration with a safe fallback mode."""

from __future__ import annotations

from typing import Any

import requests


class OpenRouteServiceClient:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key
        self.url = "https://api.openrouteservice.org/v2/directions/driving-car/json"

    def get_alternative_routes(self, origin: dict, destination: dict) -> list[dict[str, Any]] | None:
        """Return up to three route candidates, or None if the API is unavailable."""
        if not self.api_key:
            return None

        payload = {
            "coordinates": [
                [origin["lon"], origin["lat"]],
                [destination["lon"], destination["lat"]],
            ],
            "alternative_routes": {"target_count": 3, "weight_factor": 1.6},
        }
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            body = response.json()
            routes = body.get("routes", [])
        except requests.RequestException:
            return None

        normalized_routes: list[dict[str, Any]] = []
        for index, route in enumerate(routes, start=1):
            raw_geometry = route.get("geometry", [])
            if not isinstance(raw_geometry, list):
                return None
            geometry = [{"lat": lat, "lon": lon} for lon, lat in raw_geometry]
            summary = route.get("summary", {})
            normalized_routes.append(
                {
                    "route_id": f"ors-route-{index}",
                    "name": f"ORS Alternative {index}",
                    "distance_km": round(summary.get("distance", 0) / 1000, 2),
                    "travel_time_minutes": round(summary.get("duration", 0) / 60, 2),
                    "geometry": geometry,
                }
            )
        return normalized_routes or None
