import asyncio
import os
from dotenv import load_dotenv

from app.tmd_weather import TmdWeatherClient, PlaceQuery
from app.openweather import OpenWeatherClient
from app.weather_provider import WeatherProvider

load_dotenv()

async def main():
    tmd_client = TmdWeatherClient(
        os.getenv("TMD_BASE_URL", "https://data.tmd.go.th/nwpapi/v1"),
        os.getenv("TMD_ACCESS_TOKEN", "")
    )
    openweather_client = OpenWeatherClient(
        os.getenv("OPENWEATHER_BASE_URL", "https://api.openweathermap.org"),
        os.getenv("OPENWEATHER_API_KEY", "")
    )
    
    provider = WeatherProvider(
        tmd_client,
        openweather_client,
        fallback_enabled=True
    )
    
    query = PlaceQuery(
        province=os.getenv("TMD_PROVINCE", "จันทบุรี"),
        amphoe=os.getenv("TMD_AMPHOE", "นายายอาม"),
        tambon=os.getenv("TMD_TAMBON", "วังโตนด"),
    )
    
    print("Fetching weather...")
    result = await provider.fetch_daily_by_place(query)
    
    print(f"Source: {result.get('source')}")
    print(f"Days count: {len(result.get('days', []))}")
    if "query_meta" in result:
        print(f"Meta: {result['query_meta']}")
        
if __name__ == "__main__":
    asyncio.run(main())
