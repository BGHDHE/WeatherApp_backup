import csv
import io
import math
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import httpx

from app.schemas import (
    Location,
    LocationObservation,
    ObservationResponse,
    Region,
    RegionObservation,
    StationRef,
)
from app.services.daily import compass
from app.services.forecast import TIMEZONE, WeatherProviderError, frost_level
from app.services.locations import LOCATIONS, REGIONS

BASE_URL = "https://odp.met.hu/climate/observations_hungary/10_minutes"
INDEX_URL = f"{BASE_URL}/now/"
META_URL = f"{BASE_URL}/station_meta_auto.csv"

INTERPOLATION_RADIUS_KM = 10.0
NEAREST_RADIUS_KM = 20.0
INDEX_CHECK_SECONDS = 5 * 60
META_CHECK_SECONDS = 24 * 3600
MAX_STATION_LAG = timedelta(minutes=60)
MIN_PRECIP_COVERAGE = 0.8
MISSING = -999.0

_INDEX_ROW = re.compile(r"HABP_10M_(\d+)_now\.zip</a>\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Obs:
    precip: float | None
    temp: float | None
    humidity: float | None
    wind: float | None
    wind_dir: float | None
    gust: float | None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _last_sunday(year: int, month: int) -> date:
    last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def local_offset(utc: datetime) -> timedelta:
    """Central European (Budapest) offset; EU summer time without tzdata dependency."""
    start = datetime.combine(_last_sunday(utc.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(utc.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return timedelta(hours=2) if start <= utc < end else timedelta(hours=1)


def to_local(utc: datetime) -> datetime:
    return (utc + local_offset(utc)).replace(tzinfo=None)


def parse_meta(text: str) -> dict[str, tuple[Station, str]]:
    """Latest metadata row per station id, with its end date (YYYYMMDD)."""
    result: dict[str, tuple[Station, str]] = {}
    for line in text.splitlines()[1:]:
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 8:
            continue
        try:
            station = Station(parts[0], parts[6], float(parts[3]), float(parts[4]))
        except ValueError:
            continue
        end = parts[2]
        if parts[0] not in result or end >= result[parts[0]][1]:
            result[parts[0]] = (station, end)
    return result


def parse_index(html: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _INDEX_ROW.finditer(html)}


def _value(row: dict[str, str], key: str) -> float | None:
    raw = (row.get(key) or "").strip()
    if not raw or (row.get(f"Q_{key}") or "").strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return None if value <= MISSING else value


def parse_station_csv(text: str) -> dict[datetime, Obs]:
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        return {}
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=";")
    header = [h.strip() for h in next(reader)]
    result: dict[datetime, Obs] = {}
    for cells in reader:
        row = dict(zip(header, (c.strip() for c in cells)))
        try:
            ts = datetime.strptime(row["Time"], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        result[ts] = Obs(
            precip=_value(row, "r"),
            temp=_value(row, "t"),
            humidity=_value(row, "u"),
            wind=_value(row, "fs"),
            wind_dir=_value(row, "fsd"),
            gust=_value(row, "fx"),
        )
    return result


def parse_station_zip(content: bytes) -> dict[datetime, Obs]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if not names:
                return {}
            return parse_station_csv(archive.read(names[0]).decode("utf-8", errors="replace"))
    except zipfile.BadZipFile as exc:
        raise WeatherProviderError("Invalid ODP station archive") from exc


def select_stations(
    location: Location, stations: Iterable[Station]
) -> tuple[str, list[tuple[Station, float]]]:
    ranked = sorted(
        (
            (s, haversine_km(location.latitude, location.longitude, s.latitude, s.longitude))
            for s in stations
        ),
        key=lambda pair: pair[1],
    )
    close = [pair for pair in ranked if pair[1] <= INTERPOLATION_RADIUS_KM]
    if len(close) >= 2:
        return "interpoláció", close
    if close:
        return "legközelebbi állomás", close
    if ranked and ranked[0][1] <= NEAREST_RADIUS_KM:
        return "legközelebbi állomás", ranked[:1]
    return "nincs adat", []


def _idw(pairs: list[tuple[float, float]]) -> float | None:
    """Inverse-distance-squared weighted mean of (value, distance_km) pairs."""
    if not pairs:
        return None
    weights = [1.0 / max(distance, 0.5) ** 2 for _, distance in pairs]
    return sum(v * w for (v, _), w in zip(pairs, weights)) / sum(weights)


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _interpolate(
    series: dict[str, dict[datetime, Obs]], distances: dict[str, float]
) -> dict[datetime, dict[str, float | None]]:
    timestamps = sorted({ts for data in series.values() for ts in data})
    merged: dict[datetime, dict[str, float | None]] = {}
    for ts in timestamps:
        obs = [(distances[sid], data[ts]) for sid, data in series.items() if ts in data]

        def mean(attr: str) -> float | None:
            return _idw([(getattr(o, attr), d) for d, o in obs if getattr(o, attr) is not None])

        wind_pairs = [(d, o) for d, o in obs if o.wind is not None and o.wind_dir is not None]
        east = _idw([(-o.wind * math.sin(math.radians(o.wind_dir)), d) for d, o in wind_pairs])
        north = _idw([(-o.wind * math.cos(math.radians(o.wind_dir)), d) for d, o in wind_pairs])
        direction = None
        if east is not None and north is not None and math.hypot(east, north) > 1e-6:
            direction = (math.degrees(math.atan2(-east, -north))) % 360
        merged[ts] = {
            "precip": mean("precip"),
            "temp": mean("temp"),
            "humidity": mean("humidity"),
            "wind": mean("wind"),
            "wind_dir": direction,
            "gust": mean("gust"),
        }
    return merged


def _present(values: Iterable[float | None]) -> list[float]:
    return [v for v in values if v is not None]


def build_location_observation(
    location: Location,
    method: str,
    selected: list[tuple[Station, float]],
    wind_selected: list[tuple[Station, float]],
    data: dict[str, dict[datetime, Obs]],
) -> LocationObservation:
    series = {s.id: data[s.id] for s, _ in selected if data.get(s.id)}
    refs = [
        StationRef(
            name=s.name,
            distance_km=round(distance, 1),
            observed_at=max(data[s.id]) if data.get(s.id) else None,
        )
        for s, distance in selected
        if s.id in series
    ]
    wind_series = {s.id: data[s.id] for s, _ in wind_selected if data.get(s.id)}
    wind_refs = [
        StationRef(
            name=s.name,
            distance_km=round(distance, 1),
            observed_at=max(data[s.id]) if data.get(s.id) else None,
        )
        for s, distance in wind_selected
        if s.id in wind_series
    ]
    empty = dict(
        name=location.name,
        slug=location.slug,
        stations=refs,
        wind_stations=wind_refs,
        latest_time=None,
        latest_temp_c=None,
        latest_humidity_percent=None,
        latest_wind_ms=None,
        past_temp_min_c=None,
        past_temp_max_c=None,
        past_precip_mm=None,
        past_gust_max_ms=None,
        today_temp_min_c=None,
        today_temp_max_c=None,
        precip_today_mm=None,
        wind_max_ms=None,
        wind_direction=None,
        gust_max_ms=None,
        gust_time=None,
        frost_level=frost_level(None),
        frost_min_temp_c=None,
    )
    if not series:
        return LocationObservation(method="nincs adat", **empty)

    distances = {s.id: d for s, d in selected}
    merged = _interpolate(series, distances)
    wind_distances = {s.id: d for s, d in wind_selected if s.id in wind_series}
    wind_merged = _interpolate(wind_series, wind_distances)
    latest = max(merged)
    past = {ts: v for ts, v in merged.items() if latest - timedelta(hours=24) < ts <= latest}
    midnight_local = to_local(latest).replace(hour=0, minute=0, second=0, microsecond=0)
    midnight = midnight_local - local_offset(latest)
    midnight = midnight.replace(tzinfo=timezone.utc)
    today = {ts: v for ts, v in merged.items() if ts >= midnight}
    wind_today = {ts: v for ts, v in wind_merged.items() if ts >= midnight}

    def precip_sum(window: dict[datetime, dict[str, float | None]], start: datetime) -> float | None:
        expected = int((latest - start) / timedelta(minutes=10))
        values = _present(v["precip"] for ts, v in window.items() if ts > start)
        if expected <= 0 or len(values) < expected * MIN_PRECIP_COVERAGE:
            return None
        return sum(values)

    today_temps = _present(v["temp"] for v in today.values())
    today_min = min(today_temps) if today_temps else None
    past_temps = _present(v["temp"] for v in past.values())
    gusts = [(v["gust"], ts) for ts, v in wind_today.items() if v["gust"] is not None]
    gust_max = max(gusts, key=lambda pair: pair[0]) if gusts else None
    winds = [(v["wind"], ts) for ts, v in wind_today.items() if v["wind"] is not None]
    wind_max = max(winds, key=lambda pair: pair[0]) if winds else None
    past_gusts = _present(v["gust"] for v in past.values())
    now_values = merged[latest]

    empty.update(
        latest_time=latest,
        latest_temp_c=_r(now_values["temp"]),
        latest_humidity_percent=_r(now_values["humidity"]),
        latest_wind_ms=_r(now_values["wind"]),
        past_temp_min_c=_r(min(past_temps)) if past_temps else None,
        past_temp_max_c=_r(max(past_temps)) if past_temps else None,
        past_precip_mm=_r(precip_sum(past, latest - timedelta(hours=24))),
        past_gust_max_ms=_r(max(past_gusts)) if past_gusts else None,
        today_temp_min_c=_r(today_min),
        today_temp_max_c=_r(max(today_temps)) if today_temps else None,
        precip_today_mm=_r(precip_sum(today, midnight)),
        wind_max_ms=_r(wind_max[0]) if wind_max else None,
        wind_direction=compass(wind_today[wind_max[1]]["wind_dir"]) if wind_max else None,
        gust_max_ms=_r(gust_max[0]) if gust_max else None,
        gust_time=f"{to_local(gust_max[1]):%H:%M}" if gust_max else None,
        frost_level=frost_level(today_min),
        frost_min_temp_c=_r(today_min),
    )
    return LocationObservation(method=method, **empty)


def build_observations(
    stations: dict[str, Station],
    data: dict[str, dict[datetime, Obs]],
    fetched_at: datetime,
    regions: list[Region] = REGIONS,
    locations: list[Location] = LOCATIONS,
) -> ObservationResponse:
    newest = max((max(d) for d in data.values() if d), default=None)
    fresh = {
        sid: d
        for sid, d in data.items()
        if d and newest is not None and newest - max(d) <= MAX_STATION_LAG
    }
    usable = [stations[sid] for sid in fresh if sid in stations]
    by_slug = {l.slug: l for l in locations}
    region_items = []
    for region in regions:
        items = []
        for slug in region.location_slugs:
            location = by_slug[slug]
            method, selected = select_stations(location, usable)
            selected_latest = max(
                (max(fresh[s.id]) for s, _ in selected if fresh.get(s.id)),
                default=newest,
            )
            local_date = to_local(selected_latest).date() if selected_latest else to_local(fetched_at).date()

            def has_wind_data(station: Station) -> bool:
                return any(
                    to_local(ts).date() == local_date
                    and (observation.wind is not None or observation.gust is not None)
                    for ts, observation in fresh.get(station.id, {}).items()
                )

            wind_selected = [(station, distance) for station, distance in selected if has_wind_data(station)]
            if not wind_selected:
                nearby_reporting = [
                    (station, distance)
                    for station in usable
                    if (distance := haversine_km(
                        location.latitude,
                        location.longitude,
                        station.latitude,
                        station.longitude,
                    )) <= NEAREST_RADIUS_KM
                    and has_wind_data(station)
                ]
                if nearby_reporting:
                    wind_selected = [min(nearby_reporting, key=lambda pair: pair[1])]

            items.append(
                build_location_observation(location, method, selected, wind_selected, fresh)
            )
        region_items.append(RegionObservation(name=region.name, slug=region.slug, locations=items))
    local_newest = to_local(newest) if newest else None
    return ObservationResponse(
        provider="odp.met.hu",
        source_type="observation",
        fetched_at=fetched_at,
        timezone=TIMEZONE,
        date=local_newest.date() if local_newest else fetched_at.date(),
        as_of=newest,
        regions=region_items,
    )


_meta: tuple[float, dict[str, Station]] | None = None
_index_checked: float = 0.0
_index: dict[str, str] = {}
_station_data: dict[str, tuple[str, dict[datetime, Obs]]] = {}


def reset_state() -> None:
    global _meta, _index_checked, _index
    _meta = None
    _index_checked = 0.0
    _index = {}
    _station_data.clear()


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    response = await client.get(url)
    response.raise_for_status()
    return response


def _candidates(meta: dict[str, Station], index: dict[str, str]) -> dict[str, Station]:
    return {
        sid: station
        for sid, station in meta.items()
        if sid in index
        and any(
            haversine_km(l.latitude, l.longitude, station.latitude, station.longitude) <= NEAREST_RADIUS_KM
            for l in LOCATIONS
        )
    }


async def fetch_observations() -> ObservationResponse:
    global _meta, _index_checked, _index
    now = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            if _meta is None or now - _meta[0] > META_CHECK_SECONDS:
                text = (await _get(client, META_URL)).content.decode("utf-8", errors="replace")
                today = datetime.now(timezone.utc).strftime("%Y%m%d")
                limit = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y%m%d")
                meta = {
                    sid: station
                    for sid, (station, end) in parse_meta(text).items()
                    if end >= limit
                }
                _meta = (now, meta)
            if not _index or now - _index_checked > INDEX_CHECK_SECONDS:
                _index = parse_index((await _get(client, INDEX_URL)).text)
                _index_checked = now
            candidates = _candidates(_meta[1], _index)
            for sid in candidates:
                cached = _station_data.get(sid)
                if cached and cached[0] == _index[sid]:
                    continue
                try:
                    content = (await _get(client, f"{INDEX_URL}HABP_10M_{sid}_now.zip")).content
                    _station_data[sid] = (_index[sid], parse_station_zip(content))
                except (httpx.HTTPError, WeatherProviderError):
                    if cached is None:
                        continue
    except httpx.HTTPError as exc:
        raise WeatherProviderError("ODP request failed") from exc

    data = {sid: _station_data[sid][1] for sid in candidates if sid in _station_data}
    if not data:
        raise WeatherProviderError("No ODP station data available")
    return build_observations(candidates, data, datetime.now(timezone.utc))
