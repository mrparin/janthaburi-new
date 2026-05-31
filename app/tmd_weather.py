from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

import httpx


class TmdApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlaceQuery:
    province: str
    amphoe: str | None = None
    tambon: str | None = None


class TmdWeatherClient:
    def __init__(self, base_url: str, access_token: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token.strip()
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            raise TmdApiError("TMD access token is not configured")
        return {
            "accept": "application/json",
            "authorization": f"Bearer {self.access_token}",
        }

    @staticmethod
    def _clean_place_value(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _extract_locations(payload: dict[str, Any]) -> list[dict[str, Any]]:
        weather_forecast = payload.get("weather_forecast")
        if isinstance(weather_forecast, dict):
            locations = weather_forecast.get("locations")
            if isinstance(locations, list):
                return [x for x in locations if isinstance(x, dict)]

        # Real TMD payload uses the capitalized WeatherForecasts key.
        if isinstance(payload.get("WeatherForecasts"), list):
            return [x for x in payload["WeatherForecasts"] if isinstance(x, dict)]

        # Defensive fallback for older key shape found in docs.
        if isinstance(payload.get("WeatherForcasts"), list):
            return [x for x in payload["WeatherForcasts"] if isinstance(x, dict)]

        if isinstance(payload.get("weather_forecast"), list):
            return [x for x in payload["weather_forecast"] if isinstance(x, dict)]

        return []

    async def fetch_daily_by_place(
        self,
        query: PlaceQuery,
        duration_days: int = 7,
        date: dt.date | None = None,
    ) -> dict[str, Any]:
        province = self._clean_place_value(query.province)
        if not province:
            raise TmdApiError("province is required")

        amphoe = self._clean_place_value(query.amphoe)
        tambon = self._clean_place_value(query.tambon)

        # Try exact place first, then relax constraints to avoid hard failures:
        # tambon+amphoe+province -> amphoe+province -> province only.
        candidates: list[tuple[str | None, str | None]] = [(amphoe, tambon)]
        if tambon is not None:
            candidates.append((amphoe, None))
        if amphoe is not None:
            candidates.append((None, None))

        last_not_found: TmdApiError | None = None
        for idx, (a, t) in enumerate(candidates):
            try:
                data = await self._fetch_daily_once(
                    province=province,
                    amphoe=a,
                    tambon=t,
                    duration_days=duration_days,
                    date=date,
                )
                if data.get("days"):
                    return data

                # If no data and there is a broader candidate, keep trying.
                if idx < len(candidates) - 1:
                    continue
                return data
            except TmdApiError as exc:
                if str(exc) != "place not found in TMD":
                    raise
                last_not_found = exc
                if idx == len(candidates) - 1:
                    raise

        if last_not_found is not None:
            raise last_not_found
        raise TmdApiError("place not found in TMD")

    async def _fetch_daily_once(
        self,
        province: str,
        amphoe: str | None,
        tambon: str | None,
        duration_days: int,
        date: dt.date | None,
    ) -> dict[str, Any]:

        params: dict[str, Any] = {
            "province": province,
            "date": (date or dt.date.today()).isoformat(),
            "duration": max(1, min(14, int(duration_days))),
            "fields": "tc_min,tc_max,rh,rain,ws10m,cond",
        }
        if amphoe:
            params["amphoe"] = amphoe
        if tambon:
            params["tambon"] = tambon

        url = f"{self.base_url}/forecast/location/daily/place"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=self._headers())
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise TmdApiError("place not found in TMD") from exc
            raise TmdApiError(f"TMD API error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise TmdApiError(f"TMD API unavailable: {exc}") from exc

        locations = self._extract_locations(payload)
        if not locations:
            return {
                "source": "tmd",
                "location": None,
                "days": [],
            }

        first = locations[0]
        location = first.get("location") if isinstance(first.get("location"), dict) else {}
        forecasts = first.get("forecasts") if isinstance(first.get("forecasts"), list) else []

        days: list[dict[str, Any]] = []
        for item in forecasts:
            if not isinstance(item, dict):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            days.append(
                {
                    "time": item.get("time"),
                    "tc_min": data.get("tc_min"),
                    "tc_max": data.get("tc_max"),
                    "rh": data.get("rh"),
                    "rain": data.get("rain"),
                    "ws10m": data.get("ws10m"),
                    "cond": data.get("cond"),
                }
            )

        return {
            "source": "tmd",
            "location": {
                "province": location.get("province"),
                "amphoe": location.get("amphoe"),
                "tambon": location.get("tambon"),
                "lat": location.get("lat"),
                "lon": location.get("lon"),
                "region": location.get("region"),
                "areatype": location.get("areatype"),
            },
            "days": days,
        }
