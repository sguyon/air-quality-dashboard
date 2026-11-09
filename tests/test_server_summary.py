import server
from conftest import SAMPLE_PAYLOAD


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


def test_read_carries_no_unread_fields(client):
    # the page reads summary, generated_at and clock; the old card's headline, cards, checked, ahead and the pollen
    # relief line had no reader left
    r = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()
    assert not {"headline", "cards", "checked", "ahead", "relief", "relief_short"} & set(r)
    assert {"summary", "generated_at", "clock"} <= set(r)


def test_history_keeps_humidity_for_the_chart(monkeypatch, client):
    import server
    row = {"timestamp": "2026-11-08T10:00:00.000Z", "pm02": 3, "rco2": 600, "rhum": 52, "rhum_corrected": 51, "atmp": 21}
    monkeypatch.setattr(server, "api_get", lambda path, params=None: [row])
    rows = client.get("/api/history/1?from=2026-11-01T00:00:00Z&to=2026-11-02T00:00:00Z").get_json()
    assert rows[0]["rhum_corrected"] == 51 and rows[0]["rhum"] == 52 and "atmp" not in rows[0]


def test_canned_smoke_is_off_like_the_real_function(client):
    s = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()["summary"]
    assert next(n for n in s["needs"] if n["id"] == "runner")["facts"]["smoke"] is False


def test_analyze_needs_read_format(client):
    for body in ({}, {"format": "stream"}):
        r = client.post("/api/analyze", json=body)
        assert r.status_code == 400 and "error" in r.get_json()


def test_card_is_redrawn_on_every_read(client):
    a = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_co2": 1310}).get_json()
    b = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_co2": 1320}).get_json()
    num = lambda r: next(i for i in r["summary"]["items"] if i["id"] == "co2")["num"]
    assert num(a) == "1,310" and num(b) == "1,320"
