import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv


sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test TMD daily forecast responses")
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        help="Forecast start date (YYYY-MM-DD). Repeat to test multiple dates.",
    )
    parser.add_argument("--province", default=os.getenv("TMD_PROVINCE", "จันทบุรี"))
    parser.add_argument("--amphoe", default=os.getenv("TMD_AMPHOE") or None)
    parser.add_argument("--tambon", default=os.getenv("TMD_TAMBON") or None)
    parser.add_argument("--duration", type=int, default=7)
    return parser.parse_args()


def default_dates() -> list[str]:
    today = dt.date.today()
    return [(today + dt.timedelta(days=offset)).isoformat() for offset in (-1, 0, 1)]


def extract_locations(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    forecasts = payload.get("WeatherForecasts")
    if isinstance(forecasts, list):
        return [item for item in forecasts if isinstance(item, dict)]

    forecasts = payload.get("weather_forecast")
    if isinstance(forecasts, dict) and isinstance(forecasts.get("locations"), list):
        return [item for item in forecasts["locations"] if isinstance(item, dict)]
    if isinstance(forecasts, list):
        return [item for item in forecasts if isinstance(item, dict)]
    return []


async def test_date(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    base_params: dict[str, Any],
    forecast_date: str,
) -> bool:
    params = {**base_params, "date": forecast_date}
    print(f"\n=== date={forecast_date} ===")

    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}")
        return False

    print(f"HTTP status: {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        print(f"Non-JSON response: {response.text[:500]}")
        return False

    if response.is_error:
        print("Error response:", json.dumps(payload, ensure_ascii=False)[:1000])
        return False

    locations = extract_locations(payload)
    forecast_counts = [
        len(item.get("forecasts", [])) if isinstance(item.get("forecasts"), list) else 0
        for item in locations
    ]
    total_forecasts = sum(forecast_counts)
    print(f"Locations: {len(locations)}")
    print(f"Forecast counts per location: {forecast_counts}")
    print(f"Total forecast items: {total_forecasts}")

    if total_forecasts:
        print("RESULT: TMD returned forecast data")
        first = locations[0]
        preview = {
            "location": first.get("location"),
            "first_forecast": first.get("forecasts", [None])[0],
        }
        print("Preview:", json.dumps(preview, ensure_ascii=False)[:1500])
        return True

    print("RESULT: TMD returned HTTP 200 but forecasts are empty")
    return False


async def main() -> int:
    args = parse_args()
    access_token = os.getenv("TMD_ACCESS_TOKEN")
    if not access_token:
        print("TMD_ACCESS_TOKEN is not configured in .env", file=sys.stderr)
        return 2

    base_url = os.getenv("TMD_BASE_URL", "https://data.tmd.go.th/nwpapi/v1").rstrip("/")
    url = f"{base_url}/forecast/location/daily/place"
    headers = {"accept": "application/json", "authorization": f"Bearer {access_token}"}
    params: dict[str, Any] = {
        "province": args.province,
        "duration": args.duration,
        "fields": "tc_min,tc_max,rh,rain,ws10m,cond",
    }
    if args.amphoe:
        params["amphoe"] = args.amphoe
    if args.tambon:
        params["tambon"] = args.tambon

    dates = args.dates or default_dates()
    print(f"Request URL: {url}")
    print(f"Place: province={args.province}, amphoe={args.amphoe}, tambon={args.tambon}")
    print(f"Dates: {', '.join(dates)}; duration={args.duration}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = [
            await test_date(client, url, headers, params, forecast_date)
            for forecast_date in dates
        ]

    print(f"\nSummary: {sum(results)}/{len(results)} date(s) returned forecast data")
    return 0 if any(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
