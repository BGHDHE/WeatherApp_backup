from datetime import datetime, timezone

import pytest

from app.services.forecast import WeatherProviderError, frost_level, normalize_forecast
from app.services.locations import get_location


@pytest.mark.parametrize(
    ("minimum", "expected"),
    [
        (-1, "magas"),
        (0, "magas"),
        (0.1, "mérsékelt"),
        (2, "mérsékelt"),
        (2.1, "alacsony"),
        (5, "alacsony"),
        (5.1, "nincs"),
        (None, "nincs adat"),
    ],
)
def test_frost_level_thresholds(minimum: float | None, expected: str) -> None:
    assert frost_level(minimum) == expected


def test_normalize_forecast_preserves_provenance_and_converts_soil_moisture() -> None:
    location = get_location("paszto")
    assert location is not None
    fetched_at = datetime(2026, 10, 6, 10, tzinfo=timezone.utc)
    payload = {
        "timezone": "Europe/Budapest",
        "daily": {
            "time": ["2026-10-06"],
            "temperature_2m_min": [1.5],
            "temperature_2m_max": [17],
            "precipitation_sum": [4.2],
            "wind_speed_10m_max": [8.1],
            "et0_fao_evapotranspiration": [1.3],
        },
        "hourly": {
            "time": ["2026-10-06T00:00", "2026-10-06T01:00"],
            "soil_temperature_6cm": [10, 12],
            "soil_moisture_0_to_7cm": [0.2, 0.24],
        },
    }

    result = normalize_forecast(location, payload, fetched_at)

    assert result.source_type == "forecast"
    assert result.provider == "open-meteo"
    assert result.fetched_at == fetched_at
    assert result.days[0].frost_level == "mérsékelt"
    assert result.days[0].soil_temperature_c == 11
    assert result.days[0].soil_moisture_percent == pytest.approx(22)
    assert result.days[0].evapotranspiration_mm == 1.3


def test_normalize_forecast_rejects_missing_daily_data() -> None:
    location = get_location("paszto")
    assert location is not None

    with pytest.raises(WeatherProviderError, match="Missing forecast dates"):
        normalize_forecast(location, {"daily": {}, "hourly": {}})


def test_missing_minimum_temperature_is_not_reported_as_no_frost_risk() -> None:
    location = get_location("paszto")
    assert location is not None
    payload = {
        "daily": {
            "time": ["2026-10-06"],
            "temperature_2m_min": [None],
            "temperature_2m_max": [17],
            "precipitation_sum": [0],
            "wind_speed_10m_max": [3],
        },
        "hourly": {},
    }

    result = normalize_forecast(location, payload)

    assert result.days[0].temp_min_c is None
    assert result.days[0].frost_level == "nincs adat"
