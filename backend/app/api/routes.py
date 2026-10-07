import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    DailyResponse,
    FieldworkResponse,
    ForecastResponse,
    Location,
    OutlookResponse,
    ThresholdItem,
    ThresholdsResponse,
)
from app.services.daily import fetch_daily
from app.services.fieldwork import fetch_fieldwork
from app.services.forecast import WeatherProviderError, fetch_forecast
from app.services.locations import LOCATIONS, get_location
from app.services.outlook import fetch_outlook
from app.services import thresholds
from app.services.snapshots import load_snapshot, save_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/locations", response_model=list[Location])
async def list_locations() -> list[Location]:
    return LOCATIONS


@router.get("/reports/forecast", response_model=ForecastResponse)
async def get_forecast(
    location: str = Query(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$"),
    days: int = Query(default=4, ge=1, le=7),
) -> ForecastResponse:
    selected_location = get_location(location)
    if selected_location is None:
        raise HTTPException(status_code=404, detail="Ismeretlen település")

    try:
        return await fetch_forecast(selected_location, days)
    except WeatherProviderError as exc:
        logger.warning("Open-Meteo forecast request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Az időjárás-előrejelzés jelenleg nem érhető el",
        ) from exc


@router.get("/outlook", response_model=OutlookResponse)
async def get_outlook(days: int = Query(default=7, ge=3, le=7)) -> OutlookResponse:
    try:
        result = await fetch_outlook(days)
        save_snapshot(f"outlook-{days}", result)
        return result
    except WeatherProviderError as exc:
        logger.warning("Open-Meteo outlook request failed: %s", exc)
        saved = load_snapshot(f"outlook-{days}", OutlookResponse)
        if saved is not None:
            return saved.model_copy(update={"stale": True})
        raise HTTPException(
            status_code=502,
            detail="Az időjárás-előretekintés jelenleg nem érhető el",
        ) from exc


@router.get("/daily", response_model=DailyResponse)
async def get_daily() -> DailyResponse:
    try:
        result = await fetch_daily()
        save_snapshot("daily", result)
        return result
    except WeatherProviderError as exc:
        logger.warning("Open-Meteo daily request failed: %s", exc)
        saved = load_snapshot("daily", DailyResponse)
        if saved is not None:
            return saved.model_copy(update={"stale": True})
        raise HTTPException(
            status_code=502,
            detail="A napi időjárás jelenleg nem érhető el",
        ) from exc

@router.get("/fieldwork", response_model=FieldworkResponse)
async def get_fieldwork() -> FieldworkResponse:
    try:
        result = await fetch_fieldwork()
        save_snapshot("fieldwork", result)
        return result
    except WeatherProviderError as exc:
        logger.warning("Open-Meteo fieldwork request failed: %s", exc)
        saved = load_snapshot("fieldwork", FieldworkResponse)
        if saved is not None:
            return saved.model_copy(update={"stale": True})
        raise HTTPException(
            status_code=502,
            detail="A földmunka-elemzés jelenleg nem érhető el",
        ) from exc

@router.get("/thresholds", response_model=ThresholdsResponse)
async def get_thresholds() -> ThresholdsResponse:
    current = thresholds.overrides()
    items = [
        ThresholdItem(
            key=d.key,
            group=d.group,
            label=d.label,
            unit=d.unit,
            description=d.description,
            default=d.default,
            value=thresholds.get(d.key),
            overridden=d.key in current.values,
        )
        for d in thresholds.DEFINITIONS
    ]
    return ThresholdsResponse(
        approved=current.approved_by is not None and current.approved_on is not None,
        approved_by=current.approved_by,
        approved_on=current.approved_on,
        thresholds=items,
    )