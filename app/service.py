from __future__ import annotations

import json
import logging
from threading import Lock
from typing import Any

from app.db import Database
from app.logic import normalize_payload

logger = logging.getLogger(__name__)


class DataService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._latest: dict[str, Any] | None = None
        self._latest_lock = Lock()

    def process_mqtt_payload(self, payload_raw: str | bytes) -> None:
        try:
            if isinstance(payload_raw, bytes):
                payload_raw = payload_raw.decode("utf-8")
            payload = json.loads(payload_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Skipping invalid MQTT payload")
            return

        sample = normalize_payload(payload)

        defaults = {
            "air_temp": None,
            "air_humi": None,
            "lux": None,
            "wind_speed_avg5m": None,
            "wind_dir_deg": None,
            "wind_dir_th": None,
            "soil_temp": None,
            "soil_humi": None,
            "ec": None,
            "ph": None,
            "n": None,
            "p": None,
            "k": None,
            "es_kpa": None,
            "ea_kpa": None,
            "vpd_kpa": None,
            "solar_wm2_est": None,
            "solar_mj_m2_h_est": None,
            "eto_mm_h_est": None,
            "eto_mm_day_est": None,
            "vpd_status": None,
            "vpd_message": None,
            "vpd_action": None,
            "ph_status": None,
            "ph_message": None,
            "ph_action": None,
        }

        db_sample = {**defaults, **sample}
        self.db.insert_sample(db_sample)

        with self._latest_lock:
            self._latest = db_sample

    def get_latest(self) -> dict[str, Any] | None:
        with self._latest_lock:
            if self._latest is not None:
                return dict(self._latest)
        latest = self.db.get_latest()
        if latest:
            with self._latest_lock:
                self._latest = latest
        return latest

    def get_history(self, field: str, hours: int) -> list[dict[str, Any]]:
        return self.db.get_history(field, hours=hours)

    def get_scatter(self, xfield: str, yfield: str, hours: int) -> list[dict[str, Any]]:
        return self.db.get_scatter(xfield, yfield, hours=hours)
