from __future__ import annotations

import unittest

from app.openweather import OpenWeatherClient
from app.tmd_weather import PlaceQuery, TmdApiError
from app.weather_provider import WeatherProvider


PLACE = PlaceQuery("จันทบุรี", "นายายอาม", "วังโตนด")


class FakeTmdClient:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def fetch_daily_by_place(self, query, duration_days):
        if self.error:
            raise self.error
        return self.result


class FakeOpenWeatherClient:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch_daily(self, query, duration_days, **kwargs):
        self.calls += 1
        return {
            "source": "openweather",
            "location": {"lat": kwargs.get("lat"), "lon": kwargs.get("lon")},
            "days": [{"time": "2026-07-12T00:00:00+00:00"}],
            "query_meta": {
                "fallback_used": True,
                "fallback_reason": kwargs.get("fallback_reason"),
                "used": {"provider": "openweather"},
            },
        }


class WeatherProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_tmd_when_forecast_exists(self):
        tmd = FakeTmdClient({"source": "tmd", "days": [{"time": "today"}]})
        openweather = FakeOpenWeatherClient()
        provider = WeatherProvider(tmd, openweather, True)

        result = await provider.fetch_daily_by_place(PLACE, 7)

        self.assertEqual("tmd", result["source"])
        self.assertEqual(0, openweather.calls)

    async def test_falls_back_when_tmd_is_empty_and_reuses_cache(self):
        tmd = FakeTmdClient(
            {"source": "tmd", "location": {"lat": 12.7, "lon": 101.9}, "days": []}
        )
        openweather = FakeOpenWeatherClient()
        provider = WeatherProvider(tmd, openweather, True, cache_seconds=600)

        first = await provider.fetch_daily_by_place(PLACE, 7)
        second = await provider.fetch_daily_by_place(PLACE, 7)

        self.assertEqual("openweather", first["source"])
        self.assertFalse(first["query_meta"]["cache_hit"])
        self.assertTrue(second["query_meta"]["cache_hit"])
        self.assertEqual(1, openweather.calls)

    async def test_falls_back_when_tmd_raises(self):
        tmd = FakeTmdClient(error=TmdApiError("TMD API unavailable"))
        openweather = FakeOpenWeatherClient()
        provider = WeatherProvider(tmd, openweather, True)

        result = await provider.fetch_daily_by_place(PLACE, 7)

        self.assertEqual("openweather", result["source"])
        self.assertIn("tmd_error", result["query_meta"]["fallback_reason"])


class OpenWeatherMappingTests(unittest.TestCase):
    def test_maps_openweather_condition_ids_to_tmd_categories(self):
        self.assertEqual(7, OpenWeatherClient._condition_code(211))
        self.assertEqual(8, OpenWeatherClient._condition_code(500))
        self.assertEqual(9, OpenWeatherClient._condition_code(502))
        self.assertEqual(1, OpenWeatherClient._condition_code(800))
        self.assertEqual(3, OpenWeatherClient._condition_code(804))


if __name__ == "__main__":
    unittest.main()
