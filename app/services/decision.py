"""Decision engine for auto-rerouting and alert generation."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas import DecisionResult, PredictionResult, RouteOption


class DecisionEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decide(
        self,
        active_route: RouteOption,
        best_route: RouteOption,
        prediction: PredictionResult,
        auto_optimize: bool = True,
    ) -> DecisionResult:
        if prediction.delay_risk >= self.settings.delay_threshold and best_route.route_id != active_route.route_id:
            if not auto_optimize:
                return DecisionResult(
                    action="recommend_reroute",
                    should_reroute=False,
                    reason="Auto Optimize is OFF. AI recommends switching to a safer route.",
                    recommended_route_id=best_route.route_id,
                    recommended_route_name=best_route.name,
                    alert_message=(
                        f"Delay risk {prediction.delay_risk:.0%} on {active_route.name}. "
                        f"Suggested route: {best_route.name}."
                    ),
                    severity="high",
                )
            return DecisionResult(
                action="reroute",
                should_reroute=True,
                reason="High delay risk detected. Switching to a safer route.",
                recommended_route_id=best_route.route_id,
                recommended_route_name=best_route.name,
                alert_message=(
                    f"Delay risk {prediction.delay_risk:.0%} on {active_route.name}. "
                    f"Rerouting to {best_route.name}."
                ),
                severity="high",
            )
        if prediction.delay_risk >= self.settings.delay_threshold:
            return DecisionResult(
                action="monitor",
                should_reroute=False,
                reason="Delay risk is high, but the active route is still the best option.",
                recommended_route_id=active_route.route_id,
                recommended_route_name=active_route.name,
                alert_message=f"{active_route.name} is under heavy pressure. Watch this truck closely.",
                severity="medium",
            )
        return DecisionResult(
            action="continue",
            should_reroute=False,
            reason="Delay risk is within the safe band.",
            recommended_route_id=active_route.route_id,
            recommended_route_name=active_route.name,
            severity="info",
        )
