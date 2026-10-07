from datetime import datetime, timedelta, timezone

from app.services.daily import Hour, build_daily, build_location_daily, compass
from app.services.locations import LOCATIONS

NOW = datetime(2026, 10, 6, 15, 0)


def hour(ts, **kw):
    base = dict(temp=10.0, precip=0.0, prob=0.0, wind=2.0, gust=4.0, direction=315.0,
                soil_temp=11.0, soil_moisture=0.2, et0=0.1)
    base.update(kw)
    return Hour(ts=ts, **base)


def day_hours():
    start = datetime(2026, 10, 5, 0, 0)
    return [hour(start + timedelta(hours=i)) for i in range(48)]


def test_compass():
    assert compass(315) == "ÉNy"
    assert compass(0) == "É"
    assert compass(359) == "É"
    assert compass(None) is None


def test_past_24h_and_today_are_separated_and_precip_window_found():
    hours = day_hours()
    for i, h in enumerate(hours):
        if h.ts == datetime(2026, 10, 5, 20):
            hours[i] = hour(h.ts, precip=3.0, temp=-1.0)  # tegnap este: múlt 24 órában
        if datetime(2026, 10, 6, 16) <= h.ts <= datetime(2026, 10, 6, 19):
            hours[i] = hour(h.ts, precip=1.0, prob=70)
        if h.ts == datetime(2026, 10, 6, 14):
            hours[i] = hour(h.ts, gust=9.0, wind=5.0, direction=0.0)
    loc = LOCATIONS[0]

    r = build_location_daily(loc, NOW, hours)

    assert r.past_precip_mm == 3.0
    assert r.past_temp_min_c == -1.0
    assert r.today_temp_min_c == 10.0
    assert r.precip_today_mm == 4.0
    assert r.precip_window == "16:00-20:00"
    assert r.precip_probability_max == 70
    assert (r.gust_max_ms, r.gust_time, r.wind_direction) == (9.0, "14:00", "É")
    assert r.soil_moisture_percent == 20.0


def test_missing_data_stays_none_and_frost_has_no_data():
    hours = [hour(datetime(2026, 10, 6, i), temp=None, precip=None, prob=None,
                  wind=None, gust=None, direction=None, soil_temp=None,
                  soil_moisture=None, et0=None) for i in range(24)]
    r = build_location_daily(LOCATIONS[0], NOW, hours)
    assert r.today_temp_min_c is None
    assert r.precip_today_mm is None
    assert r.precip_window is None
    assert r.frost_level == "nincs adat"
    assert r.soil_moisture_percent is None


def test_build_daily_groups_by_region():
    data = {l.slug: (NOW, day_hours()) for l in LOCATIONS}
    result = build_daily(data, datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert [r.name for r in result.regions] == [
        "Szarvasgede–Pásztó", "Hort–Gyöngyös", "Kál–Kompolt–Heves"]
    assert [l.name for l in result.regions[2].locations] == ["Kál", "Kompolt", "Heves"]
    assert str(result.date) == "2026-10-06"