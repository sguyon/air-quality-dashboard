"""Sources that are off or not set up: each says so, calmly, and the summary drops what is missing."""
import pytest

import server
from conftest import SAMPLE_PAYLOAD
from test_golden import config_from, strings


@pytest.fixture
def use_config():
    before = server.CFG
    yield server.use_config
    server.use_config(before)


def status(client):
    return client.get("/api/context").get_json()["status"]


def test_pollen_without_key_is_not_set_up(monkeypatch, client):
    monkeypatch.delenv("GOOGLE_POLLEN_API_KEY", raising=False)
    assert status(client)["pollen"] == "not_set_up"


def test_pollen_with_key_is_ok_or_error(monkeypatch, client):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "test-key")
    assert status(client)["pollen"] == "error"   # on, set up, and nothing came back
    monkeypatch.setattr(server, "get_pollen_days", lambda *a, **k: {"today": [{"name": "Grass", "index": 1}], "tomorrow": []})
    assert status(client)["pollen"] == "ok"


def test_pollen_turned_off_is_off_and_never_fetched(monkeypatch, client, use_config):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "test-key")
    use_config(config_from(sources={"pollen": False}))

    def boom(*a, **k):
        raise AssertionError("pollen was fetched")
    monkeypatch.setattr(server, "get_pollen_days", boom)
    assert status(client)["pollen"] == "off"


def test_smoke_off_in_config(monkeypatch, client, use_config):
    use_config(config_from(sources={"smoke": False}))

    def boom(*a, **k):
        raise AssertionError("smoke was fetched")
    monkeypatch.setattr(server, "smoke_status", boom)
    assert status(client)["smoke"] == "off"


def test_smoke_on_is_ok_when_checked_error_when_not(monkeypatch, client):
    monkeypatch.setattr(server, "smoke_status", lambda: {"checked": True, "detected": False, "density": None, "date": "2026-11-08"})
    assert status(client)["smoke"] == "ok"
    monkeypatch.setattr(server, "smoke_status", lambda: {"checked": False, "detected": False, "density": None, "date": None})
    assert status(client)["smoke"] == "error"


def test_no_road_is_off(client, use_config):
    assert status(client)["road"] == "ok"
    use_config(config_from(road=None))
    assert status(client)["road"] == "off"


def test_nearby_off_in_config(monkeypatch, client, use_config):
    use_config(config_from(sources={"nearby": False}))

    def boom(*a, **k):
        raise AssertionError("nearby was fetched")
    monkeypatch.setattr(server, "_fetch_nearby", boom)
    assert status(client)["nearby"] == "off"
    assert client.get("/api/neighborhood").get_json() == []


def test_summary_without_pollen_uses_humidity_only(monkeypatch, client, use_config):
    monkeypatch.delenv("GOOGLE_POLLEN_API_KEY", raising=False)
    high = [{"name": "Grass", "level": "High", "index": 4, "in_season": True}]
    # even if a stale cache held pollen, a source that is not set up is not read
    monkeypatch.setattr(server, "get_pollen_data", lambda *a, **k: high)
    monkeypatch.setattr(server, "get_pollen_days", lambda *a, **k: {"today": high, "tomorrow": high})
    body = {"format": "read", **SAMPLE_PAYLOAD, "indoor_humidity": 45}
    out = client.post("/api/analyze", json=body).get_json()
    needs = out["summary"]["needs"]
    sinus = next(n for n in needs if n["id"] == "sinus")
    assert sinus["facts"]["pollen_index"] is None
    assert all(i["id"] != "pollen" for i in out["summary"]["items"])
    said = list(strings(out["summary"])) + list(strings(out["needs"]))
    assert not any("{" in s or "  " in s for s in said)
    assert not any("pollen" in s.lower() for s in strings(sinus))
