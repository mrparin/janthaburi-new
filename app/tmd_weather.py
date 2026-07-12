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

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            # Some providers may return numeric values as strings.
            try:
                return float(text.replace(",", ""))
            except ValueError:
                return None
        return None

    @classmethod
    def _pick_first_float(cls, data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = cls._to_float(data.get(key))
            if value is not None:
                return value
        return None

    @staticmethod
    def _scope_of(amphoe: str | None, tambon: str | None) -> str:
        if tambon:
            return "tambon"
        if amphoe:
            return "amphoe"
        return "province"

    @staticmethod
    def _build_params(
        *,
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
        return params

    async def _request_daily_payload(self, params: dict[str, Any]) -> dict[str, Any]:
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
        return payload

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
        requested_scope = self._scope_of(amphoe, tambon)

        # Try exact place first, then relax constraints to avoid hard failures:
        # tambon+amphoe+province -> amphoe+province -> province only.
        candidates: list[tuple[str | None, str | None]] = [(amphoe, tambon)]
        if tambon is not None:
            candidates.append((amphoe, None))
        if amphoe is not None:
            candidates.append((None, None))

        last_not_found: TmdApiError | None = None
        best_location: dict[str, Any] | None = None
        for idx, (a, t) in enumerate(candidates):
            try:
                data = await self._fetch_daily_once(
                    province=province,
                    amphoe=a,
                    tambon=t,
                    duration_days=duration_days,
                    date=date,
                )
                used_scope = self._scope_of(a, t)
                data["query_meta"] = {
                    "requested": {
                        "province": province,
                        "amphoe": amphoe,
                        "tambon": tambon,
                        "scope": requested_scope,
                    },
                    "used": {
                        "province": province,
                        "amphoe": a,
                        "tambon": t,
                        "scope": used_scope,
                    },
                    "fallback_used": idx > 0 or used_scope != requested_scope,
                }
                if best_location is None and isinstance(data.get("location"), dict):
                    best_location = data["location"]
                if data.get("days"):
                    return data

                # If no data and there is a broader candidate, keep trying.
                if idx < len(candidates) - 1:
                    continue
                if best_location is not None:
                    data["location"] = best_location
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

    async def fetch_daily_raw_by_place(
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
        requested_scope = self._scope_of(amphoe, tambon)

        candidates: list[tuple[str | None, str | None]] = [(amphoe, tambon)]
        if tambon is not None:
            candidates.append((amphoe, None))
        if amphoe is not None:
            candidates.append((None, None))

        last_not_found: TmdApiError | None = None
        for idx, (a, t) in enumerate(candidates):
            try:
                params = self._build_params(
                    province=province,
                    amphoe=a,
                    tambon=t,
                    duration_days=duration_days,
                    date=date,
                )
                payload = await self._request_daily_payload(params)
                locations = self._extract_locations(payload)
                used_scope = self._scope_of(a, t)
                first_location = locations[0].get("location") if locations else None
                resolved_location = first_location if isinstance(first_location, dict) else None
                fallback_used = idx > 0 or used_scope != requested_scope

                fallback_note = (
                    f"fallback to {used_scope} scope"
                    if fallback_used
                    else "exact requested scope"
                )

                result = {
                    "source": "tmd_raw",
                    "raw_payload": payload,
                    "resolved_location": {
                        "province": resolved_location.get("province") if resolved_location else None,
                        "amphoe": resolved_location.get("amphoe") if resolved_location else None,
                        "tambon": resolved_location.get("tambon") if resolved_location else None,
                        "name": resolved_location.get("name") if resolved_location else None,
                        "areatype": resolved_location.get("areatype") if resolved_location else None,
                        "lat": resolved_location.get("lat") if resolved_location else None,
                        "lon": resolved_location.get("lon") if resolved_location else None,
                    },
                    "query_meta": {
                        "requested": {
                            "province": province,
                            "amphoe": amphoe,
                            "tambon": tambon,
                            "scope": requested_scope,
                        },
                        "used": {
                            "province": province,
                            "amphoe": a,
                            "tambon": t,
                            "scope": used_scope,
                        },
                        "fallback_used": fallback_used,
                        "note": fallback_note,
                    },
                    "request_params": params,
                    "has_locations": bool(locations),
                }

                if locations or idx == len(candidates) - 1:
                    return result
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
        params = self._build_params(
            province=province,
            amphoe=amphoe,
            tambon=tambon,
            duration_days=duration_days,
            date=date,
        )
        payload = await self._request_daily_payload(params)

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
            rain_raw = self._pick_first_float(data, ("rain", "rainfall", "rain_24h"))
            rain_mm = self._pick_first_float(data, ("rain_mm", "rainfall", "rain_24h"))
            rain_pct = self._pick_first_float(data, ("rain_pct", "rain_chance", "rain_prob", "pop"))

            # In this dashboard, treat raw rain as rainfall amount (mm) when rain_mm is absent.
            if rain_mm is None and rain_raw is not None:
                rain_mm = rain_raw

            days.append(
                {
                    "time": item.get("time"),
                    "tc_min": data.get("tc_min"),
                    "tc_max": data.get("tc_max"),
                    "rh": data.get("rh"),
                    "rain": rain_raw,
                    "rain_mm": rain_mm,
                    "rain_pct": rain_pct,
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
