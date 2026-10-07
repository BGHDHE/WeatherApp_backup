from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.schemas import DailyResponse
from app.services.forecast import WeatherProviderError


def sample() -> DailyResponse:
    return DailyResponse(
        provider="open-meteo",
        source_type="forecast",
        fetched_at=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
        timezone="Europe/Budapest",
        date=date(2026, 10, 6),
        as_of=datetime(2026, 10, 6, 14, 0),
        regions=[],
    )


def test_daily_serves_stale_snapshot_when_provider_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_DB", str(tmp_path / "s.sqlite3"))
    client = TestClient(app)

    async def ok():
        return sample()

    async def fail():
        raise WeatherProviderError("down")

    monkeypatch.setattr(routes, "fetch_daily", ok)
    first = client.get("/api/daily")
    assert first.status_code == 200
    assert first.json()["stale"] is False

    monkeypatch.setattr(routes, "fetch_daily", fail)
    second = client.get("/api/daily")
    assert second.status_code == 200
    assert second.json()["stale"] is True


def test_daily_returns_502_without_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_DB", str(tmp_path / "empty.sqlite3"))

    async def fail():
        raise WeatherProviderError("down")

    monkeypatch.setattr(routes, "fetch_daily", fail)
    assert TestClient(app).get("/api/daily").status_code == 502