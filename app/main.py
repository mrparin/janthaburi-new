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
from app.location_catalog import ThaiLocationCatalog
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
location_catalog = ThaiLocationCatalog(fallback_provinces=[settings.tmd_province])
line_notifier = LineNotifier(settings.line_channel_access_token, settings.line_user_id)

_last_line_alert_sent_at: dt.datetime | None = None
_last_line_alert_fingerprint: str | None = None
_line_alert_runtime_enabled: bool = settings.line_alert_enabled
_last_risk_level: str | None = None
_last_danger_started_at: dt.datetime | None = None
_last_danger_reminder_at: dt.datetime | None = None
_daily_alert_date: dt.date | None = None
_daily_alert_count: int = 0

_MAX_ALERTS_PER_DAY = 8
_DANGER_REMINDER_EVERY = dt.timedelta(hours=2)
_LINE_ALERT_STATE_KEY = "line_alert_runtime_enabled"


def _risk_severity(level: str | None) -> int:
    if level == "danger":
        return 2
    if level == "warning":
        return 1
    return 0


def _line_alert_runtime_allowed() -> bool:
    return _line_alert_runtime_enabled and line_notifier.enabled and bool(settings.tmd_province)


def _rollover_daily_counter(now: dt.datetime) -> None:
    global _daily_alert_date
    global _daily_alert_count

    today = now.date()
    if _daily_alert_date != today:
        _daily_alert_date = today
        _daily_alert_count = 0


def _line_alert_status_payload() -> dict[str, object]:
    persisted = db.get_state(_LINE_ALERT_STATE_KEY)
    return {
        "enabled": _line_alert_runtime_enabled,
        "effective_enabled": _line_alert_runtime_allowed(),
        "configured_in_env": settings.line_alert_enabled,
        "persisted": persisted,
        "notifier_configured": line_notifier.enabled,
        "has_default_place": bool(settings.tmd_province),
        "daily_limit": _MAX_ALERTS_PER_DAY,
        "daily_sent": _daily_alert_count,
    }


def _load_line_alert_runtime_enabled() -> None:
    global _line_alert_runtime_enabled

    persisted = db.get_state(_LINE_ALERT_STATE_KEY)
    if persisted is None:
        _line_alert_runtime_enabled = settings.line_alert_enabled
        return

    value = persisted.strip().lower()
    _line_alert_runtime_enabled = value in {"1", "true", "yes", "on"}


def _reset_line_alert_state() -> None:
    global _last_line_alert_sent_at
    global _last_line_alert_fingerprint
    global _last_risk_level
    global _last_danger_started_at
    global _last_danger_reminder_at

    _last_line_alert_sent_at = None
    _last_line_alert_fingerprint = None
    _last_risk_level = None
    _last_danger_started_at = None
    _last_danger_reminder_at = None


_load_line_alert_runtime_enabled()


async def _send_line_event_alert(
    *,
    location_name: str,
    summary: dict,
    reason: str,
    event_key: str,
    now: dt.datetime,
) -> bool:
    global _last_line_alert_sent_at
    global _last_line_alert_fingerprint
    global _daily_alert_count

    _rollover_daily_counter(now)
    if _daily_alert_count >= _MAX_ALERTS_PER_DAY:
        return False

    cooldown = dt.timedelta(minutes=max(1, settings.line_alert_cooldown_minutes))
    fingerprint = f"{event_key}|{summary.get('risk_level')}|{summary.get('headline')}"
    if (
        _last_line_alert_fingerprint == fingerprint
        and _last_line_alert_sent_at is not None
        and (now - _last_line_alert_sent_at) < cooldown
    ):
        return False

    message = f"{format_line_alert(location_name, summary)}\n\nเหตุแจ้งเตือน: {reason}"
    sent = await line_notifier.send_text(message)
    if not sent:
        return False

    _last_line_alert_sent_at = now
    _last_line_alert_fingerprint = fingerprint
    _daily_alert_count += 1
    return True


def _choose_place(
    province: str | None,
    amphoe: str | None,
    tambon: str | None,
) -> PlaceQuery:
    # None means "not provided" -> allow default from settings.
    # Empty string means "provided but intentionally blank" -> keep as None (no default fallback).
    p_raw = settings.tmd_province if province is None else province
    a_raw = settings.tmd_amphoe if amphoe is None else amphoe
    t_raw = settings.tmd_tambon if tambon is None else tambon

    p = p_raw.strip()
    a = a_raw.strip() or None
    t = t_raw.strip() or None
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
    global _last_risk_level
    global _last_danger_started_at
    global _last_danger_reminder_at

    while not stop_event.is_set():
        try:
            now = dt.datetime.now(dt.timezone.utc)
            _rollover_daily_counter(now)

            if _line_alert_runtime_allowed():
                payload = await _build_weather_and_summary(
                    PlaceQuery(
                        province=settings.tmd_province,
                        amphoe=settings.tmd_amphoe or None,
                        tambon=settings.tmd_tambon or None,
                    ),
                    duration_days=3,
                )
                summary = payload["summary"]
                risk_level = str(summary.get("risk_level") or "normal")
                location_name = _format_location_name(payload.get("weather", {}).get("location"))

                if risk_level == "danger":
                    if _last_danger_started_at is None:
                        _last_danger_started_at = now
                else:
                    _last_danger_started_at = None
                    _last_danger_reminder_at = None

                event_reason: str | None = None
                event_key: str | None = None

                prev_level = _last_risk_level
                if prev_level is None and risk_level in {"warning", "danger"}:
                    event_reason = "เริ่มเข้าโหมดเฝ้าระวัง"
                    event_key = "bootstrap_risk"
                elif prev_level is not None and _risk_severity(risk_level) > _risk_severity(prev_level):
                    if risk_level == "danger":
                        event_reason = "ระดับความเสี่ยงเพิ่มขึ้นเป็นอันตราย"
                        event_key = "risk_up_danger"
                    else:
                        event_reason = "ระดับความเสี่ยงเพิ่มขึ้นเป็นเฝ้าระวัง"
                        event_key = "risk_up_warning"
                elif prev_level in {"warning", "danger"} and risk_level == "normal":
                    event_reason = "ความเสี่ยงกลับสู่ระดับปกติ"
                    event_key = "risk_recovered"
                elif (
                    risk_level == "danger"
                    and _last_danger_started_at is not None
                    and (now - _last_danger_started_at) >= _DANGER_REMINDER_EVERY
                    and (
                        _last_danger_reminder_at is None
                        or (now - _last_danger_reminder_at) >= _DANGER_REMINDER_EVERY
                    )
                ):
                    event_reason = "อยู่ในระดับอันตรายต่อเนื่องเกิน 2 ชั่วโมง"
                    event_key = "danger_persistent"

                if event_reason and event_key:
                    sent = await _send_line_event_alert(
                        location_name=location_name,
                        summary=summary,
                        reason=event_reason,
                        event_key=event_key,
                        now=now,
                    )
                    if sent:
                        if event_key == "danger_persistent":
                            _last_danger_reminder_at = now
                        logger.info("Sent LINE alert event: %s", event_key)

                _last_risk_level = risk_level
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
            "tmd_province": settings.tmd_province,
            "tmd_amphoe": settings.tmd_amphoe,
            "tmd_tambon": settings.tmd_tambon,
            "tmd_forecast_days": settings.tmd_forecast_days,
        },
    )


@app.get("/api/latest")
async def api_latest() -> JSONResponse:
    latest = service.get_latest()
    return JSONResponse(content={"data": latest})


@app.get("/api/locations/provinces")
async def api_location_provinces() -> JSONResponse:
    provinces = await location_catalog.list_provinces()
    return JSONResponse(content={"items": provinces})


@app.get("/api/locations/amphoes")
async def api_location_amphoes(
    province: str = Query("", max_length=120),
) -> JSONResponse:
    amphoes = await location_catalog.list_amphoes(province)
    return JSONResponse(content={"items": amphoes})


@app.get("/api/locations/tambons")
async def api_location_tambons(
    province: str = Query("", max_length=120),
    amphoe: str = Query("", max_length=120),
) -> JSONResponse:
    tambons = await location_catalog.list_tambons(province, amphoe)
    return JSONResponse(content={"items": tambons})


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
    province: str | None = Query(None, max_length=120),
    amphoe: str | None = Query(None, max_length=120),
    tambon: str | None = Query(None, max_length=120),
    duration_days: int = Query(7, ge=1, le=14),
) -> JSONResponse:
    try:
        place = _choose_place(province, amphoe, tambon)
        data = await tmd_client.fetch_daily_by_place(place, duration_days=duration_days)
    except TmdApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse(content=data)


@app.get("/api/weather/raw")
async def api_weather_raw(
    province: str | None = Query(None, max_length=120),
    amphoe: str | None = Query(None, max_length=120),
    tambon: str | None = Query(None, max_length=120),
    duration_days: int = Query(7, ge=1, le=14),
) -> JSONResponse:
    try:
        place = _choose_place(province, amphoe, tambon)
        data = await tmd_client.fetch_daily_raw_by_place(place, duration_days=duration_days)
    except TmdApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse(content=data)


@app.get("/api/farm-summary")
async def api_farm_summary(
    province: str | None = Query(None, max_length=120),
    amphoe: str | None = Query(None, max_length=120),
    tambon: str | None = Query(None, max_length=120),
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
    province: str | None = Query(None, max_length=120),
    amphoe: str | None = Query(None, max_length=120),
    tambon: str | None = Query(None, max_length=120),
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


@app.get("/api/line/alert-status")
async def api_line_alert_status() -> JSONResponse:
    now = dt.datetime.now(dt.timezone.utc)
    _rollover_daily_counter(now)
    return JSONResponse(content=_line_alert_status_payload())


@app.post("/api/line/alert-toggle")
async def api_line_alert_toggle(enabled: bool | None = Query(None)) -> JSONResponse:
    global _line_alert_runtime_enabled

    if enabled is None:
        _line_alert_runtime_enabled = not _line_alert_runtime_enabled
    else:
        _line_alert_runtime_enabled = bool(enabled)

    if not _line_alert_runtime_enabled:
        _reset_line_alert_state()

    db.set_state(_LINE_ALERT_STATE_KEY, "1" if _line_alert_runtime_enabled else "0")

    return JSONResponse(content=_line_alert_status_payload())


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
