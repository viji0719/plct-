"""SQLite helper functions for telemetry and alerts."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.models.schemas import AlertItem, TruckStatus


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    truck_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    eta_minutes REAL NOT NULL,
                    delay_risk REAL NOT NULL,
                    route_name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    truck_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_telemetry(self, truck: TruckStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telemetry (
                    truck_id,
                    timestamp,
                    lat,
                    lon,
                    eta_minutes,
                    delay_risk,
                    route_name,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    truck.truck_id,
                    truck.last_updated.isoformat(),
                    truck.current_position["lat"],
                    truck.current_position["lon"],
                    truck.delay_prediction.eta_minutes,
                    truck.delay_prediction.delay_risk,
                    truck.active_route_name,
                    truck.status,
                ),
            )
            conn.commit()

    def save_alert(self, alert: AlertItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alerts (truck_id, severity, message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    alert.truck_id,
                    alert.severity,
                    alert.message,
                    alert.created_at.isoformat(),
                ),
            )
            conn.commit()

    def fetch_recent_alerts(self, limit: int = 20) -> list[AlertItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT truck_id, severity, message, created_at
                FROM alerts
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit * 5,),
            ).fetchall()
        alerts: list[AlertItem] = []
        seen_signatures: set[tuple[str, str, str]] = set()
        for row in rows:
            signature = (row["truck_id"], row["severity"], row["message"])
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            alerts.append(
                AlertItem(
                    truck_id=row["truck_id"],
                    severity=row["severity"],
                    message=row["message"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
            if len(alerts) >= limit:
                break
        return alerts

    def fetch_truck_telemetry(self, truck_id: str, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT truck_id, timestamp, eta_minutes, delay_risk, route_name, status
                FROM telemetry
                WHERE truck_id = ?
                ORDER BY datetime(timestamp) DESC
                LIMIT ?
                """,
                (truck_id, limit),
            ).fetchall()
        return [
            {
                "truck_id": row["truck_id"],
                "timestamp": row["timestamp"],
                "eta_minutes": row["eta_minutes"],
                "delay_risk": row["delay_risk"],
                "route_name": row["route_name"],
                "status": row["status"],
            }
            for row in reversed(rows)
        ]

    def clear_demo_data(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM telemetry")
            conn.execute("DELETE FROM alerts")
            conn.commit()
