from fastapi.testclient import TestClient

from app.main import app
from app.services import thresholds


def test_keys_unique_and_values_match_logic():
    keys = [d.key for d in thresholds.DEFINITIONS]
    assert len(keys) == len(set(keys))
    assert thresholds.get("spray.max_gust_ms") == 8.0


def test_endpoint_lists_all_thresholds():
    data = TestClient(app).get("/api/thresholds").json()
    assert len(data["thresholds"]) == len(thresholds.DEFINITIONS)
    assert set(data) == {"thresholds"}
    first = data["thresholds"][0]
    assert {"key", "label", "unit", "description", "value"} <= set(first)