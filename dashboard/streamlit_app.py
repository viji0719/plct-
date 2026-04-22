"""Streamlit dashboard for the Predictive Logistics Control Tower."""

from __future__ import annotations

import os
import time
from typing import Any

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REFRESH_MIN_SECONDS = 2
REFRESH_MAX_SECONDS = 5


def initialize_state() -> None:
    if "dashboard_state" not in st.session_state:
        st.session_state.dashboard_state = None
    if "previous_dashboard_state" not in st.session_state:
        st.session_state.previous_dashboard_state = None
    if "map_data" not in st.session_state:
        st.session_state.map_data = []
    if "last_refresh_at" not in st.session_state:
        st.session_state.last_refresh_at = 0.0
    if "auto_optimize" not in st.session_state:
        st.session_state.auto_optimize = True
    if "telemetry_history" not in st.session_state:
        st.session_state.telemetry_history = {}


def fetch_state(advance: bool = False) -> dict[str, Any]:
    endpoint = "/api/simulation/tick" if advance else "/api/dashboard/state"
    response = requests.post(f"{BACKEND_URL}{endpoint}", timeout=8) if advance else requests.get(
        f"{BACKEND_URL}{endpoint}",
        timeout=8,
    )
    response.raise_for_status()
    return response.json()


def fetch_control_mode() -> bool:
    response = requests.get(f"{BACKEND_URL}/api/control-mode", timeout=8)
    response.raise_for_status()
    return response.json()["auto_optimize"]


def update_control_mode(auto_optimize: bool) -> bool:
    response = requests.post(
        f"{BACKEND_URL}/api/control-mode",
        json={"auto_optimize": auto_optimize},
        timeout=8,
    )
    response.raise_for_status()
    return response.json()["auto_optimize"]


def get_default_prediction() -> dict[str, Any]:
    return {
        "eta_minutes": 0.0,
        "predicted_delay_minutes": 0.0,
        "delay_risk": 0.0,
        "model_name": "AI Risk Prediction Engine",
        "risk_breakdown": {
            "traffic": 0.0,
            "distance": 0.0,
            "route_risk": 0.0,
            "time_pressure": 0.0,
        },
    }


def normalize_prediction(prediction: dict[str, Any] | None) -> dict[str, Any]:
    normalized = get_default_prediction()
    if prediction:
        normalized.update({key: value for key, value in prediction.items() if key != "risk_breakdown"})
        normalized["risk_breakdown"].update(prediction.get("risk_breakdown", {}))
    return normalized


def normalize_truck(truck: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(truck)
    normalized["delay_prediction"] = normalize_prediction(truck.get("delay_prediction"))
    normalized["decision"] = truck.get("decision", {})
    normalized["route_options"] = truck.get("route_options", [])
    normalized["current_position"] = truck.get("current_position", {"lat": 0.0, "lon": 0.0})
    normalized["destination_position"] = truck.get("destination_position", {"lat": 0.0, "lon": 0.0})
    return normalized


def fetch_truck_telemetry(truck_id: str, limit: int = 20) -> list[dict[str, Any]]:
    response = requests.get(f"{BACKEND_URL}/api/trucks/{truck_id}/telemetry", params={"limit": limit}, timeout=8)
    response.raise_for_status()
    return response.json()


def severity_badge(severity: str, message: str) -> None:
    if severity == "high":
        st.error(message)
    elif severity == "medium":
        st.warning(message)
    else:
        st.info(message)


def risk_level(delay_risk: float) -> str:
    if delay_risk < 0.30:
        return "Low"
    if delay_risk < 0.70:
        return "Medium"
    return "High"


def risk_color(delay_risk: float) -> str:
    if delay_risk < 0.30:
        return "#2e8b57"
    if delay_risk < 0.70:
        return "#f39c12"
    return "#d64541"


def build_visual_trucks(trucks: list[dict]) -> list[dict]:
    previous_positions = {item["truck_id"]: item for item in st.session_state.map_data}
    visual_trucks: list[dict] = []
    updated_truck_positions: list[dict] = []

    for truck in trucks:
        previous = previous_positions.get(truck["truck_id"])
        current = truck["current_position"]
        if previous:
            lat = previous["lat"] + (current["lat"] - previous["lat"]) * 0.55
            lon = previous["lon"] + (current["lon"] - previous["lon"]) * 0.55
        else:
            lat = current["lat"]
            lon = current["lon"]

        visual_truck = {
            **truck,
            "current_position": {"lat": lat, "lon": lon},
        }
        visual_trucks.append(visual_truck)
        updated_truck_positions.append(
            {
                "truck_id": truck["truck_id"],
                "lat": current["lat"],
                "lon": current["lon"],
                "active_route_id": truck["active_route_id"],
            }
        )

    st.session_state.map_data = updated_truck_positions
    return visual_trucks


def build_map(trucks: list[dict], previous_trucks: dict[str, dict]) -> folium.Map:
    center_lat = sum(item["current_position"]["lat"] for item in trucks) / len(trucks)
    center_lon = sum(item["current_position"]["lon"] for item in trucks) / len(trucks)
    logistics_map = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap")

    for truck in trucks:
        current_risk = truck["delay_prediction"]["delay_risk"]
        marker_color = risk_color(current_risk)
        route = next(
            route for route in truck["route_options"] if route["route_id"] == truck["active_route_id"]
        )
        previous_route = previous_trucks.get(truck["truck_id"], {})
        previous_route_id = previous_route.get("active_route_id")
        if previous_route_id and previous_route_id != truck["active_route_id"]:
            previous_route_data = next(
                (item for item in truck["route_options"] if item["route_id"] == previous_route_id),
                None,
            )
            if previous_route_data:
                old_geometry = [(point["lat"], point["lon"]) for point in previous_route_data["geometry"]]
                folium.PolyLine(
                    old_geometry,
                    color="#a0a0a0",
                    weight=3,
                    opacity=0.6,
                    dash_array="8, 10",
                    tooltip=f"Old Route - {previous_route_data['name']}",
                ).add_to(logistics_map)

        geometry = [(point["lat"], point["lon"]) for point in route["geometry"]]
        folium.PolyLine(
            geometry,
            color="#1f77b4" if truck["decision"]["should_reroute"] else marker_color,
            weight=4,
            opacity=0.7,
            tooltip=f"{truck['truck_id']} - {truck['active_route_name']}",
        ).add_to(logistics_map)
        folium.CircleMarker(
            location=[truck["current_position"]["lat"], truck["current_position"]["lon"]],
            tooltip=truck["truck_id"],
            popup=(
                f"{truck['truck_id']}<br>"
                f"Driver: {truck['driver_name']}<br>"
                f"ETA: {truck['delay_prediction']['eta_minutes']} mins<br>"
                f"Risk: {truck['delay_prediction']['delay_risk']}<br>"
                f"AI Engine: {truck['delay_prediction']['model_name']}"
            ),
            radius=9,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.95,
        ).add_to(logistics_map)
        folium.CircleMarker(
            location=[truck["destination_position"]["lat"], truck["destination_position"]["lon"]],
            radius=6,
            color="#e74c3c",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"Destination: {truck['destination_name']}",
        ).add_to(logistics_map)

    return logistics_map


def route_comparison_dataframe(truck: dict) -> pd.DataFrame:
    dataframe = pd.DataFrame(truck["route_options"])
    dataframe["Recommendation"] = dataframe["route_id"].apply(
        lambda route_id: "Best Route" if route_id == truck["decision"]["recommended_route_id"] else (
            "Active Route" if route_id == truck["active_route_id"] else ""
        )
    )
    return dataframe[
        [
            "name",
            "distance_km",
            "travel_time_minutes",
            "traffic_factor",
            "cost_factor",
            "risk_factor",
            "score",
            "Recommendation",
        ]
    ].rename(
        columns={
            "name": "Route",
            "distance_km": "Distance (km)",
            "travel_time_minutes": "Travel Time (min)",
            "traffic_factor": "Traffic",
            "cost_factor": "Cost",
            "risk_factor": "Risk",
            "score": "Score",
            "Recommendation": "AI Recommendation",
        }
    )


def styled_route_comparison(truck: dict):
    dataframe = route_comparison_dataframe(truck)

    def highlight_row(row: pd.Series) -> list[str]:
        if row["AI Recommendation"] == "Best Route":
            return ["background-color: #00ff7f; color: #000; font-weight: bold;"] * len(row)
        if row["AI Recommendation"] == "Active Route":
            return ["background-color: #00bfff; color: #000; font-weight: bold;"] * len(row)
        return [""] * len(row)

    return dataframe.style.apply(highlight_row, axis=1)


def dedupe_alerts(alerts: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for alert in alerts:
        signature = (alert["truck_id"], alert["severity"], alert["message"])
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(alert)
    return deduped


def risk_driver_labels(prediction: dict) -> list[str]:
    labels: list[str] = []
    breakdown = normalize_prediction(prediction).get("risk_breakdown", {})
    if breakdown.get("traffic", 0) >= 0.65:
        labels.append("Traffic: High congestion")
    elif breakdown.get("traffic", 0) >= 0.35:
        labels.append("Traffic: Moderate congestion")
    else:
        labels.append("Traffic: Low congestion")
    if breakdown.get("distance", 0) >= 0.65:
        labels.append("Distance: Long haul")
    elif breakdown.get("distance", 0) >= 0.35:
        labels.append("Distance: Medium haul")
    else:
        labels.append("Distance: Short haul")
    if breakdown.get("route_risk", 0) >= 0.55:
        labels.append("Route Risk: Elevated")
    else:
        labels.append("Route Risk: Stable corridor")
    if breakdown.get("time_pressure", 0) >= 0.55:
        labels.append("Time Window: Tight")
    else:
        labels.append("Time Window: Off-peak hours")
    return labels


def render_metric_card(title: str, value: str, caption: str | None = None) -> None:
    body = f"<div class='metric-card'><div class='metric-title'>{title}</div><div class='metric-value'>{value}</div>"
    if caption:
        body += f"<div class='metric-caption'>{caption}</div>"
    body += "</div>"
    st.markdown(body, unsafe_allow_html=True)


def render_risk_progress(label: str, value: float) -> None:
    safe_value = max(0.0, min(1.0, value))
    st.progress(safe_value)
    st.caption(f"{label}: {risk_level(safe_value)} impact ({safe_value:.0%})")


def sync_dashboard_state(request_advance: bool, force_reset: bool = False) -> dict[str, Any]:
    st.session_state.previous_dashboard_state = st.session_state.dashboard_state
    if force_reset:
        response = requests.post(f"{BACKEND_URL}/api/simulation/reset", timeout=8)
        response.raise_for_status()
        state = response.json()
    else:
        state = fetch_state(advance=request_advance)
    st.session_state.dashboard_state = state
    st.session_state.last_refresh_at = time.time()
    return state


st.set_page_config(
    page_title="PLCT Dashboard",
    page_icon=":truck:",
    layout="wide",
)

initialize_state()

st.markdown(
    "<h1 class='main-title'>Predictive Logistics Control Tower</h1>"
    "<p class='main-subtitle'>AI-powered control tower for live visibility, delay prediction, smart alerts, and dynamic route decisions.</p>",
    unsafe_allow_html=True
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Outfit', sans-serif;
    }

    /* Shared styles using Streamlit native CSS variables for perfect Theme switching */
    .risk-pill {
        display: inline-block;
        padding: 0.4rem 1.2rem;
        border-radius: 50px;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: white !important;
    }
    
    .kpi-card, .metric-card {
        padding: 1.5rem;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 1.5rem;
        background: linear-gradient(135deg, var(--secondary-background-color) 0%, var(--background-color) 100%);
        border: 2px solid rgba(150, 150, 150, 0.1);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        color: var(--text-color);
        position: relative;
        overflow: hidden;
    }
    .kpi-card {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, var(--secondary-background-color) 100%);
        border-color: rgba(59, 130, 246, 0.3);
    }
    .kpi-card:hover, .metric-card:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
        z-index: 10;
    }
    
    /* Hover effects for different themes */
    @media (prefers-color-scheme: dark) {
        .kpi-card:hover, .metric-card:hover {
            border-color: #ffffff !important;
            box-shadow: 0 0 20px rgba(255, 255, 255, 0.4), 0 15px 30px rgba(0, 0, 0, 0.4);
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(30, 41, 59, 1) 100%);
        }
    }
    @media (prefers-color-scheme: light) {
        .kpi-card:hover, .metric-card:hover {
            border-color: var(--primary-color) !important;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.3), 0 15px 30px rgba(0, 0, 0, 0.1);
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, #ffffff 100%);
        }
    }

    .metric-card {
        text-align: left;
        min-height: 140px;
    }
    .metric-title {
        font-size: 1rem;
        margin-bottom: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        opacity: 0.7;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.2;
        color: var(--primary-color);
    }
    .metric-caption {
        margin-top: 0.8rem;
        font-size: 1rem;
        font-weight: 500;
        opacity: 0.6;
    }
    .tower-tag {
        padding: 0.3rem 0.8rem;
        border-radius: 6px;
        font-weight: 700;
        letter-spacing: 0.02em;
        font-size: 1.1rem;
        color: var(--primary-color);
        background-color: var(--secondary-background-color);
        border: 1px solid var(--primary-color);
    }
    
    /* Increase Streamlit native text sizes */
    div[data-testid="stMetricValue"] {
        font-size: 2.6rem !important;
        font-weight: 800 !important;
        color: var(--primary-color) !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
    }
    p, span, label {
        font-size: 1.15rem !important;
    }
    
    /* Main Title Styling */
    .main-title {
        font-size: 5rem !important;
        font-weight: 900 !important;
        color: #3b82f6 !important;
        text-align: center !important;
        letter-spacing: -0.04em;
        margin-top: 1rem !important;
        margin-bottom: 0.5rem !important;
        line-height: 1.1 !important;
        text-shadow: 0 4px 15px rgba(0,0,0,0.3);
        width: 100% !important;
        display: block !important;
    }
    
    .main-subtitle {
        text-align: center !important;
        font-size: 1.5rem !important;
        width: 100% !important;
        display: block !important;
        margin-bottom: 3rem !important;
        opacity: 0.8;
        color: var(--text-color);
        font-weight: 500;
    }

    /* Section Headings */
    h2, .stHeader h2 {
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        margin-top: 2rem !important;
        margin-bottom: 1.5rem !important;
        color: var(--primary-color) !important;
        border-bottom: 2px solid rgba(150, 150, 150, 0.1);
        padding-bottom: 0.5rem;
    }
    
    div.stButton > button:first-child {
        border-radius: 12px;
        font-weight: 800;
        font-size: 1.2rem !important;
        padding: 0.8rem 2rem !important;
        color: #ffffff !important;
        background: linear-gradient(45deg, #007bff, #6610f2) !important;
        border: none !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(0, 123, 255, 0.4) !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px) scale(1.05) !important;
        box-shadow: 0 8px 25px rgba(102, 16, 242, 0.5) !important;
        filter: brightness(1.2) !important;
    }
    div.stButton > button:first-child:active {
        transform: translateY(0) scale(0.98) !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(150, 150, 150, 0.2);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    backend_control_mode = fetch_control_mode()
    st.session_state.auto_optimize = backend_control_mode
except requests.RequestException:
    backend_control_mode = st.session_state.auto_optimize

control_col1, control_col2, control_col3, control_col4 = st.columns([1.1, 1.1, 1.0, 1.0])
with control_col1:
    auto_advance = st.checkbox("Advance simulation on refresh", value=True)
with control_col2:
    live_mode = st.checkbox("Live dashboard mode", value=False)
with control_col3:
    refresh_seconds = st.slider("Refresh every (sec)", REFRESH_MIN_SECONDS, REFRESH_MAX_SECONDS, 3)
with control_col4:
    if st.button("Reset Simulation", width="stretch"):
        try:
            sync_dashboard_state(request_advance=False, force_reset=True)
            st.session_state.map_data = []
        except requests.RequestException:
            st.error("Could not reset the simulation.")

toggle_col1, toggle_col2 = st.columns([1.2, 2.0])
with toggle_col1:
    auto_optimize = st.toggle("Control Tower Auto Optimize", value=backend_control_mode)
with toggle_col2:
    st.markdown(
        f"<span class='tower-tag'>AI Risk Prediction Engine</span> | "
        f"Auto optimize is currently <strong>{'ON' if auto_optimize else 'OFF'}</strong>.",
        unsafe_allow_html=True,
    )

if auto_optimize != st.session_state.auto_optimize:
    try:
        st.session_state.auto_optimize = update_control_mode(auto_optimize)
    except requests.RequestException:
        st.error("Could not update control tower mode.")

try:
    refresh_now = st.button("Refresh Dashboard", width="stretch")
    state_missing = st.session_state.dashboard_state is None
    cooldown_elapsed = (time.time() - st.session_state.last_refresh_at) >= refresh_seconds
    should_refresh = refresh_now or state_missing or cooldown_elapsed
    if should_refresh:
        state = sync_dashboard_state(request_advance=auto_advance)
    else:
        state = st.session_state.dashboard_state
except requests.RequestException:
    st.error("Backend is not reachable. Start FastAPI first: `uvicorn app.main:app --reload`")
    st.stop()

trucks = [normalize_truck(truck) for truck in state["trucks"]]
alerts = dedupe_alerts(state["alerts"])
previous_trucks = {
    truck["truck_id"]: normalize_truck(truck)
    for truck in (st.session_state.previous_dashboard_state or {}).get("trucks", [])
}
visual_trucks = build_visual_trucks(trucks)

metric_cols = st.columns(4)
high_risk_count = sum(item["delay_prediction"]["delay_risk"] >= 0.65 for item in trucks)
reroute_count = sum(item["decision"]["should_reroute"] for item in trucks)
delivered_count = sum(item["status"] == "Delivered" for item in trucks)
avg_delay = round(sum(item["delay_prediction"]["predicted_delay_minutes"] for item in trucks) / len(trucks), 1)
on_time_ratio = round(
    (sum(item["delay_prediction"]["delay_risk"] < 0.65 for item in trucks) / len(trucks)) * 100,
    1,
)
metric_cols[0].markdown(f"<div class='kpi-card'><strong>Simulation Tick</strong><br>{state['tick']}</div>", unsafe_allow_html=True)
metric_cols[1].markdown(f"<div class='kpi-card'><strong>Avg Delay</strong><br>{avg_delay} min</div>", unsafe_allow_html=True)
metric_cols[2].markdown(f"<div class='kpi-card'><strong>High-Risk Trucks</strong><br>{high_risk_count}</div>", unsafe_allow_html=True)
metric_cols[3].markdown(f"<div class='kpi-card'><strong>On-Time Confidence</strong><br>{on_time_ratio}%</div>", unsafe_allow_html=True)

metric_cols_2 = st.columns(3)
metric_cols_2[0].metric("Auto Reroutes", reroute_count)
metric_cols_2[1].metric("Delivered", delivered_count)
metric_cols_2[2].metric("Unique Alerts", len(alerts))

left_col, right_col = st.columns([1.7, 1.0])

with left_col:
    st.subheader("Live Fleet Map")
    map_placeholder = st.empty()
    with map_placeholder.container():
        live_map = build_map(visual_trucks, previous_trucks)
        st_folium(live_map, width=None, height=520, returned_objects=[])

with right_col:
    st.subheader("Alerts")
    alerts_placeholder = st.empty()
    with alerts_placeholder.container():
        if not alerts:
            st.success("No active alerts right now.")
        else:
            for alert in alerts[:8]:
                severity_badge(
                    alert["severity"],
                    f"{alert['created_at']} | {alert['truck_id']} | {alert['message']}",
                )

st.subheader("Fleet Overview")
fleet_df = pd.DataFrame(
    [
        {
            "Truck": truck["truck_id"],
            "Driver": truck["driver_name"],
            "Cargo": truck["cargo_type"],
            "Route": truck["active_route_name"],
            "Status": truck["status"],
            "ETA (min)": truck["delay_prediction"]["eta_minutes"],
            "Predicted Delay (min)": truck["delay_prediction"]["predicted_delay_minutes"],
            "Delay Risk": truck["delay_prediction"]["delay_risk"],
            "Risk Level": risk_level(truck["delay_prediction"]["delay_risk"]),
            "Decision": truck["decision"]["action"],
        }
        for truck in trucks
    ]
)
st.dataframe(fleet_df, width="stretch", hide_index=True)

truck_lookup = {truck["truck_id"]: truck for truck in trucks}
selected_truck_id = st.selectbox("Select a truck for route comparison", options=list(truck_lookup))
selected_truck = truck_lookup[selected_truck_id]

detail_col1, detail_col2 = st.columns([1.0, 1.0])
with detail_col1:
    try:
        prediction = normalize_prediction(selected_truck.get("delay_prediction"))
        decision = selected_truck.get("decision", {})
        breakdown = prediction.get("risk_breakdown", {})
        pill_color = risk_color(prediction.get("delay_risk", 0.0))
        st.subheader(f"{selected_truck_id} Delay Insight")
        st.markdown(
            (
                f"<span class='risk-pill' style='background:{pill_color}; color:white;'>"
                f"{risk_level(prediction.get('delay_risk', 0.0))} Risk</span>"
            ),
            unsafe_allow_html=True,
        )
        card_col1, card_col2 = st.columns(2)
        with card_col1:
            render_metric_card("AI Model", prediction.get("model_name", "AI Risk Prediction Engine"), "Decision engine")
            render_metric_card("ETA", f"{prediction.get('eta_minutes', 0):.1f} min", "Current projected arrival")
            render_metric_card("Delay", f"{prediction.get('predicted_delay_minutes', 0):.1f} min", "Predicted extra time")
        with card_col2:
            render_metric_card("Risk", risk_level(prediction.get("delay_risk", 0.0)), f"{prediction.get('delay_risk', 0.0):.0%} delay probability")
            render_metric_card("Confidence", f"{max(55, round(prediction.get('delay_risk', 0.0) * 100))}%", "AI decision confidence")
            render_metric_card(
                "Suggested Route",
                decision.get("recommended_route_name", "Current Route"),
                decision.get("reason", "Monitoring current shipment"),
            )

        st.caption("Why delay is happening")
        for label in risk_driver_labels(prediction):
            st.write(f"- {label}")
        render_risk_progress("Traffic Impact", breakdown.get("traffic", 0))
        render_risk_progress("Distance Impact", breakdown.get("distance", 0))
        render_risk_progress("Route Risk Impact", breakdown.get("route_risk", 0))
        render_risk_progress("Time Pressure Impact", breakdown.get("time_pressure", 0))

        telemetry_history = fetch_truck_telemetry(selected_truck_id, limit=12)
        st.session_state.telemetry_history[selected_truck_id] = telemetry_history
        if telemetry_history:
            trend_df = pd.DataFrame(telemetry_history)
            trend_df["timestamp"] = pd.to_datetime(trend_df["timestamp"])
            trend_df = trend_df.set_index("timestamp")[["eta_minutes", "delay_risk"]]
            st.caption("Delay trend over time")
            st.line_chart(trend_df, height=220)
    except Exception:
        st.warning("Data not available yet")

with detail_col2:
    st.subheader(f"{selected_truck_id} Route Comparison")
    st.table(styled_route_comparison(selected_truck))

st.caption(
    "Tip: connect an OpenRouteService API key in `.env` to swap demo routes with real alternative routes."
)

if live_mode:
    time.sleep(refresh_seconds)
    st.rerun()
