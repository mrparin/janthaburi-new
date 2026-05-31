from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mqtt_host: str = os.getenv("MQTT_HOST", "sci-iot.ddns.net")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_topic: str = os.getenv("MQTT_TOPIC", "durian_farm1/node_sensor")
    mqtt_qos: int = int(os.getenv("MQTT_QOS", "1"))

    db_path: str = os.getenv("DB_PATH", "./data/durian_dashboard.db")
    retain_days: int = int(os.getenv("RETAIN_DAYS", "90"))

    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8080"))
    refresh_seconds: int = int(os.getenv("REFRESH_SECONDS", "3"))

    tmd_base_url: str = os.getenv("TMD_BASE_URL", "https://data.tmd.go.th/nwpapi/v1")
    tmd_access_token: str = os.getenv("TMD_ACCESS_TOKEN", "")
    tmd_province: str = os.getenv("TMD_PROVINCE", "")
    tmd_amphoe: str = os.getenv("TMD_AMPHOE", "")
    tmd_tambon: str = os.getenv("TMD_TAMBON", "")
    tmd_forecast_days: int = int(os.getenv("TMD_FORECAST_DAYS", "7"))

    line_channel_access_token: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id: str = os.getenv("LINE_USER_ID", "")
    line_alert_enabled: bool = _env_bool("LINE_ALERT_ENABLED", False)
    line_alert_interval_seconds: int = int(os.getenv("LINE_ALERT_INTERVAL_SECONDS", "600"))
    line_alert_cooldown_minutes: int = int(os.getenv("LINE_ALERT_COOLDOWN_MINUTES", "180"))


settings = Settings()
