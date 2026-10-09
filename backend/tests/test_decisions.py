from app.services.decisions import assess_harvest, assess_spraying


def test_spray_ok():
    assert assess_spraying(0.0, 5.0, 8.0, 20.0).status == "kedvező"


def test_spray_reports_every_problem():
    a = assess_spraying(3.0, 12.0, 8.0, 20.0)
    assert a.status == "kedvezőtlen"
    assert "csapadék" in a.reason and "széllökés" in a.reason
    assert "m/s" in a.threshold


def test_spray_temperature_limits():
    assert assess_spraying(0.0, 5.0, 2.0, 20.0).status == "kedvezőtlen"
    assert assess_spraying(0.0, 5.0, 8.0, 30.0).status == "kedvezőtlen"


def test_spray_mean_wind_limit():
    a = assess_spraying(0.0, 7.0, 8.0, 20.0, wind=6.0)
    assert a.status == "kedvezőtlen" and "szél 6" in a.reason
    assert assess_spraying(0.0, 7.0, 8.0, 20.0, wind=3.0).status == "kedvező"


def test_missing_data_is_not_favourable():
    assert assess_spraying(0.0, None, 8.0, 20.0).status == "nincs adat"
    assert assess_harvest(None).status == "nincs adat"


def test_harvest():
    assert assess_harvest(0.8).status == "kedvező"
    assert assess_harvest(5.0).status == "kedvezőtlen"

def test_spray_humidity_dew_delta_t_are_conditional():
    base = dict(wind=2.0)
    ok = assess_spraying(0.0, 5.0, 8.0, 20.0, humidity=60, delta_t=5.0, dew_spread=4.0, inversion=False, **base)
    assert ok.status == "kedvező"
    assert assess_spraying(0.0, 5.0, 8.0, 20.0, humidity=30, **base).status == "feltételes"
    assert "harmat" in assess_spraying(0.0, 5.0, 8.0, 20.0, dew_spread=0.5, **base).reason
    assert assess_spraying(0.0, 5.0, 8.0, 20.0, delta_t=1.0, **base).status == "feltételes"
    assert assess_spraying(0.0, 5.0, 8.0, 20.0, delta_t=9.0, **base).status == "feltételes"
    assert assess_spraying(0.0, 5.0, 8.0, 20.0, delta_t=11.0, **base).status == "kedvezőtlen"


def test_spray_inversion_is_unfavourable():
    a = assess_spraying(0.0, 3.0, 8.0, 20.0, wind=1.0, inversion=True)
    assert a.status == "kedvezőtlen" and "inverzió" in a.reason


def test_harvest_humidity():
    assert assess_harvest(0.0, humidity=70).status == "kedvező"
    assert assess_harvest(0.0, humidity=85).status == "feltételes"
    assert assess_harvest(0.0, humidity=95).status == "kedvezőtlen"


def test_tillage_frost():
    from app.services.fieldwork import assess_tillage

    assert assess_tillage(0.0, 0.0, 20.0, 5.0, temp_min=-1.0).status == "kedvezőtlen"
    assert assess_tillage(0.0, 0.0, 20.0, 5.0, temp_min=1.5).status == "feltételes"
    assert assess_tillage(0.0, 0.0, 20.0, 5.0, temp_min=6.0).status == "kedvező"


def test_sowing_week_precip_and_soil_trend():
    from app.services.fieldwork import assess_sowing

    ok = assess_sowing(0.0, 10.0, 5.0, 25.0, week_precip=15.0, soil_trend=0.5)
    assert ok.status == "kedvező"
    assert assess_sowing(0.0, 10.0, 5.0, 25.0, week_precip=60.0).status == "feltételes"
    assert assess_sowing(0.0, 10.0, 5.0, 25.0, week_precip=1.0).status == "feltételes"
    assert assess_sowing(0.0, 10.0, 5.0, 25.0, week_precip=15.0, soil_trend=-3.0).status == "feltételes"


def test_field_hour_delta_t_and_inversion():
    from datetime import datetime
    from app.services.fieldwork import FieldHour

    h = FieldHour(ts=datetime(2026, 4, 1, 7), temp=20.0, precip=0, gust=1, soil_temp=8, top=0.2, sub=0.3,
                  wind=1.0, humidity=50.0, dew_point=9.3, temp_80m=21.0)
    assert 6.0 < h.delta_t < 6.6
    assert h.inversion is True
    assert FieldHour(ts=h.ts, temp=20.0, precip=0, gust=1, soil_temp=8, top=0.2, sub=0.3, wind=5.0, temp_80m=21.0).inversion is False