"""Small utility helpers used across the app."""

from __future__ import annotations

import math
from typing import Iterable


def haversine_km(point_a: dict, point_b: dict) -> float:
    """Return the distance in kilometers between two lat/lon points."""
    lat1, lon1 = math.radians(point_a["lat"]), math.radians(point_a["lon"])
    lat2, lon2 = math.radians(point_b["lat"]), math.radians(point_b["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Keep a numeric value inside the expected range."""
    return max(low, min(high, value))


def midpoint(origin: dict, destination: dict, offset_lat: float = 0.0, offset_lon: float = 0.0) -> dict:
    """Create a midpoint used to fake alternate routes when no API is configured."""
    return {
        "lat": (origin["lat"] + destination["lat"]) / 2 + offset_lat,
        "lon": (origin["lon"] + destination["lon"]) / 2 + offset_lon,
    }


def path_distance_km(geometry: Iterable[dict]) -> float:
    """Approximate the length of a route geometry."""
    points = list(geometry)
    total = 0.0
    for start, end in zip(points, points[1:]):
        total += haversine_km(start, end)
    return total


def move_along_path(geometry: list[dict], distance_km: float) -> dict:
    """Move along the path by a specific distance and return the new point."""
    if not geometry:
        return {"lat": 0.0, "lon": 0.0}
    if len(geometry) == 1 or distance_km <= 0:
        return geometry[0]

    remaining = distance_km
    for start, end in zip(geometry, geometry[1:]):
        segment = haversine_km(start, end)
        if segment == 0:
            continue
        if remaining <= segment:
            ratio = remaining / segment
            return {
                "lat": start["lat"] + (end["lat"] - start["lat"]) * ratio,
                "lon": start["lon"] + (end["lon"] - start["lon"]) * ratio,
            }
        remaining -= segment
    return geometry[-1]
