import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas import ForecastDay, ForecastResponse, Location
from app.services import thresholds

logger = logging.getLogger(__name__)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Europe/Budapest"


class WeatherProviderError(Exception):
    pass


def frost_level(minimum_temperature: float | None) -> str:
    if minimum_temperature is None:
        return "nincs adat"
    if minimum_temperature <= thresholds.get("frost.high_c"):
        return "magas"
    if minimum_temperature <= thresholds.get("frost.moderate_c"):
        return "mérsékelt"
    if minimum_temperature <= thresholds.get("frost.low_c"):
        return "alacsony"
    return "nincs"


def _number(values: Any, index: int) -> float | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherProviderError("Invalid numeric value in Open-Meteo response")
    return float(value)


def _daily_average(
    hourly: dict[str, Any], variable: str, day: str
) -> float | None:
    times = hourly.get("time")
    values = hourly.get(variable)
    if not isinstance(times, list) or not isinstance(values, list):
        return None

    matching = [
        value
        for timestamp, value in zip(times, values)
        if isinstance(timestamp, str) and timestamp.startswith(day)
    ]
    numeric_values = [
        value
        for value in matching
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def normalize_forecast(
    location: Location,
    payload: dict[str, Any],
    fetched_at: datetime | None = None,
) -> ForecastResponse:
    daily = payload.get("daily")
    hourly = payload.get("hourly", {})
    if not isinstance(daily, dict) or not isinstance(hourly, dict):
        raise WeatherProviderError("Missing daily/hourly data in Open-Meteo response")

    dates = daily.get("time")
    if not isinstance(dates, list) or not dates:
        raise WeatherProviderError("Missing forecast dates in Open-Meteo response")
    if not isinstance(payload.get("timezone", TIMEZONE), str):
        raise WeatherProviderError("Invalid timezone in Open-Meteo response")

    required_variables = (
        "temperature_2m_min",
        "temperature_2m_max",
        "precipitation_sum",
        "wind_speed_10m_max",
    )
    if any(not isinstance(daily.get(variable), list) for variable in required_variables):
        raise WeatherProviderError("Incomplete daily data in Open-Meteo response")

    days: list[ForecastDay] = []
    for index, day in enumerate(dates):
        if not isinstance(day, str):
            raise WeatherProviderError("Invalid forecast date in Open-Meteo response")

        minimum = _number(daily["temperature_2m_min"], index)
        soil_temperature = _daily_average(hourly, "soil_temperature_6cm", day)
        soil_moisture = _daily_average(hourly, "soil_moisture_0_to_7cm", day)
        days.append(
            ForecastDay(
                date=day,
                temp_min_c=minimum,
                temp_max_c=_number(daily["temperature_2m_max"], index),
                precipitation_mm=_number(daily["precipitation_sum"], index),
                wind_max_ms=_number(daily["wind_speed_10m_max"], index),
                frost_level=frost_level(minimum),
                frost_min_temp_c=minimum,
                soil_temperature_c=soil_temperature,
                soil_moisture_percent=(
                    soil_moisture * 100 if soil_moisture is not None else None
                ),
                evapotranspiration_mm=_number(
                    daily.get("et0_fao_evapotranspiration"), index
                ),
            )
        )

    return ForecastResponse(
        location=location,
        provider="open-meteo",
        source_type="forecast",
        fetched_at=fetched_at or datetime.now(timezone.utc),
        timezone=payload.get("timezone", TIMEZONE),
        days=days,
    )


async def fetch_forecast(location: Location, days: int = 4) -> ForecastResponse:
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "hourly": "soil_temperature_6cm,soil_moisture_0_to_7cm",
        "daily": (
            "temperature_2m_min,temperature_2m_max,precipitation_sum,"
            "wind_speed_10m_max,et0_fao_evapotranspiration"
        ),
        "wind_speed_unit": "ms",
        "timezone": TIMEZONE,
        "forecast_days": days,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherProviderError("Open-Meteo request or response failed") from exc

    if not isinstance(payload, dict):
        raise WeatherProviderError("Invalid Open-Meteo response")
    try:
        return normalize_forecast(location, payload)
    except WeatherProviderError:
        logger.exception("Could not normalize Open-Meteo forecast")
        raise
