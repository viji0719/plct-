"""Delay prediction logic: a simple rule engine plus an optional ML model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.models.schemas import PredictionResult
from app.utils import clamp

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
except ImportError:  # pragma: no cover - safe fallback when sklearn is missing
    RandomForestClassifier = None
    RandomForestRegressor = None


@dataclass
class PredictionFeatures:
    distance_km: float
    traffic_factor: float
    avg_speed_kmph: float
    route_risk: float
    time_pressure: float


def build_risk_breakdown(features: PredictionFeatures) -> dict[str, float]:
    """Expose the main risk drivers so the dashboard can explain the prediction."""
    return {
        "distance": round(clamp(features.distance_km / 400), 2),
        "traffic": round(clamp(features.traffic_factor), 2),
        "route_risk": round(clamp(features.route_risk), 2),
        "time_pressure": round(clamp(features.time_pressure), 2),
    }


class SimpleDelayPredictor:
    """Fast heuristic model for demo and explanation."""

    def predict(self, features: PredictionFeatures) -> PredictionResult:
        eta_minutes = max(8.0, (features.distance_km / max(features.avg_speed_kmph, 15)) * 60)
        risk = (
            0.30 * min(features.distance_km / 400, 1.0)
            + 0.35 * features.traffic_factor
            + 0.20 * features.route_risk
            + 0.15 * features.time_pressure
        )
        delay_minutes = eta_minutes * (0.15 + risk * 0.45)
        return PredictionResult(
            delay_risk=round(clamp(risk), 2),
            predicted_delay_minutes=round(delay_minutes, 1),
            eta_minutes=round(eta_minutes, 1),
            model_name="Simple Heuristic",
            risk_breakdown=build_risk_breakdown(features),
        )


class MLDelayPredictor:
    """Synthetic-data ML model to make the demo look more realistic."""

    def __init__(self) -> None:
        self.enabled = bool(RandomForestClassifier and RandomForestRegressor)
        self.classifier = None
        self.regressor = None
        if self.enabled:
            self._train_models()

    def _train_models(self) -> None:
        rng = np.random.default_rng(42)
        samples = 800
        data = pd.DataFrame(
            {
                "distance_km": rng.uniform(30, 900, samples),
                "traffic_factor": rng.uniform(0.1, 1.0, samples),
                "avg_speed_kmph": rng.uniform(25, 75, samples),
                "route_risk": rng.uniform(0.05, 0.95, samples),
                "time_pressure": rng.uniform(0.1, 1.0, samples),
            }
        )
        data["delay_minutes"] = (
            data["distance_km"] * 0.09
            + data["traffic_factor"] * 38
            + data["route_risk"] * 27
            + data["time_pressure"] * 18
            - data["avg_speed_kmph"] * 0.45
            + rng.normal(0, 6, samples)
        ).clip(lower=5)
        data["delay_flag"] = (data["delay_minutes"] > 35).astype(int)

        features = data[["distance_km", "traffic_factor", "avg_speed_kmph", "route_risk", "time_pressure"]]
        self.regressor = RandomForestRegressor(n_estimators=120, random_state=42)
        self.classifier = RandomForestClassifier(n_estimators=120, random_state=42)
        self.regressor.fit(features, data["delay_minutes"])
        self.classifier.fit(features, data["delay_flag"])

    def predict(self, features: PredictionFeatures) -> PredictionResult | None:
        if not self.enabled or self.regressor is None or self.classifier is None:
            return None
        dataframe = pd.DataFrame(
            [
                {
                    "distance_km": features.distance_km,
                    "traffic_factor": features.traffic_factor,
                    "avg_speed_kmph": features.avg_speed_kmph,
                    "route_risk": features.route_risk,
                    "time_pressure": features.time_pressure,
                }
            ]
        )
        delay_minutes = float(self.regressor.predict(dataframe)[0])
        delay_risk = float(self.classifier.predict_proba(dataframe)[0][1])
        eta_minutes = max(8.0, (features.distance_km / max(features.avg_speed_kmph, 15)) * 60)
        return PredictionResult(
            delay_risk=round(clamp(delay_risk), 2),
            predicted_delay_minutes=round(delay_minutes, 1),
            eta_minutes=round(eta_minutes, 1),
            model_name="Random Forest ML",
            risk_breakdown=build_risk_breakdown(features),
        )


class HybridDelayPredictor:
    """Prefer the ML output, but always keep the simple model as a fallback."""

    def __init__(self) -> None:
        self.simple_predictor = SimpleDelayPredictor()
        self.ml_predictor = MLDelayPredictor()

    def predict(self, features: PredictionFeatures) -> dict[str, PredictionResult]:
        simple_result = self.simple_predictor.predict(features)
        ml_result = self.ml_predictor.predict(features)
        selected = ml_result or simple_result
        return {
            "simple": simple_result,
            "ml": ml_result or simple_result,
            "selected": selected,
        }
