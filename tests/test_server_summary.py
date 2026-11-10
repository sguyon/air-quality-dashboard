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
    server._fetch_weather(server.home_here())
    assert seen["daily"] == "sunrise,sunset" and seen["past_hours"] == 4 and seen["forecast_days"] == 2


def test_payload_has_summary(client):
    s = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()["summary"]
    assert set(s) == {"label", "clock", "items", "also", "profiles", "all_clear", "timeline"} and len(s["profiles"]) == 3
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
    assert next(n for n in s["profiles"] if n["id"] == "runner")["facts"]["smoke"] is False


def test_analyze_profiles_read_format(client):
    for body in ({}, {"format": "stream"}):
        r = client.post("/api/analyze", json=body)
        assert r.status_code == 400 and "error" in r.get_json()


def test_card_is_redrawn_on_every_read(client):
    a = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_co2": 1310}).get_json()
    b = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_co2": 1320}).get_json()
    num = lambda r: next(i for i in r["summary"]["items"] if i["id"] == "co2")["num"]
    assert num(a) == "1,310" and num(b) == "1,320"


def test_home_without_outdoor_history_draws_no_model_past(monkeypatch):
    """The model's past hours stand in for a public monitor's history only: a home whose outdoor history is missing
    (AirGradient failed, or no outdoor monitor) draws no past PM2.5, as before."""
    from fixtures import golden_inputs as gi
    gi.install(server, monkeypatch, gi.EVENING)
    monkeypatch.setattr(server, "history_points", lambda lid, now, hours=24: gi.history(lid, now, hours) if lid == 1 else [])
    with server.app.test_client() as c:
        pm = c.post("/api/analyze", json={"format": "read", **gi.PAYLOAD}).get_json()["summary"]["timeline"]["pm"]
    assert "source" not in pm and pm["past"] == [] and pm["fc"]


def test_outdoor_only_home_reads_nothing_indoors(client, monkeypatch):
    """An outdoor-only home: even if the page posts indoor readings, the summary has no CO₂ or humidity item, the
    toddler waits for an indoor monitor and the sinus profile runs on pollen alone."""
    from config import load_config
    from conftest import REFERENCE_TOML
    before = server.CFG
    server.use_config(load_config({"CONFIG_TOML": REFERENCE_TOML.replace('indoor = "apartment"\n', "")}))
    try:
        monkeypatch.setattr(server, "get_pollen_days", lambda *a, **k: {"today": [{"name": "Tree", "index": 1}], "tomorrow": []})
        monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "test-key")
        s = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD}).get_json()["summary"]
    finally:
        server.use_config(before)
    assert not {"co2", "rh"} & {i["id"] for i in s["items"]}
    states = {n["id"]: (n["ok"], n["state"]) for n in s["profiles"]}
    assert states["toddler"] == (None, "Needs an indoor monitor")
    assert states["sinus"] == (True, "Pollen low")
    assert "pollen only: no indoor monitor for humidity" in next(n for n in s["profiles"] if n["id"] == "sinus")["why"]
    assert "config" not in str(s).lower()


def test_dev_server_keeps_the_days_pollen_on_disk(monkeypatch, tmp_path):
    """The reloading dev server reuses the day's pollen across restarts; production never writes it."""
    import server
    calls = []
    monkeypatch.setattr(server, "_fetch_pollen", lambda: calls.append(1) or {"today": [{"name": "Tree"}], "tomorrow": []})
    monkeypatch.setattr(server, "DEV_CACHE_DIR", tmp_path / "cache")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    server._fetch_pollen_kept()
    assert calls == [1] and not (tmp_path / "cache").exists()   # production: nothing stored
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    first, again = server._fetch_pollen_kept(), server._fetch_pollen_kept()   # a restart reads the file
    assert first == again == {"today": [{"name": "Tree"}], "tomorrow": []} and calls == [1, 1]


def test_pollen_is_asked_once_a_day(monkeypatch):
    """A daily forecast: the second read the same day, hours later, is the first answer; a new day asks again."""
    import server
    from datetime import datetime, timedelta
    calls, clock = [], {"t": 1_000_000.0}
    monkeypatch.setattr(server, "_fetch_pollen", lambda: calls.append(1) or {"today": [], "tomorrow": []})
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.setattr(server.time, "time", lambda: clock["t"])
    day = {"d": datetime(2026, 11, 10, 8, 0)}
    monkeypatch.setattr(server, "local_now", lambda *a: day["d"])
    with server._cache_lock:
        for k in [k for k in server._cache if k.startswith("pollen:")]:
            del server._cache[k]
    server.get_pollen_days()
    clock["t"] += 14 * 3600; day["d"] += timedelta(hours=14)   # 10 PM, same day
    server.get_pollen_days()
    assert calls == [1]
    clock["t"] += 3 * 3600; day["d"] += timedelta(hours=3)     # 1 AM, the next day
    server.get_pollen_days()
    assert calls == [1, 1]
