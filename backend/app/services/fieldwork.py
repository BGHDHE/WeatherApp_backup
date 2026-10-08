import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.schemas import (
    FieldworkAssessment,
    FieldworkDay,
    FieldworkLocation,
    FieldworkRegion,
    FieldworkResponse,
    FieldworkSlot,
    LocationObservation,
    ObservationResponse,
)
from app.services import thresholds
from app.services.observations import fetch_observations
from app.services.decisions import assess_harvest, assess_spraying
from app.services.forecast import OPEN_METEO_URL, TIMEZONE, WeatherProviderError
from app.services.locations import LOCATIONS, REGIONS
from app.services.outlook import WEEKDAYS_ON

CACHE_SECONDS = 10 * 60
FORECAST_DAYS = 7
PAST_DAYS = 3
SLOTS = [(6, 9), (9, 12), (12, 15), (15, 18)]
SLOT_PRECIP_SCALE = 0.25

# Kezdeti küszöbök; éles használat előtt agronómussal jóváhagyandók.
TILL_OK_PRECIP = thresholds.get("tillage.ok_precip_mm")
TILL_BAD_PRECIP = thresholds.get("tillage.bad_precip_mm")
TILL_OK_PREV3 = thresholds.get("tillage.ok_prev3_mm")
TILL_BAD_PREV3 = thresholds.get("tillage.bad_prev3_mm")
TILL_OK_SUBSOIL = thresholds.get("tillage.ok_subsoil_pct")
TILL_BAD_SUBSOIL = thresholds.get("tillage.bad_subsoil_pct")
TRAFFIC_OK_TOPSOIL = thresholds.get("traffic.ok_topsoil_pct")
TRAFFIC_BAD_TOPSOIL = thresholds.get("traffic.bad_topsoil_pct")
SOW_OK_SOIL_TEMP = thresholds.get("sowing.ok_soil_temp_c")
SOW_BAD_SOIL_TEMP = thresholds.get("sowing.bad_soil_temp_c")
SOW_DRY_TOPSOIL = thresholds.get("sowing.dry_topsoil_pct")

TILL_THRESHOLD = (
    f"kedvező: csapadék ≤ {TILL_OK_PRECIP:g} mm, előző 3 nap ≤ {TILL_OK_PREV3:g} mm, "
    f"alsó réteg nedvessége ≤ {TILL_OK_SUBSOIL:g}%, talaj > 0 °C; "
    f"kedvezőtlen: csapadék > {TILL_BAD_PRECIP:g} mm, előző 3 nap > {TILL_BAD_PREV3:g} mm, "
    f"alsó réteg > {TILL_BAD_SUBSOIL:g}% vagy fagyott talaj"
)
TRAFFIC_THRESHOLD = (
    f"kedvező: felső réteg nedvessége ≤ {TRAFFIC_OK_TOPSOIL:g}%, csapadék ≤ {TILL_OK_PRECIP:g} mm, "
    f"előző 3 nap ≤ {TILL_OK_PREV3:g} mm; kedvezőtlen: felső réteg > {TRAFFIC_BAD_TOPSOIL:g}%, "
    f"csapadék > {TILL_BAD_PRECIP:g} mm vagy előző 3 nap > {TILL_BAD_PREV3:g} mm"
)
SOW_THRESHOLD = (
    f"kedvező: talajhőmérséklet ≥ {SOW_OK_SOIL_TEMP:g} °C, nincs fagy, csapadék ≤ {TILL_BAD_PRECIP:g} mm, "
    f"felső réteg ≥ {SOW_DRY_TOPSOIL:g}%; kedvezőtlen: talaj < {SOW_BAD_SOIL_TEMP:g} °C, fagy vagy "
    f"csapadék > {TILL_BAD_PRECIP:g} mm"
)


@dataclass(frozen=True)
class FieldHour:
    ts: datetime
    temp: float | None
    precip: float | None
    gust: float | None
    soil_temp: float | None
    top: float | None
    sub: float | None
    wind: float | None = None


def _num(values: Any, index: int) -> float | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherProviderError("Invalid numeric value in Open-Meteo response")
    return float(value)


def parse_field_hours(payload: dict[str, Any]) -> tuple[date, list[FieldHour]]:
    hourly = payload.get("hourly")
    current = payload.get("current")
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        raise WeatherProviderError("Missing hourly data in Open-Meteo response")
    if not isinstance(current, dict):
        raise WeatherProviderError("Missing current time in Open-Meteo response")
    try:
        today = datetime.fromisoformat(current["time"]).date()
        hours = [
            FieldHour(
                ts=datetime.fromisoformat(raw),
                temp=_num(hourly.get("temperature_2m"), i),
                precip=_num(hourly.get("precipitation"), i),
                gust=_num(hourly.get("wind_gusts_10m"), i),
                soil_temp=_num(hourly.get("soil_temperature_6cm"), i),
                top=_num(hourly.get("soil_moisture_0_to_7cm"), i),
                sub=_num(hourly.get("soil_moisture_7_to_28cm"), i),
                wind=_num(hourly.get("wind_speed_10m"), i),
            )
            for i, raw in enumerate(hourly["time"])
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherProviderError("Invalid time in Open-Meteo response") from exc
    return today, hours


def _vals(hours: list[FieldHour], attr: str) -> list[float]:
    return [v for v in (getattr(h, attr) for h in hours) if v is not None]


def _sum(hours: list[FieldHour], attr: str) -> float | None:
    values = _vals(hours, attr)
    return round(sum(values), 1) if values else None


def _mean(hours: list[FieldHour], attr: str, scale: float = 1.0) -> float | None:
    values = _vals(hours, attr)
    return round(sum(values) / len(values) * scale, 1) if values else None


def _min(hours: list[FieldHour], attr: str) -> float | None:
    values = _vals(hours, attr)
    return round(min(values), 1) if values else None


def _max(hours: list[FieldHour], attr: str) -> float | None:
    values = _vals(hours, attr)
    return round(max(values), 1) if values else None


def _verdict(activity, threshold, bad, caution, ok_reason) -> FieldworkAssessment:
    if bad:
        status, reason = "kedvezőtlen", ", ".join(bad + caution)
    elif caution:
        status, reason = "feltételes", ", ".join(caution)
    else:
        status, reason = "kedvező", ok_reason
    return FieldworkAssessment(activity=activity, status=status, reason=reason, threshold=threshold)


def _no_data(activity, threshold) -> FieldworkAssessment:
    return FieldworkAssessment(activity=activity, status="nincs adat", reason="Hiányos adat", threshold=threshold)


def assess_tillage(precip, prev3, sub, soil_temp, precip_scale=1.0) -> FieldworkAssessment:
    if None in (precip, prev3, sub, soil_temp):
        return _no_data("talajművelés", TILL_THRESHOLD)
    bad, caution = [], []
    if soil_temp <= 0:
        bad.append(f"fagyott talaj ({soil_temp:g} °C)")
    if sub > TILL_BAD_SUBSOIL:
        bad.append(f"átázott alsó réteg ({sub:g}%)")
    elif sub > TILL_OK_SUBSOIL:
        caution.append(f"nedves alsó réteg ({sub:g}%)")
    if precip > TILL_BAD_PRECIP * precip_scale:
        bad.append(f"csapadék {precip:g} mm")
    elif precip > TILL_OK_PRECIP * precip_scale:
        caution.append(f"csapadék {precip:g} mm")
    if prev3 > TILL_BAD_PREV3:
        bad.append(f"előző 3 napban {prev3:g} mm")
    elif prev3 > TILL_OK_PREV3:
        caution.append(f"előző 3 napban {prev3:g} mm")
    return _verdict("talajművelés", TILL_THRESHOLD, bad, caution, "A talaj és a csapadék a küszöbökön belül van")


def assess_traffic(precip, prev3, top, precip_scale=1.0) -> FieldworkAssessment:
    if None in (precip, prev3, top):
        return _no_data("gépek járhatósága", TRAFFIC_THRESHOLD)
    bad, caution = [], []
    if top > TRAFFIC_BAD_TOPSOIL:
        bad.append(f"vizes felső réteg ({top:g}%)")
    elif top > TRAFFIC_OK_TOPSOIL:
        caution.append(f"nedves felső réteg ({top:g}%)")
    if precip > TILL_BAD_PRECIP * precip_scale:
        bad.append(f"csapadék {precip:g} mm")
    elif precip > TILL_OK_PRECIP * precip_scale:
        caution.append(f"csapadék {precip:g} mm")
    if prev3 > TILL_BAD_PREV3:
        bad.append(f"előző 3 napban {prev3:g} mm")
    elif prev3 > TILL_OK_PREV3:
        caution.append(f"előző 3 napban {prev3:g} mm")
    return _verdict("gépek járhatósága", TRAFFIC_THRESHOLD, bad, caution, "A talaj teherbíró, száraz idő várható")


def assess_sowing(precip, soil_temp, temp_min, top, precip_scale=1.0) -> FieldworkAssessment:
    if None in (precip, soil_temp, temp_min, top):
        return _no_data("vetés", SOW_THRESHOLD)
    bad, caution = [], []
    if soil_temp < SOW_BAD_SOIL_TEMP:
        bad.append(f"hideg talaj ({soil_temp:g} °C)")
    elif soil_temp < SOW_OK_SOIL_TEMP:
        caution.append(f"hűvös talaj ({soil_temp:g} °C)")
    if temp_min <= 0:
        bad.append(f"fagy ({temp_min:g} °C)")
    if precip > TILL_BAD_PRECIP * precip_scale:
        bad.append(f"csapadék {precip:g} mm")
    if top < SOW_DRY_TOPSOIL:
        caution.append(f"száraz felső réteg ({top:g}%)")
    return _verdict("vetés", SOW_THRESHOLD, bad, caution, "A talajhőmérséklet és a nedvesség megfelelő")


def _runs(days: list[FieldworkDay]) -> list[list[date]]:
    runs: list[list[date]] = []
    for day in days:
        ok = next((a for a in day.assessments if a.activity == "talajművelés"), None)
        if ok and ok.status == "kedvező":
            if runs and (day.date - runs[-1][-1]).days == 1:
                runs[-1].append(day.date)
            else:
                runs.append([day.date])
    return runs


def format_run(run: list[date]) -> str:
    first, last = WEEKDAYS_ON[run[0].weekday()], WEEKDAYS_ON[run[-1].weekday()]
    return first if len(run) == 1 else f"{first}–{last}"


def combine_slots(results: list[tuple[str, FieldworkAssessment]]) -> FieldworkAssessment:
    """A nap értékelése a 3 órás szakaszokból: mind kedvezőtlen -> kedvezőtlen; mind kedvező -> kedvező;
    egyébként (legalább egy feltételes vagy kedvezőtlen) feltételes."""
    first = results[0][1]
    slots = [FieldworkSlot(label=label, status=a.status, reason=a.reason) for label, a in results]
    known = [s for s in slots if s.status != "nincs adat"]
    threshold = first.threshold + f" (3 órás szakaszokra a csapadékküszöb ×{SLOT_PRECIP_SCALE:g})"
    if not known:
        return FieldworkAssessment(
            activity=first.activity, status="nincs adat", reason="Hiányos adat", threshold=threshold, slots=slots
        )
    bad = [s for s in known if s.status == "kedvezőtlen"]
    warn = [s for s in known if s.status == "feltételes"]
    if len(bad) == len(slots):
        status = "kedvezőtlen"
    elif bad or warn:
        status = "feltételes"
    else:
        status = "kedvező"
    if status == "kedvező":
        reason = "Mind a négy időszak (6–18 óra) kedvező"
    else:
        reason = "; ".join(f"{s.label} óra: {s.reason}" for s in bad + warn)
    return FieldworkAssessment(
        activity=first.activity, status=status, reason=reason, threshold=threshold, slots=slots
    )


def build_location(
    name: str,
    slug: str,
    today: date,
    hours: list[FieldHour],
    observation: LocationObservation | None = None,
    observed_date: date | None = None,
) -> FieldworkLocation:
    by_day: dict[date, list[FieldHour]] = defaultdict(list)
    for h in hours:
        by_day[h.ts.date()].append(h)

    days = []
    for offset in range(FORECAST_DAYS):
        d = today + timedelta(days=offset)
        day_hours = by_day.get(d, [])
        if not day_hours:
            continue
        prev = [h for k in range(1, PAST_DAYS + 1) for h in by_day.get(d - timedelta(days=k), [])]
        prev_complete = all(by_day.get(d - timedelta(days=k)) for k in range(1, PAST_DAYS + 1))
        precip = _sum(day_hours, "precip")
        prev3 = _sum(prev, "precip") if prev_complete else None
        top = _mean(day_hours, "top", 100)
        sub = _mean(day_hours, "sub", 100)
        soil_temp = _mean(day_hours, "soil_temp")
        temp_min = _min(day_hours, "temp")
        gust = _max(day_hours, "gust")
        temp_max = _max(day_hours, "temp")
        observed = False
        precip_factor = 1.0
        precip_even: float | None = None
        if observation is not None and d == today and observed_date == today:
            if observation.precip_today_mm is not None:
                if precip and precip > 0:
                    precip_factor = observation.precip_today_mm / precip
                else:
                    precip_even = observation.precip_today_mm
                precip, observed = observation.precip_today_mm, True
            if observation.today_temp_min_c is not None and observation.today_temp_max_c is not None:
                temp_min, temp_max, observed = observation.today_temp_min_c, observation.today_temp_max_c, True
            if observation.gust_max_ms is not None:
                gust, observed = observation.gust_max_ms, True

        slots = []
        for start, end in SLOTS:
            slot_hours = [h for h in day_hours if start <= h.ts.hour < end]
            slot_precip = _sum(slot_hours, "precip")
            if slot_precip is not None:
                slot_precip = round(slot_precip * precip_factor, 2)
            if precip_even is not None and slot_hours:
                slot_precip = round(precip_even * len(slot_hours) / 24, 2)
            slots.append(
                (
                    f"{start}–{end}",
                    dict(
                        precip=slot_precip,
                        temp_min=_min(slot_hours, "temp"),
                        temp_max=_max(slot_hours, "temp"),
                        gust=_max(slot_hours, "gust"),
                        wind=_max(slot_hours, "wind"),
                        soil_temp=_mean(slot_hours, "soil_temp"),
                        top=_mean(slot_hours, "top", 100),
                        sub=_mean(slot_hours, "sub", 100),
                    ),
                )
            )
        s = SLOT_PRECIP_SCALE
        assessments = [
            combine_slots(
                [
                    (label, assess_tillage(v["precip"], prev3, v["sub"], v["soil_temp"], s))
                    for label, v in slots
                ]
            ),
            combine_slots(
                [
                    (label, assess_sowing(v["precip"], v["soil_temp"], v["temp_min"], v["top"], s))
                    for label, v in slots
                ]
            ),
            combine_slots(
                [(label, assess_traffic(v["precip"], prev3, v["top"], s)) for label, v in slots]
            ),
            combine_slots(
                [
                    (label, assess_spraying(v["precip"], v["gust"], v["temp_min"], v["temp_max"], s, v["wind"]))
                    for label, v in slots
                ]
            ),
            combine_slots([(label, assess_harvest(v["precip"], s)) for label, v in slots]),
        ]
        days.append(
            FieldworkDay(
                date=d,
                precipitation_mm=precip,
                precipitation_prev_3d_mm=prev3,
                temp_min_c=temp_min,
                temp_max_c=temp_max,
                soil_temperature_c=soil_temp,
                topsoil_moisture_percent=None if top is None else round(top),
                subsoil_moisture_percent=None if sub is None else round(sub),
                wind_gust_max_ms=gust,
                observed=observed,
                assessments=assessments,
            )
        )
    if not days:
        raise WeatherProviderError("No fieldwork data for a location")

    runs = _runs(days)
    best = max(runs, key=len) if runs else None
    week = [d.precipitation_mm for d in days if d.precipitation_mm is not None]
    week_precip = round(sum(week), 1) if week else None
    if best:
        summary = f"Talajművelésre kedvező: {format_run(best)}."
        if len(runs) > 1:
            summary += " További kedvező nap(ok): " + ", ".join(format_run(r) for r in runs if r is not best) + "."
    else:
        summary = "A héten nincs talajművelésre kedvező nap."
    return FieldworkLocation(
        name=name,
        slug=slug,
        summary=summary,
        precipitation_week_mm=week_precip,
        best_tillage_window=format_run(best) if best else None,
        days=days,
    )


def build_region_summary(locations: list[FieldworkLocation]) -> str:
    common: list[date] = []
    for index, day in enumerate(locations[0].days):
        if all(
            index < len(loc.days)
            and loc.days[index].date == day.date
            and loc.days[index].assessments[0].status == "kedvező"
            for loc in locations
        ):
            common.append(day.date)
    if not common:
        return "Nincs olyan nap, amikor a térség minden településén kedvező a talajművelés."
    runs: list[list[date]] = []
    for d in common:
        if runs and (d - runs[-1][-1]).days == 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    return "Az egész térségben kedvező talajművelésre: " + ", ".join(format_run(r) for r in runs) + "."


def build_fieldwork(
    data: dict[str, tuple[date, list[FieldHour]]],
    fetched_at: datetime,
    observations: ObservationResponse | None = None,
) -> FieldworkResponse:
    names = {l.slug: l.name for l in LOCATIONS}
    observed = {}
    if observations is not None:
        observed = {loc.slug: loc for region in observations.regions for loc in region.locations}
    regions = []
    for region in REGIONS:
        locations = [
            build_location(
                names[slug],
                slug,
                data[slug][0],
                data[slug][1],
                observed.get(slug),
                observations.date if observations is not None else None,
            )
            for slug in region.location_slugs
        ]
        regions.append(
            FieldworkRegion(
                name=region.name,
                slug=region.slug,
                summary=build_region_summary(locations),
                locations=locations,
            )
        )
    return FieldworkResponse(
        provider="open-meteo",
        source_type="forecast",
        fetched_at=fetched_at,
        timezone=TIMEZONE,
        regions=regions,
    )


_cache: tuple[float, FieldworkResponse] | None = None


async def fetch_fieldwork() -> FieldworkResponse:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    params = {
        "latitude": ",".join(str(l.latitude) for l in LOCATIONS),
        "longitude": ",".join(str(l.longitude) for l in LOCATIONS),
        "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m,soil_temperature_6cm,"
        "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm",
        "current": "temperature_2m",
        "wind_speed_unit": "ms",
        "timezone": TIMEZONE,
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
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

    data = {l.slug: parse_field_hours(item) for l, item in zip(LOCATIONS, items)}
    try:
        observations = await fetch_observations()
    except WeatherProviderError:
        observations = None
    result = build_fieldwork(data, datetime.now(timezone.utc), observations)
    _cache = (time.monotonic(), result)
    return result