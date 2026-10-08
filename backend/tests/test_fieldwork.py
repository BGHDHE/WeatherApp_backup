from datetime import date, datetime, timedelta

from app.services.fieldwork import (
    FieldHour,
    assess_sowing,
    assess_tillage,
    assess_traffic,
    build_location,
    build_region_summary,
)

TODAY = date(2026, 10, 7)


def hours(precip_by_day=None, **kw):
    precip_by_day = precip_by_day or {}
    base = dict(temp=10.0, gust=4.0, soil_temp=10.0, top=0.25, sub=0.28)
    base.update(kw)
    start = datetime(2026, 10, 4)
    out = []
    for i in range(10 * 24):
        ts = start + timedelta(hours=i)
        p = precip_by_day.get(ts.date(), 0.0) / 24
        out.append(FieldHour(ts=ts, precip=p, **base))
    return out


def test_tillage_levels():
    assert assess_tillage(0, 0, 28, 10).status == "kedvező"
    assert assess_tillage(2, 0, 28, 10).status == "feltételes"
    assert assess_tillage(0, 25, 28, 10).status == "kedvezőtlen"
    assert assess_tillage(0, 0, 45, 10).status == "kedvezőtlen"
    frozen = assess_tillage(0, 0, 28, -1)
    assert frozen.status == "kedvezőtlen" and "fagyott" in frozen.reason


def test_missing_data_is_no_data():
    assert assess_tillage(None, 0, 28, 10).status == "nincs adat"
    assert assess_traffic(0, None, 20).status == "nincs adat"
    assert assess_sowing(0, 10, None, 20).status == "nincs adat"


def test_traffic_and_sowing():
    assert assess_traffic(0, 0, 20).status == "kedvező"
    assert assess_traffic(0, 0, 38).status == "feltételes"
    assert assess_traffic(0, 0, 45).status == "kedvezőtlen"
    assert assess_sowing(0, 10, 5, 25).status == "kedvező"
    assert assess_sowing(0, 6, 5, 25).status == "feltételes"
    assert assess_sowing(0, 10, -1, 25).status == "kedvezőtlen"
    assert assess_sowing(0, 10, 5, 10).status == "feltételes"


def test_build_location_best_window_and_rain_memory():
    rain = {date(2026, 10, 9): 15.0}
    loc = build_location("Teszt", "teszt", TODAY, hours(rain))
    assert len(loc.days) == 7
    assert loc.precipitation_week_mm == 15.0
    by_date = {d.date: d for d in loc.days}
    # a 10-i napon az előző 3 nap csapadéka 15 mm -> csak feltételes
    assert by_date[date(2026, 10, 10)].precipitation_prev_3d_mm == 15.0
    assert by_date[date(2026, 10, 10)].assessments[0].status == "feltételes"
    assert by_date[date(2026, 10, 9)].assessments[0].status == "kedvezőtlen" or by_date[date(2026, 10, 9)].assessments[0].status == "feltételes"
    assert loc.best_tillage_window is not None


def test_region_summary_requires_all_locations():
    a = build_location("A", "a", TODAY, hours())
    b = build_location("B", "b", TODAY, hours({date(2026, 10, 7): 20.0}))
    text = build_region_summary([a, b])
    assert "szerdán" not in text.split("kedvező talajművelésre:")[-1]
    assert build_region_summary([a, a]).startswith("Az egész térségben")

def test_day_status_is_built_from_time_slots():
    rainy = hours()
    for i, h in enumerate(rainy):
        if h.ts.date() == date(2026, 10, 8) and 9 <= h.ts.hour < 12:
            rainy[i] = FieldHour(ts=h.ts, temp=10.0, precip=3.0, gust=4.0, soil_temp=10.0, top=0.25, sub=0.28)
    loc = build_location("Teszt", "teszt", TODAY, rainy)
    day = {d.date: d for d in loc.days}[date(2026, 10, 8)]
    harvest = next(a for a in day.assessments if a.activity == "betakarítás")
    assert [s.label for s in harvest.slots] == ["6–9", "9–12", "12–15", "15–18"]
    assert [s.status for s in harvest.slots] == ["kedvező", "kedvezőtlen", "kedvező", "kedvező"]
    assert harvest.status == "feltételes" and "9–12" in harvest.reason
    clear = {d.date: d for d in loc.days}[date(2026, 10, 9)]
    assert all(a.status == "kedvező" and len(a.slots) == 4 for a in clear.assessments)


def test_location_days_include_spraying_and_harvest():
    loc = build_location("Teszt", "teszt", TODAY, hours())
    activities = [a.activity for a in loc.days[0].assessments]
    assert activities == ["talajművelés", "vetés", "gépek járhatósága", "permetezés", "betakarítás"]
