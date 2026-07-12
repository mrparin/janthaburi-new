import httpx
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

async def main():
    base_url = os.getenv("TMD_BASE_URL", "https://data.tmd.go.th/nwpapi/v1").rstrip("/")
    access_token = os.getenv("TMD_ACCESS_TOKEN")
    
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {access_token}",
    }
    
    params = {
        "province": os.getenv("TMD_PROVINCE", "จันทบุรี"),
        "amphoe": os.getenv("TMD_AMPHOE", "นายายอาม"),
        "tambon": os.getenv("TMD_TAMBON", "วังโตนด"),
        "duration": 7,
        "fields": "tc_min,tc_max,rh,rain,ws10m,cond",
    }
    
    url = f"{base_url}/forecast/location/daily/place"
    
    print(f"Requesting URL: {url}")
    print("Params printed locally, skipping print to avoid encoding errors")
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, params=params, headers=headers)
            print(f"Status Code: {response.status_code}")
            try:
                data = response.json()
                print("Response JSON keys:", list(data.keys()) if isinstance(data, dict) else type(data))
                if isinstance(data, dict):
                    print("WeatherForecasts present:", "WeatherForecasts" in data)
                    print("weather_forecast present:", "weather_forecast" in data)
                    
                    forecast = data.get("weather_forecast") or data.get("WeatherForecasts")
                    if forecast:
                        print("Forecast type:", type(forecast))
                        if isinstance(forecast, list):
                            print("Forecast items:", len(forecast))
                            if len(forecast) > 0:
                                print("First location keys:", list(forecast[0].keys()))
                        elif isinstance(forecast, dict):
                            print("Forecast location keys:", list(forecast.get("location", {}).keys()) if "location" in forecast else "no location")
                            locs = forecast.get("locations")
                            if isinstance(locs, list):
                                print("Locations in dict:", len(locs))
                                if len(locs) > 0:
                                    print("First location from locations:", list(locs[0].keys()))
                                    
                import json
                print("Raw Response preview:", json.dumps(data, ensure_ascii=False)[:500])
            except Exception as e:
                print("Failed to parse JSON:", str(e))
                print("Raw text:", response.text[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
