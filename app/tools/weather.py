import logging

import httpx

from app.config import settings
from app.tools import register_tool
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)

OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherTool(Tool):
    name = "weather"
    description = (
        "Get the current weather for any city. Returns temperature, conditions, "
        "humidity, and wind speed. Use this when the user asks about weather "
        "in a specific location."
    )
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, optionally with country code (e.g. 'London' or 'Paris,FR').",
            },
        },
        "required": ["city"],
    }

    async def execute(self, ctx: ToolContext, args: dict) -> str:
        city = args["city"].strip()
        logger.info(f"Weather lookup: {city}")

        if not settings.openweathermap_api_key:
            return "Error: Weather tool is not configured (missing OPENWEATHERMAP_API_KEY)."

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                OWM_URL,
                params={
                    "q": city,
                    "appid": settings.openweathermap_api_key,
                    "units": "metric",
                },
            )

        if response.status_code == 404:
            return f"City not found: {city}"
        response.raise_for_status()

        data = response.json()
        name = data.get("name", city)
        country = data.get("sys", {}).get("country", "")
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"].capitalize()
        wind_speed = data["wind"]["speed"]

        return (
            f"Weather in {name}{', ' + country if country else ''}:\n"
            f"  {description}\n"
            f"  Temperature: {temp:.1f}°C (feels like {feels_like:.1f}°C)\n"
            f"  Humidity: {humidity}%\n"
            f"  Wind: {wind_speed} m/s"
        )


register_tool(WeatherTool())
