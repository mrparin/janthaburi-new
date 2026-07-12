from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Any

from app.openweather import OpenWeatherApiError, OpenWeatherClient
from app.tmd_weather import PlaceQuery, TmdApiError, TmdWeatherClient


logger = logging.getLogger(__name__)


class WeatherProvider:
    def __init__(
        self,
        tmd_client: TmdWeatherClient,
        openweather_client: OpenWeatherClient,
        fallback_enabled: bool,
        cache_seconds: int = 600,
    ) -> None:
        self.tmd_client = tmd_client
        self.openweather_client = openweather_client
        self.fallback_enabled = fallback_enabled
        self.cache_seconds = max(0, cache_seconds)
        self._fallback_cache: dict[tuple[str, str | None, str | None, int], tuple[float, dict[str, Any]]] = {}
        self._fallback_lock = asyncio.Lock()

    def _cache_key(
        self, query: PlaceQuery, duration_days: int
    ) -> tuple[str, str | None, str | None, int]:
        return (query.province, query.amphoe, query.tambon, duration_days)

    def _get_cached_fallback(
        self, key: tuple[str, str | None, str | None, int]
    ) -> dict[str, Any] | None:
        cached = self._fallback_cache.get(key)
        if cached is None:
            return None
        expires_at, data = cached
        if time.monotonic() >= expires_at:
            self._fallback_cache.pop(key, None)
            return None
        result = copy.deepcopy(data)
        result["query_meta"]["cache_hit"] = True
        return result

    async def fetch_daily_by_place(
        self, query: PlaceQuery, duration_days: int = 7
    ) -> dict[str, Any]:
        tmd_data: dict[str, Any] | None = None
        tmd_error: TmdApiError | None = None
        try:
            tmd_data = await self.tmd_client.fetch_daily_by_place(query, duration_days)
            if tmd_data.get("days"):
                return tmd_data
        except TmdApiError as exc:
            tmd_error = exc

        if not self.fallback_enabled:
            if tmd_error:
                raise tmd_error
            return tmd_data or {"source": "tmd", "location": None, "days": []}

        fallback_reason = (
            f"tmd_error:{tmd_error}" if tmd_error else "tmd_empty_forecast"
        )
        location = tmd_data.get("location") if isinstance(tmd_data, dict) else None
        lat = location.get("lat") if isinstance(location, dict) else None
        lon = location.get("lon") if isinstance(location, dict) else None
        key = self._cache_key(query, duration_days)
        cached = self._get_cached_fallback(key)
        if cached is not None:
            return cached
        try:
            async with self._fallback_lock:
                cached = self._get_cached_fallback(key)
                if cached is not None:
                    return cached
                logger.warning("Using OpenWeather fallback: %s", fallback_reason)
                data = await self.openweather_client.fetch_daily(
                    query,
                    duration_days,
                    lat=lat,
                    lon=lon,
                    fallback_reason=fallback_reason,
                )
                data["query_meta"]["cache_hit"] = False
                if self.cache_seconds:
                    self._fallback_cache[key] = (
                        time.monotonic() + self.cache_seconds,
                        copy.deepcopy(data),
                    )
                return data
        except OpenWeatherApiError as exc:
            if tmd_error:
                raise TmdApiError(f"{tmd_error}; fallback failed: {exc}") from exc
            raise TmdApiError(f"TMD returned no forecast; fallback failed: {exc}") from exc
