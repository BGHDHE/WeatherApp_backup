import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import thresholds


def test_defaults_when_no_file(tmp_path):
    result = thresholds.load_overrides(tmp_path / "missing.json")
    assert result.values == {} and result.approved_by is None


def test_valid_overrides_and_approval(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({
        "approved_by": "Teszt Elek", "approved_on": "2026-10-20",
        "values": {"spray.max_gust_ms": 6, "nincs.ilyen": 1, "spray.min_temp_c": "x", "harvest.max_precip_mm": True},
    }), encoding="utf-8")
    result = thresholds.load_overrides(path)
    assert result.values == {"spray.max_gust_ms": 6.0}
    assert result.approved_by == "Teszt Elek"


def test_broken_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "t.json"
    path.write_text("{nem json", encoding="utf-8")
    assert thresholds.load_overrides(path).values == {}


def test_keys_unique_and_defaults_match_logic():
    keys = [d.key for d in thresholds.DEFINITIONS]
    assert len(keys) == len(set(keys))
    assert thresholds.get("spray.max_gust_ms") == 8.0


def test_endpoint_lists_all_thresholds():
    data = TestClient(app).get("/api/thresholds").json()
    assert len(data["thresholds"]) == len(thresholds.DEFINITIONS)
    assert data["approved"] is False
    first = data["thresholds"][0]
    assert {"key", "label", "unit", "description", "default", "value", "overridden"} <= set(first)