from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import Database
from app.farm_summary import build_farm_summary, format_line_alert
from app.line_notifier import LineNotifier
from app.mqtt_client import MqttIngestClient
from app.service import DataService
from app.tmd_weather import PlaceQuery, TmdApiError, TmdWeatherClient

from typing import Literal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


db = Database(settings.db_path)
service = DataService(db)
mqtt_client = MqttIngestClient(settings, service)
tmd_client = TmdWeatherClient(settings.tmd_base_url, settings.tmd_access_token)
line_notifier = LineNotifier(settings.line_channel_access_token, settings.line_user_id)

_last_line_alert_sent_at: dt.datetime | None = None
_last_line_alert_fingerprint: str | None = None


def _choose_place(
    province: str | None,
    amphoe: str | None,
    tambon: str | None,
) -> PlaceQuery:
    p = (province or settings.tmd_province).strip()
    a = (amphoe or settings.tmd_amphoe).strip() or None
    t = (tambon or settings.tmd_tambon).strip() or None
    if not p:
        raise HTTPException(status_code=400, detail="province is required")
    return PlaceQuery(province=p, amphoe=a, tambon=t)


def _format_location_name(location: dict | None) -> str:
    if not isinstance(location, dict):
        return "ไม่ระบุพื้นที่"
    parts = [location.get("tambon"), location.get("amphoe"), location.get("province")]
    return " ".join(str(x).strip() for x in parts if x)


async def _build_weather_and_summary(place: PlaceQuery, duration_days: int | None = None) -> dict:
    weather = await tmd_client.fetch_daily_by_place(
        query=place,
        duration_days=duration_days or settings.tmd_forecast_days,
    )
    latest = service.get_latest()
    summary = build_farm_summary(latest, weather)
    return {
        "place": {
            "province": place.province,
            "amphoe": place.amphoe,
            "tambon": place.tambon,
        },
        "weather": weather,
        "sensor_latest": latest,
        "summary": summary,
    }


async def periodic_cleanup(stop_event: asyncio.Event) -> None:
    # Run periodic retention cleanup so DB size stays bounded even without restarts.
    while not stop_event.is_set():
        try:
            deleted = db.cleanup_old_data(settings.retain_days)
            if deleted:
                logger.info("Periodic cleanup removed %s rows", deleted)
        except Exception as exc:  # pragma: no cover
            logger.exception("Periodic cleanup failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
        except asyncio.TimeoutError:
            continue


async def periodic_line_alert(stop_event: asyncio.Event) -> None:
    global _last_line_alert_sent_at
    global _last_line_alert_fingerprint

    while not stop_event.is_set():
        try:
            if settings.line_alert_enabled and line_notifier.enabled and settings.tmd_province:
                payload = await _build_weather_and_summary(
                    PlaceQuery(
                        province=settings.tmd_province,
                        amphoe=settings.tmd_amphoe or None,
                        tambon=settings.tmd_tambon or None,
                    ),
                    duration_days=3,
                )
                summary = payload["summary"]
                risk_level = summary.get("risk_level")
                forecast_3d = summary.get("snapshot", {}).get("forecast_3d", {})
                rain_sum = forecast_3d.get("rain_sum")
                vpd_kpa = summary.get("snapshot", {}).get("vpd_kpa")
                fingerprint = f"{risk_level}|{summary.get('headline')}|{rain_sum}|{vpd_kpa}"

                cooldown = dt.timedelta(minutes=max(1, settings.line_alert_cooldown_minutes))
                now = dt.datetime.now(dt.timezone.utc)
                cooldown_ok = _last_line_alert_sent_at is None or (now - _last_line_alert_sent_at) >= cooldown
                changed = _last_line_alert_fingerprint != fingerprint

                if risk_level in {"warning", "danger"} and (cooldown_ok or changed):
                    location_name = _format_location_name(payload.get("weather", {}).get("location"))
                    message = format_line_alert(location_name, summary)
                    sent = await line_notifier.send_text(message)
                    if sent:
                        _last_line_alert_sent_at = now
                        _last_line_alert_fingerprint = fingerprint
                        logger.info("Sent LINE alert: %s", fingerprint)
        except Exception as exc:  # pragma: no cover
            logger.exception("Periodic LINE alert failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(60, settings.line_alert_interval_seconds))
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(periodic_cleanup(stop_event))
    line_alert_task = asyncio.create_task(periodic_line_alert(stop_event))
    mqtt_client.start()
    logger.info("Application startup complete")
    try:
        yield
    finally:
        stop_event.set()
        await cleanup_task
        await line_alert_task
        mqtt_client.stop()
        deleted = db.cleanup_old_data(settings.retain_days)
        logger.info("Cleanup removed %s rows", deleted)
        db.close()
        logger.info("Application shutdown complete")


app = FastAPI(title="Durian Dashboard", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "refresh_seconds": settings.refresh_seconds,
            "topic": settings.mqtt_topic,
        },
    )


@app.get("/api/latest")
async def api_latest() -> JSONResponse:
    latest = service.get_latest()
    return JSONResponse(content={"data": latest})


@app.get("/api/history")
async def api_history(
    field: str = Query("vpd_kpa"),
    hours: int = Query(24, ge=1, le=168),
) -> JSONResponse:
    rows = service.get_history(field=field, hours=hours)
    return JSONResponse(content={"field": field, "hours": hours, "points": rows})


# --- New: API for scatter plot pairs ---
@app.get("/api/scatter")
async def api_scatter(
    pair: Literal["air", "soil"] = Query("air"),
    hours: int = Query(24, ge=1, le=168),
) -> JSONResponse:
    # Get (x, y) pairs for scatter plot
    if pair == "air":
        xfield, yfield = "air_temp", "air_humi"
    else:
        xfield, yfield = "soil_temp", "soil_humi"
    points = service.get_scatter(xfield, yfield, hours=hours)
    return JSONResponse(content={"pair": pair, "hours": hours, "points": points})


@app.get("/api/weather")
async def api_weather(
    province: str = Query("", max_length=120),
    amphoe: str = Query("", max_length=120),
    tambon: str = Query("", max_length=120),
    duration_days: int = Query(7, ge=1, le=14),
) -> JSONResponse:
    try:
        place = _choose_place(province, amphoe, tambon)
        data = await tmd_client.fetch_daily_by_place(place, duration_days=duration_days)
    except TmdApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse(content=data)


@app.get("/api/farm-summary")
async def api_farm_summary(
    province: str = Query("", max_length=120),
    amphoe: str = Query("", max_length=120),
    tambon: str = Query("", max_length=120),
    duration_days: int = Query(7, ge=1, le=14),
) -> JSONResponse:
    try:
        place = _choose_place(province, amphoe, tambon)
        data = await _build_weather_and_summary(place=place, duration_days=duration_days)
    except TmdApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse(content=data)


@app.post("/api/line/test-alert")
async def api_line_test_alert(
    province: str = Query("", max_length=120),
    amphoe: str = Query("", max_length=120),
    tambon: str = Query("", max_length=120),
) -> JSONResponse:
    if not line_notifier.enabled:
        raise HTTPException(status_code=400, detail="LINE notifier is not configured")
    try:
        place = _choose_place(province, amphoe, tambon)
        payload = await _build_weather_and_summary(place=place, duration_days=3)
    except TmdApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    location_name = _format_location_name(payload.get("weather", {}).get("location"))
    message = format_line_alert(location_name, payload["summary"])
    sent = await line_notifier.send_text(message)
    return JSONResponse(content={"ok": sent, "location": location_name})


@app.websocket("/ws")
async def websocket_latest(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            latest = service.get_latest()
            await websocket.send_text(json.dumps({"data": latest}))
            await asyncio.sleep(max(1, settings.refresh_seconds))
    except WebSocketDisconnect:
        return
