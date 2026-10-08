from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Location(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    slug: str
    latitude: float
    longitude: float
    region: str


class ForecastDay(BaseModel):
    date: date
    temp_min_c: float | None
    temp_max_c: float | None
    precipitation_mm: float | None
    wind_max_ms: float | None
    frost_level: Literal["nincs adat", "nincs", "alacsony", "mérsékelt", "magas"]
    frost_min_temp_c: float | None
    soil_temperature_c: float | None
    soil_moisture_percent: float | None
    evapotranspiration_mm: float | None


class ForecastResponse(BaseModel):
    location: Location
    provider: Literal["open-meteo"]
    source_type: Literal["forecast"]
    fetched_at: datetime
    timezone: str
    days: list[ForecastDay]


class Region(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    slug: str
    location_slugs: list[str]


class OutlookDay(BaseModel):
    date: date
    temp_min_c: float | None
    temp_max_c: float | None
    precipitation_max_mm: float | None
    wind_gust_max_ms: float | None
    condition: Literal["száraz", "csapadék", "zivatar", "nincs adat"]


class OutlookAlert(BaseModel):
    date: date
    kind: Literal["zivatar", "csapadék", "szél", "fagy", "hőség"]
    locations: list[str]
    message: str


class RegionOutlook(BaseModel):
    name: str
    slug: str
    locations: list[str]
    summary: str
    days: list[OutlookDay]
    alerts: list[OutlookAlert]


class OutlookResponse(BaseModel):
    provider: Literal["open-meteo"]
    source_type: Literal["forecast"]
    fetched_at: datetime
    timezone: str
    regions: list[RegionOutlook]
    stale: bool = False


class LocationDaily(BaseModel):
    name: str
    slug: str
    past_temp_min_c: float | None
    past_temp_max_c: float | None
    past_precip_mm: float | None
    past_gust_max_ms: float | None
    today_temp_min_c: float | None
    today_temp_max_c: float | None
    precip_today_mm: float | None
    precip_window: str | None
    precip_probability_max: int | None
    wind_max_ms: float | None
    wind_direction: str | None
    gust_max_ms: float | None
    gust_time: str | None
    frost_level: Literal["nincs adat", "nincs", "alacsony", "mérsékelt", "magas"]
    frost_min_temp_c: float | None
    soil_temperature_c: float | None
    soil_moisture_percent: float | None
    evapotranspiration_mm: float | None


class RegionDaily(BaseModel):
    name: str
    slug: str
    locations: list[LocationDaily]


class DailyResponse(BaseModel):
    provider: Literal["open-meteo"]
    source_type: Literal["forecast"]
    fetched_at: datetime
    timezone: str
    date: date
    as_of: datetime
    regions: list[RegionDaily]
    stale: bool = False

class FieldworkSlot(BaseModel):
    label: str
    status: Literal["kedvező", "feltételes", "kedvezőtlen", "nincs adat"]
    reason: str


class FieldworkAssessment(BaseModel):
    activity: Literal["talajművelés", "vetés", "gépek járhatósága", "permetezés", "betakarítás"]
    status: Literal["kedvező", "feltételes", "kedvezőtlen", "nincs adat"]
    reason: str
    threshold: str
    slots: list[FieldworkSlot] = []


class FieldworkDay(BaseModel):
    date: date
    precipitation_mm: float | None
    precipitation_prev_3d_mm: float | None
    temp_min_c: float | None
    temp_max_c: float | None
    soil_temperature_c: float | None
    topsoil_moisture_percent: float | None
    subsoil_moisture_percent: float | None
    wind_gust_max_ms: float | None
    observed: bool = False
    assessments: list[FieldworkAssessment]


class FieldworkLocation(BaseModel):
    name: str
    slug: str
    summary: str
    precipitation_week_mm: float | None
    best_tillage_window: str | None
    days: list[FieldworkDay]


class FieldworkRegion(BaseModel):
    name: str
    slug: str
    summary: str
    locations: list[FieldworkLocation]


class FieldworkResponse(BaseModel):
    provider: Literal["open-meteo"]
    source_type: Literal["forecast"]
    fetched_at: datetime
    timezone: str
    regions: list[FieldworkRegion]
    stale: bool = False

class ThresholdItem(BaseModel):
    key: str
    group: str
    label: str
    unit: str
    description: str
    default: float
    value: float
    overridden: bool


class ThresholdsResponse(BaseModel):
    approved: bool
    approved_by: str | None
    approved_on: str | None
    thresholds: list[ThresholdItem]

class StationRef(BaseModel):
    name: str
    distance_km: float
    observed_at: datetime | None


class LocationObservation(BaseModel):
    name: str
    slug: str
    method: Literal["interpoláció", "legközelebbi állomás", "nincs adat"]
    stations: list[StationRef]
    wind_stations: list[StationRef] = Field(default_factory=list)
    latest_time: datetime | None
    latest_temp_c: float | None
    latest_humidity_percent: float | None
    latest_wind_ms: float | None
    past_temp_min_c: float | None
    past_temp_max_c: float | None
    past_precip_mm: float | None
    past_gust_max_ms: float | None
    today_temp_min_c: float | None
    today_temp_max_c: float | None
    precip_today_mm: float | None
    wind_max_ms: float | None
    wind_direction: str | None
    gust_max_ms: float | None
    gust_time: str | None
    frost_level: Literal["nincs adat", "nincs", "alacsony", "mérsékelt", "magas"]
    frost_min_temp_c: float | None


class RegionObservation(BaseModel):
    name: str
    slug: str
    locations: list[LocationObservation]


class ObservationResponse(BaseModel):
    provider: Literal["odp.met.hu"]
    source_type: Literal["observation"]
    fetched_at: datetime
    timezone: str
    date: date
    as_of: datetime | None
    regions: list[RegionObservation]
    stale: bool = False
