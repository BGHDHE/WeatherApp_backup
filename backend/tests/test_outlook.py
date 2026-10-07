from datetime import date, datetime, timezone

from app.services.locations import LOCATIONS
from app.services.outlook import (
    DayData,
    aggregate_days,
    build_alerts,
    build_outlook,
    build_summary,
    parse_days,
)

TODAY = date(2026, 10, 6)  # kedd


def day(offset, tmin=8, tmax=18, precip=0.0, gust=6.0, code=1):
    return DayData(date.fromordinal(TODAY.toordinal() + offset), tmin, tmax, precip, gust, code)


def test_dry_week_is_summarised_generally():
    days = aggregate_days({"Hort": [day(i) for i in range(7)]})
    summary = build_summary(days, TODAY)
    assert summary.startswith("Végig száraz idő várható.")
    assert "8 és 18 °C" in summary


def test_storm_in_one_location_becomes_a_named_alert():
    hort = [day(i) for i in range(7)]
    hort[2] = day(2, precip=15.4, code=95)  # csütörtök
    data = {"Hort": hort, "Gyöngyös": [day(i) for i in range(7)]}

    alerts = build_alerts(data, TODAY)

    assert len(alerts) == 1
    assert alerts[0].kind == "zivatar"
    assert alerts[0].locations == ["Hort"]
    assert alerts[0].message == "Hort: csütörtökön zivatar várható, legfeljebb 15 mm esővel."


def test_same_event_in_several_locations_is_grouped():
    data = {
        "Kál": [day(0, tmin=-1)],
        "Heves": [day(0, tmin=1)],
        "Kompolt": [day(0, tmin=6)],
    }
    alerts = build_alerts(data, TODAY)
    assert len(alerts) == 1
    assert alerts[0].locations == ["Kál", "Heves"]
    assert alerts[0].message == "Kál, Heves: ma fagy, a minimum akár -1 °C."


def test_moderate_rain_is_not_an_alert_but_shows_in_summary():
    data = {"Hort": [day(0), day(1, precip=4.0), day(2)]}
    assert build_alerts(data, TODAY) == []
    summary = build_summary(aggregate_days(data), TODAY)
    assert "Többnyire száraz idő várható, csapadék holnap lehet." in summary


def test_missing_values_do_not_become_zero():
    data = {"Hort": [DayData(TODAY, None, None, None, None, None)]}
    days = aggregate_days(data)
    assert days[0].condition == "nincs adat"
    assert days[0].temp_min_c is None
    assert build_summary(days, TODAY) == "Nincs elég adat az előretekintéshez."


def test_parse_days_and_build_outlook_cover_all_regions():
    payload = {
        "daily": {
            "time": ["2026-10-06", "2026-10-07"],
            "temperature_2m_min": [3, 4],
            "temperature_2m_max": [15, 16],
            "precipitation_sum": [0, 2],
            "wind_gusts_10m_max": [5, 6],
            "weather_code": [1, 61],
        }
    }
    parsed = parse_days(payload)
    result = build_outlook(
        {loc.slug: parsed for loc in LOCATIONS}, datetime(2026, 10, 6, tzinfo=timezone.utc)
    )
    assert [r.name for r in result.regions] == [
        "Szarvasgede–Pásztó",
        "Hort–Gyöngyös",
        "Kál–Kompolt–Heves",
    ]
    assert result.regions[2].locations == ["Kál", "Kompolt", "Heves"]
    assert result.regions[0].days[1].condition == "csapadék"
