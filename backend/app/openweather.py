from __future__ import annotations

import datetime as dt
from typing import Any

import httpx

from app.tmd_weather import PlaceQuery


class OpenWeatherApiError(RuntimeError):
    pass


class OpenWeatherClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _require_key(self) -> None:
        if not self.api_key:
            raise OpenWeatherApiError("OpenWeather API key is not configured")

    async def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        self._require_key()
        params = {**params, "appid": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}{path}", params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise OpenWeatherApiError(
                f"OpenWeather API error: {exc.response.status_code}"
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise OpenWeatherApiError(f"OpenWeather API unavailable: {exc}") from exc

    async def geocode(self, query: PlaceQuery) -> tuple[float, float]:
        parts = [query.tambon, query.amphoe, query.province, "TH"]
        place_text = ",".join(part for part in parts if part)
        try:
            payload = await self._get_json(
                "/geo/1.0/direct", {"q": place_text, "limit": 1}
            )
        except OpenWeatherApiError as exc:
            if "error: 404" in str(exc):
                payload = []
            else:
                raise
                
        if not isinstance(payload, list) or not payload:
            # Thai subdistrict names are not always indexed; retry at province level.
            try:
                payload = await self._get_json(
                    "/geo/1.0/direct", {"q": f"{query.province},TH", "limit": 1}
                )
            except OpenWeatherApiError as exc:
                if "error: 404" in str(exc):
                    payload = []
                else:
                    raise
                    
        if not isinstance(payload, list) or not payload:
            raise OpenWeatherApiError("place not found in OpenWeather")
        first = payload[0]
        try:
            return float(first["lat"]), float(first["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OpenWeatherApiError("invalid OpenWeather geocoding response") from exc

    @staticmethod
    def _condition_code(weather_id: Any) -> int | None:
        try:
            code = int(weather_id)
        except (TypeError, ValueError):
            return None
        if 200 <= code < 300:
            return 7  # thunderstorm
        if 300 <= code < 400:
            return 5  # drizzle
        if 500 <= code < 600:
            return 9 if code >= 502 else 8  # heavy/general rain
        if 600 <= code < 700:
            return 6  # snow/overcast (closest TMD display category)
        if 700 <= code < 800:
            return 3  # mist/atmosphere
        if code == 800:
            return 1  # clear
        if code == 801:
            return 2  # partly cloudy
        if 802 <= code <= 804:
            return 3  # cloudy
        return None

    async def fetch_daily(
        self,
        query: PlaceQuery,
        duration_days: int,
        *,
        lat: float | None = None,
        lon: float | None = None,
        fallback_reason: str,
    ) -> dict[str, Any]:
        if lat is None or lon is None:
            lat, lon = await self.geocode(query)

        payload = await self._get_json(
            "/data/3.0/onecall",
            {
                "lat": lat,
                "lon": lon,
                "exclude": "current,minutely,hourly,alerts",
                "units": "metric",
                "lang": "th",
            },
        )
        daily = payload.get("daily") if isinstance(payload, dict) else None
        if not isinstance(daily, list) or not daily:
            raise OpenWeatherApiError("OpenWeather returned no daily forecast")

        days: list[dict[str, Any]] = []
        limit = max(1, min(8, int(duration_days)))
        for item in daily[:limit]:
            if not isinstance(item, dict):
                continue
            temp = item.get("temp") if isinstance(item.get("temp"), dict) else {}
            weather = item.get("weather") if isinstance(item.get("weather"), list) else []
            weather_id = weather[0].get("id") if weather and isinstance(weather[0], dict) else None
            timestamp = item.get("dt")
            time_value = None
            if isinstance(timestamp, (int, float)):
                time_value = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat()
            pop = item.get("pop")
            rain_pct = float(pop) * 100 if isinstance(pop, (int, float)) else None
            rain_mm = item.get("rain") if isinstance(item.get("rain"), (int, float)) else None
            days.append(
                {
                    "time": time_value,
                    "tc_min": temp.get("min"),
                    "tc_max": temp.get("max"),
                    "rh": item.get("humidity"),
                    "rain": rain_mm,
                    "rain_mm": rain_mm,
                    "rain_pct": rain_pct,
                    "ws10m": item.get("wind_speed"),
                    "cond": self._condition_code(weather_id),
                }
            )

        return {
            "source": "openweather",
            "location": {
                "province": query.province,
                "amphoe": query.amphoe,
                "tambon": query.tambon,
                "lat": lat,
                "lon": lon,
                "region": None,
                "areatype": "tambon" if query.tambon else "amphoe" if query.amphoe else "province",
            },
            "days": days,
            "query_meta": {
                "requested": {
                    "province": query.province,
                    "amphoe": query.amphoe,
                    "tambon": query.tambon,
                    "scope": "tambon" if query.tambon else "amphoe" if query.amphoe else "province",
                },
                "used": {"provider": "openweather", "lat": lat, "lon": lon},
                "fallback_used": True,
                "fallback_reason": fallback_reason,
            },
        }
