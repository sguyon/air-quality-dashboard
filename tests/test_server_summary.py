import pytest

import server
from conftest import SAMPLE_PAYLOAD


def test_summary_ai_off_never_calls_model(monkeypatch, client):
    monkeypatch.setattr(server, "SUMMARY_AI", False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(server, "call_read_model", lambda *a, **k: pytest.fail("model called"))
    r = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()
    assert r["source"] == "rules" and r["note"] is None


def test_pm_fine_is_15():
    assert server.PM_FINE == 15


def test_weather_asks_for_sun_times_and_past_hours(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"current": {"temperature_2m": 1}}

    def fake_get(url, params=None, timeout=None):
        seen.update(params or {})
        return R()
    monkeypatch.setattr(server.requests, "get", fake_get)
    server._fetch_weather()
    assert seen["daily"] == "sunrise,sunset" and seen["past_hours"] == 4 and seen["forecast_days"] == 2


def test_payload_has_summary(client):
    s = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()["summary"]
    assert set(s) == {"label", "clock", "items", "also", "needs", "all_clear", "timeline"} and len(s["needs"]) == 3
    assert [i["id"] for i in s["items"]][:2] == ["co2", "rh"]


def test_model_means_reach_the_card(monkeypatch, client):
    monkeypatch.setattr(server, "SUMMARY_AI", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(server, "ai_allowed", lambda ip: None)
    monkeypatch.setattr(server, "call_read_model", lambda *a, **k: {"why": "Stale and damp inside today.",
                        "means": {"co2": "Stale air makes sleep lighter.", "humidity": "Damp air feeds mold.", "pm": "Clean air."}})
    body = {"format": "read", "force": True, **SAMPLE_PAYLOAD, "indoor_co2": 1310}
    r = client.post("/api/analyze", json=body).get_json()
    co2 = next(i for i in r["summary"]["items"] if i["id"] == "co2")
    assert r["source"] == "model" and co2["why"].startswith("Stale air makes sleep lighter.")


def test_history_keeps_humidity_for_the_chart(monkeypatch, client):
    import server
    row = {"timestamp": "2026-11-08T10:00:00.000Z", "pm02": 3, "rco2": 600, "rhum": 52, "rhum_corrected": 51, "atmp": 21}
    monkeypatch.setattr(server, "api_get", lambda path, params=None: [row])
    rows = client.get("/api/history/1?from=2026-11-01T00:00:00Z&to=2026-11-02T00:00:00Z").get_json()
    assert rows[0]["rhum_corrected"] == 51 and rows[0]["rhum"] == 52 and "atmp" not in rows[0]


def test_cached_model_read_still_draws_a_fresh_card(monkeypatch, client):
    monkeypatch.setattr(server, "SUMMARY_AI", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(server, "ai_allowed", lambda ip: None)
    monkeypatch.setattr(server, "call_read_model", lambda *a, **k: {"why": "Stale and damp inside today.",
                        "means": {"co2": "Stale air makes sleep lighter.", "humidity": "Damp air feeds mold.", "pm": "Clean air."}})
    client.post("/api/analyze", json={"format": "read", "force": True, **SAMPLE_PAYLOAD, "indoor_co2": 1310})
    r = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_co2": 1320}).get_json()
    co2 = next(i for i in r["summary"]["items"] if i["id"] == "co2")
    assert r.get("cached") and co2["num"] == "1,320" and co2["why"].startswith("Stale air makes sleep lighter.")


def test_canned_smoke_is_off_like_the_real_function(client):
    s = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()["summary"]
    assert next(n for n in s["needs"] if n["id"] == "runner")["facts"]["smoke"] is False
