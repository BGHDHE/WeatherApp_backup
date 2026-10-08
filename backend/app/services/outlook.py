import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

import httpx

from app.schemas import (
    Location,
    OutlookAlert,
    OutlookDay,
    OutlookResponse,
    Region,
    RegionOutlook,
)
from app.services import thresholds
from app.services.forecast import OPEN_METEO_URL, TIMEZONE, WeatherProviderError
from app.services.locations import LOCATIONS, REGIONS

logger = logging.getLogger(__name__)

# Kezdeti küszöbök; éles használat előtt agronómussal jóváhagyandók.
HEAVY_RAIN_MM = thresholds.get("outlook.heavy_rain_mm")
STRONG_GUST_MS = thresholds.get("outlook.strong_gust_ms")
FROST_C = thresholds.get("outlook.frost_c")
HEAT_C = thresholds.get("outlook.heat_c")
WET_DAY_MM = thresholds.get("outlook.wet_day_mm")
CACHE_SECONDS = 30 * 60

WEEKDAYS_ON = ["hétfőn", "kedden", "szerdán", "csütörtökön", "pénteken", "szombaton", "vasárnap"]
KIND_ORDER = {"zivatar": 0, "csapadék": 1, "szél": 2, "fagy": 3, "hőség": 4}


@dataclass(frozen=True)
class DayData:
    date: date
    temp_min: float | None
    temp_max: float | None
    precip: float | None
    gust: float | None
    weather_code: int | None


def _value(values: Any, index: int) -> float | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherProviderError("Invalid numeric value in Open-Meteo response")
    return float(value)


def parse_days(payload: dict[str, Any]) -> list[DayData]:
    daily = payload.get("daily")
    if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
        raise WeatherProviderError("Missing daily data in Open-Meteo response")
    days = []
    for index, raw_date in enumerate(daily["time"]):
        try:
            day = date.fromisoformat(raw_date)
        except (TypeError, ValueError) as exc:
            raise WeatherProviderError("Invalid forecast date") from exc
        code = _value(daily.get("weather_code"), index)
        days.append(
            DayData(
                date=day,
                temp_min=_value(daily.get("temperature_2m_min"), index),
                temp_max=_value(daily.get("temperature_2m_max"), index),
                precip=_value(daily.get("precipitation_sum"), index),
                gust=_value(daily.get("wind_gusts_10m_max"), index),
                weather_code=int(code) if code is not None else None,
            )
        )
    return days


def _when(day: date, today: date) -> str:
    offset = (day - today).days
    if offset == 0:
        return "ma"
    if offset == 1:
        return "holnap"
    return WEEKDAYS_ON[day.weekday()]


def _is_storm(day: DayData) -> bool:
    return day.weather_code is not None and day.weather_code >= 95


def _alert_kinds(day: DayData) -> list[tuple[str, float | None]]:
    kinds: list[tuple[str, float | None]] = []
    if _is_storm(day):
        kinds.append(("zivatar", day.precip))
    elif day.precip is not None and day.precip >= HEAVY_RAIN_MM:
        kinds.append(("csapadék", day.precip))
    if day.gust is not None and day.gust >= STRONG_GUST_MS:
        kinds.append(("szél", day.gust))
    if day.temp_min is not None and day.temp_min <= FROST_C:
        kinds.append(("fagy", day.temp_min))
    if day.temp_max is not None and day.temp_max >= HEAT_C:
        kinds.append(("hőség", day.temp_max))
    return kinds


def _alert_message(kind: str, names: list[str], when: str, value: float | None) -> str:
    who = ", ".join(names)
    number = round(value) if value is not None else None
    if kind == "zivatar":
        rain = f", legfeljebb {number} mm esővel" if value is not None and value >= 1 else ""
        return f"{who}: {when} zivatar várható{rain}."
    if kind == "csapadék":
        return f"{who}: {when} csapadék várható, legfeljebb {number} mm."
    if kind == "szél":
        return f"{who}: {when} erős szél, széllökés legfeljebb {number} m/s."
    if kind == "fagy":
        label = "fagy" if value is not None and value <= 0 else "fagyveszély"
        return f"{who}: {when} {label}, a minimum akár {number} °C."
    return f"{who}: {when} hőség, a maximum akár {number} °C."


def build_alerts(
    days_by_location: dict[str, list[DayData]], today: date
) -> list[OutlookAlert]:
    grouped: dict[tuple[date, str], dict[str, Any]] = {}
    for name, days in days_by_location.items():
        for day in days:
            for kind, value in _alert_kinds(day):
                entry = grouped.setdefault((day.date, kind), {"names": [], "value": None})
                entry["names"].append(name)
                if value is None:
                    continue
                current = entry["value"]
                if current is None:
                    entry["value"] = value
                elif kind == "fagy":
                    entry["value"] = min(current, value)
                else:
                    entry["value"] = max(current, value)

    alerts = []
    for (day, kind), entry in sorted(
        grouped.items(), key=lambda item: (item[0][0], KIND_ORDER[item[0][1]])
    ):
        alerts.append(
            OutlookAlert(
                date=day,
                kind=kind,
                locations=entry["names"],
                message=_alert_message(kind, entry["names"], _when(day, today), entry["value"]),
            )
        )
    return alerts


def _aggregate(
    values: list[float | None], pick: Callable[[list[float]], float]
) -> float | None:
    present = [v for v in values if v is not None]
    return pick(present) if present else None


def aggregate_days(days_by_location: dict[str, list[DayData]]) -> list[OutlookDay]:
    dates = sorted({d.date for days in days_by_location.values() for d in days})
    result = []
    for current in dates:
        entries = [
            d for days in days_by_location.values() for d in days if d.date == current
        ]
        precip = _aggregate([d.precip for d in entries], max)
        if any(_is_storm(d) for d in entries):
            condition = "zivatar"
        elif precip is None:
            condition = "nincs adat"
        elif precip >= WET_DAY_MM:
            condition = "csapadék"
        else:
            condition = "száraz"
        result.append(
            OutlookDay(
                date=current,
                temp_min_c=_aggregate([d.temp_min for d in entries], min),
                temp_max_c=_aggregate([d.temp_max for d in entries], max),
                precipitation_max_mm=precip,
                wind_gust_max_ms=_aggregate([d.gust for d in entries], max),
                condition=condition,
            )
        )
    return result


def _join_days(days: list[OutlookDay], today: date) -> str:
    names = [_when(d.date, today) for d in days]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " és " + names[-1]


def build_summary(days: list[OutlookDay], today: date) -> str:
    known = [d for d in days if d.condition != "nincs adat"]
    if not known:
        return "Nincs elég adat az előretekintéshez."
    wet = [d for d in known if d.condition != "száraz"]
    if not wet:
        text = "Végig száraz idő várható."
    elif len(wet) <= 2:
        text = f"Többnyire száraz idő várható, csapadék {_join_days(wet, today)} lehet."
    elif len(wet) <= 4:
        text = f"Változékony idő, csapadék {_join_days(wet, today)} várható."
    else:
        text = "Tartósan csapadékos, változékony idő várható."

    lows = [d.temp_min_c for d in days if d.temp_min_c is not None]
    highs = [d.temp_max_c for d in days if d.temp_max_c is not None]
    if lows and highs:
        text += f" A hőmérséklet {round(min(lows))} és {round(max(highs))} °C között alakul."
    return text


def build_outlook(
    daily_by_slug: dict[str, list[DayData]],
    fetched_at: datetime,
    regions: list[Region] = REGIONS,
    locations: list[Location] = LOCATIONS,
) -> OutlookResponse:
    names = {location.slug: location.name for location in locations}
    outlooks = []
    for region in regions:
        by_name = {
            names[slug]: daily_by_slug[slug]
            for slug in region.location_slugs
            if slug in daily_by_slug
        }
        days = aggregate_days(by_name)
        if not days:
            raise WeatherProviderError("No forecast data for a region")
        today = days[0].date
        outlooks.append(
            RegionOutlook(
                name=region.name,
                slug=region.slug,
                locations=[names[slug] for slug in region.location_slugs],
                summary=build_summary(days, today),
                days=days,
                alerts=build_alerts(by_name, today),
            )
        )
    return OutlookResponse(
        provider="open-meteo",
        source_type="forecast",
        fetched_at=fetched_at,
        timezone=TIMEZONE,
        regions=outlooks,
    )


_cache: tuple[float, int, OutlookResponse] | None = None


async def fetch_outlook(days: int = 7) -> OutlookResponse:
    global _cache
    if _cache and _cache[1] == days and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[2]

    params = {
        "latitude": ",".join(str(location.latitude) for location in LOCATIONS),
        "longitude": ",".join(str(location.longitude) for location in LOCATIONS),
        "daily": (
            "temperature_2m_min,temperature_2m_max,precipitation_sum,"
            "wind_gusts_10m_max,weather_code"
        ),
        "wind_speed_unit": "ms",
        "timezone": TIMEZONE,
        "forecast_days": days,
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

    daily_by_slug = {
        location.slug: parse_days(item) for location, item in zip(LOCATIONS, items)
    }
    result = build_outlook(daily_by_slug, datetime.now(timezone.utc))
    _cache = (time.monotonic(), days, result)
    return result
