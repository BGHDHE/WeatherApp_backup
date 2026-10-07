import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.schemas import DailyResponse, Location, LocationDaily, Region, RegionDaily
from app.services.forecast import OPEN_METEO_URL, TIMEZONE, WeatherProviderError, frost_level
from app.services.locations import LOCATIONS, REGIONS

CACHE_SECONDS = 15 * 60
RAIN_HOUR_MM = 0.1
RAIN_HOUR_PROB = 50
COMPASS = ["É", "ÉK", "K", "DK", "D", "DNy", "Ny", "ÉNy"]

HOURLY_VARS = (
    "temperature_2m,precipitation,precipitation_probability,wind_speed_10m,"
    "wind_gusts_10m,wind_direction_10m,soil_temperature_6cm,"
    "soil_moisture_0_to_7cm,et0_fao_evapotranspiration"
)


@dataclass(frozen=True)
class Hour:
    ts: datetime
    temp: float | None
    precip: float | None
    prob: float | None
    wind: float | None
    gust: float | None
    direction: float | None
    soil_temp: float | None
    soil_moisture: float | None
    et0: float | None


def _num(values: Any, index: int) -> float | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherProviderError("Invalid numeric value in Open-Meteo response")
    return float(value)


def parse_hours(payload: dict[str, Any]) -> tuple[datetime, list[Hour]]:
    hourly = payload.get("hourly")
    current = payload.get("current")
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        raise WeatherProviderError("Missing hourly data in Open-Meteo response")
    if not isinstance(current, dict):
        raise WeatherProviderError("Missing current time in Open-Meteo response")
    try:
        now = datetime.fromisoformat(current["time"])
        hours = [
            Hour(
                ts=datetime.fromisoformat(raw),
                temp=_num(hourly.get("temperature_2m"), i),
                precip=_num(hourly.get("precipitation"), i),
                prob=_num(hourly.get("precipitation_probability"), i),
                wind=_num(hourly.get("wind_speed_10m"), i),
                gust=_num(hourly.get("wind_gusts_10m"), i),
                direction=_num(hourly.get("wind_direction_10m"), i),
                soil_temp=_num(hourly.get("soil_temperature_6cm"), i),
                soil_moisture=_num(hourly.get("soil_moisture_0_to_7cm"), i),
                et0=_num(hourly.get("et0_fao_evapotranspiration"), i),
            )
            for i, raw in enumerate(hourly["time"])
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherProviderError("Invalid time in Open-Meteo response") from exc
    return now, hours


def _present(values) -> list[float]:
    return [v for v in values if v is not None]


def _min(values) -> float | None:
    present = _present(values)
    return min(present) if present else None


def _max(values) -> float | None:
    present = _present(values)
    return max(present) if present else None


def _sum(values) -> float | None:
    present = _present(values)
    return sum(present) if present else None


def _avg(values) -> float | None:
    present = _present(values)
    return sum(present) / len(present) if present else None


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    return COMPASS[int((degrees % 360) / 45 + 0.5) % 8]


def _rain_window(hours: list[Hour]) -> tuple[str | None, int | None]:
    wet = [
        h
        for h in hours
        if (h.precip or 0) >= RAIN_HOUR_MM or (h.prob or 0) >= RAIN_HOUR_PROB
    ]
    probs = _present(h.prob for h in hours)
    prob_max = round(max(probs)) if probs else None
    if not wet:
        return None, prob_max
    start, end = wet[0].ts, wet[-1].ts + timedelta(hours=1)
    end_label = "24:00" if end.date() != start.date() else end.strftime("%H:%M")
    return f"{start:%H:%M}-{end_label}", prob_max


def build_location_daily(location: Location, now: datetime, hours: list[Hour]) -> LocationDaily:
    today = [h for h in hours if h.ts.date() == now.date()]
    past = [h for h in hours if now - timedelta(hours=24) < h.ts <= now]
    if not today:
        raise WeatherProviderError("No hourly data for today")

    gust_hour = None
    gusts = [h for h in today if h.gust is not None]
    if gusts:
        gust_hour = max(gusts, key=lambda h: h.gust)
    wind_hour = None
    winds = [h for h in today if h.wind is not None]
    if winds:
        wind_hour = max(winds, key=lambda h: h.wind)

    window, prob_max = _rain_window(today)
    today_min = _min(h.temp for h in today)
    moisture = _avg(h.soil_moisture for h in today)
    return LocationDaily(
        name=location.name,
        slug=location.slug,
        past_temp_min_c=_r(_min(h.temp for h in past)),
        past_temp_max_c=_r(_max(h.temp for h in past)),
        past_precip_mm=_r(_sum(h.precip for h in past)),
        past_gust_max_ms=_r(_max(h.gust for h in past)),
        today_temp_min_c=_r(today_min),
        today_temp_max_c=_r(_max(h.temp for h in today)),
        precip_today_mm=_r(_sum(h.precip for h in today)),
        precip_window=window,
        precip_probability_max=prob_max,
        wind_max_ms=wind_hour.wind if wind_hour else None,
        wind_direction=compass(wind_hour.direction) if wind_hour else None,
        gust_max_ms=gust_hour.gust if gust_hour else None,
        gust_time=f"{gust_hour.ts:%H:%M}" if gust_hour else None,
        frost_level=frost_level(today_min),
        frost_min_temp_c=_r(today_min),
        soil_temperature_c=_r(_avg(h.soil_temp for h in today)),
        soil_moisture_percent=_r(moisture * 100) if moisture is not None else None,
        evapotranspiration_mm=_r(_sum(h.et0 for h in today)),
    )


def build_daily(
    data: dict[str, tuple[datetime, list[Hour]]],
    fetched_at: datetime,
    regions: list[Region] = REGIONS,
    locations: list[Location] = LOCATIONS,
) -> DailyResponse:
    by_slug = {location.slug: location for location in locations}
    region_items = []
    for region in regions:
        items = [
            build_location_daily(by_slug[slug], *data[slug])
            for slug in region.location_slugs
            if slug in data
        ]
        if not items:
            raise WeatherProviderError("No forecast data for a region")
        region_items.append(RegionDaily(name=region.name, slug=region.slug, locations=items))
    now = next(iter(data.values()))[0]
    return DailyResponse(
        provider="open-meteo",
        source_type="forecast",
        fetched_at=fetched_at,
        timezone=TIMEZONE,
        date=now.date(),
        as_of=now,
        regions=region_items,
    )


_cache: tuple[float, DailyResponse] | None = None


async def fetch_daily() -> DailyResponse:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    params = {
        "latitude": ",".join(str(l.latitude) for l in LOCATIONS),
        "longitude": ",".join(str(l.longitude) for l in LOCATIONS),
        "hourly": HOURLY_VARS,
        "current": "temperature_2m",
        "wind_speed_unit": "ms",
        "timezone": TIMEZONE,
        "past_days": 1,
        "forecast_days": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherProviderError("Open-Meteo request or response failed") from exc

    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(LOCATIONS) or not all(isinstance(i, dict) for i in items):
        raise WeatherProviderError("Unexpected Open-Meteo multi-location response")

    data = {l.slug: parse_hours(item) for l, item in zip(LOCATIONS, items)}
    result = build_daily(data, datetime.now(timezone.utc))
    _cache = (time.monotonic(), result)
    return result