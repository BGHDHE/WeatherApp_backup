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


def test_missing_data_is_not_favourable():
    assert assess_spraying(0.0, None, 8.0, 20.0).status == "nincs adat"
    assert assess_harvest(None).status == "nincs adat"


def test_harvest():
    assert assess_harvest(0.8).status == "kedvező"
    assert assess_harvest(5.0).status == "kedvezőtlen"