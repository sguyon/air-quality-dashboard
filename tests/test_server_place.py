"""The place-dependent fetchers take a place and default to the home, with the home's cache keys unchanged."""
import server
import summary as summary_rules
from config import airgradient_map
from server import Here

BANGKOK = Here("m1", 13.9, 100.5, "Asia/Bangkok")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def fake_get(monkeypatch, payload):
    calls = []

    def get(url, params=None, **kw):
        calls.append(params)
        return FakeResponse(payload)
    monkeypatch.setattr(server.requests, "get", get)
    return calls


def test_weather_uses_the_place_given(monkeypatch):
    calls = fake_get(monkeypatch, {"current": {"temperature_2m": 30}})
    server._fetch_weather(BANGKOK)
    assert (calls[0]["latitude"], calls[0]["longitude"], calls[0]["timezone"]) == (13.9, 100.5, "Asia/Bangkok")


def test_air_forecast_uses_the_place_given(monkeypatch):
    calls = fake_get(monkeypatch, {"hourly": {"time": ["2026-11-09T10:00"], "pm2_5": [8.0]}})
    server._fetch_air_forecast(BANGKOK)
    assert (calls[0]["latitude"], calls[0]["longitude"], calls[0]["timezone"]) == (13.9, 100.5, "Asia/Bangkok")


def test_nearby_around_a_place(monkeypatch):
    world = [
        {"locationId": 1, "latitude": 13.95, "longitude": 100.5},     # ~5.5 km
        {"locationId": 2, "latitude": 13.9, "longitude": 100.55},     # ~5.4 km
        {"locationId": 3, "latitude": 40.7, "longitude": -74.0},      # far
    ]
    found = server._fetch_nearby(world, BANGKOK)
    assert {m["locationId"] for m in found} == {1, 2}
    assert all("distance_km" in m for m in found)
    assert [m["distance_km"] for m in found] == sorted(m["distance_km"] for m in found)


def test_home_keys_unchanged(monkeypatch):
    keys = []

    def spy(key, fetch, **kw):
        keys.append(key)
        raise RuntimeError("stop")
    monkeypatch.setattr(server, "cached", spy)
    server.get_open_meteo_data()
    server.get_air_forecast()
    server.smoke_status()
    assert keys == ["wx", "aq", "smoke"]
    keys.clear()
    server.get_open_meteo_data(BANGKOK)
    assert keys == ["wx:m1"]
    keys.clear()
    server.app.test_client().get("/api/neighborhood")
    assert keys == ["ag:world"]


def test_neighborhood_for_the_home_end_to_end(monkeypatch):
    home = server.home_here()
    world = [
        {"locationId": 1, "latitude": home.lat + 0.01, "longitude": home.lon},
        {"locationId": 2, "latitude": home.lat + 0.02, "longitude": home.lon},
        {"locationId": 3, "latitude": -home.lat, "longitude": home.lon + 90},
    ]
    monkeypatch.setattr(server, "cached", lambda key, fetch, **kw: (world, {"state": "hit", "age": 0}))
    got = server.app.test_client().get("/api/neighborhood").get_json()
    assert [m["locationId"] for m in got] == [1, 2]
    assert all(m["distance_km"] < server.NEARBY_RADIUS_KM for m in got)
    assert "distance_km" not in world[0]


# ── Neighbors on the corrected PM2.5, like a home's own monitors (Task 6c) ──

def test_nearby_rows_carry_corrected_pm():
    world = [{"locationId": 1, "latitude": 13.95, "longitude": 100.5, "pm02": 12.0, "rhum": 60}]
    row, = server._fetch_nearby(world, BANGKOK)
    assert row["pm02"] == 12.0   # the raw reading stays as it came
    assert row["pm02_corrected"] == summary_rules.corrected_pm(12.0, 60) == 6.9   # 0.524·12 − 0.0862·60 + 5.75
    assert "pm02_corrected" not in world[0]   # the cached world list is left as it came


def test_nearby_without_humidity_stays_raw():
    world = [{"locationId": 1, "latitude": 13.95, "longitude": 100.5, "pm02": 12.0},
             {"locationId": 2, "latitude": 13.9, "longitude": 100.55, "rhum": 60}]
    found = server._fetch_nearby(world, BANGKOK)
    assert all("pm02_corrected" not in n for n in found)
    assert {n["locationId"]: n.get("pm02") for n in found} == {1: 12.0, 2: None}


def test_nearby_rows_link_to_airgradients_map():
    world = [{"locationId": 1, "latitude": 13.95123456789012, "longitude": 100.50341234567891, "pm02": 3.0, "rhum": 50}]
    row, = server._fetch_nearby(world, BANGKOK)
    assert row["map_url"] == airgradient_map(13.9512, 100.5034)   # to about 10 m, not the list's 14 digits
    assert row["map_url"].startswith("https://www.airgradient.com/map?zoom=15&long=100.5034&lat=13.9512&")


# ── NOAA's smoke polygons: one file for North America, downloaded and parsed once, each place tested against it ──

def kml_around(lat, lon, density, half=0.5):
    """A one-placemark HMS file: a square of `half` degrees around a point."""
    ring = " ".join(f"{x},{y},0" for x, y in ((lon - half, lat - half), (lon + half, lat - half), (lon + half, lat + half),
                                               (lon - half, lat + half), (lon - half, lat - half)))
    return (f"<kml><Placemark><description>Density: {density}</description><Polygon><coordinates>{ring}</coordinates>"
            f"</Polygon></Placemark></kml>")


def test_smoke_polygons_fetched_once_for_every_place(monkeypatch):
    home = server.home_here()
    far = Here("m2", home.lat + 5, home.lon, home.tz)
    calls = []

    class Kml:
        status_code = 200

        def __init__(self, text):
            self.text = text

    def get(url, **kw):
        calls.append(url)
        return Kml(kml_around(home.lat, home.lon, "Light") + kml_around(home.lat, home.lon, "Heavy", half=0.2))
    monkeypatch.setattr(server.requests, "get", get)
    server._cache.pop("smoke", None)
    try:
        got = server.smoke_status()
        assert got == {"checked": True, "detected": True, "density": "Heavy", "date": got["date"]} and got["date"]
        assert server.smoke_status(far) == {"checked": True, "detected": False, "density": None, "date": got["date"]}
        assert server.smoke_status() == got
        assert len(calls) == 1 and "nesdis.noaa.gov" in calls[0]
    finally:
        server._cache.pop("smoke", None)


def test_logged_and_returned_errors_carry_no_keys(monkeypatch, caplog):
    """A failed pollen call's error text holds its URL (?key=...): the log line must not carry the key."""
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "FAKEPOLLENKEY12345")
    monkeypatch.setattr(server, "TOKEN", "FAKETOKEN6789")
    def boom():
        raise RuntimeError("400 Client Error for url: https://pollen.googleapis.com/v1/forecast:lookup?key=FAKEPOLLENKEY12345&x=FAKETOKEN6789")
    import logging
    with caplog.at_level(logging.WARNING, logger="aq.cache"):
        try:
            server._cache_run("test:redact", boom)
        except RuntimeError:
            pass
    text = caplog.text
    assert "upstream test:redact failed" in text
    assert "FAKEPOLLENKEY12345" not in text and "FAKETOKEN6789" not in text
    assert server._redact("a FAKEPOLLENKEY12345 b") == "a *** b"


def test_neighborhood_error_carries_no_keys(monkeypatch):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "FAKEPOLLENKEY12345")
    def boom(*a, **k):
        raise RuntimeError("failed url ...?key=FAKEPOLLENKEY12345")
    monkeypatch.setattr(server, "cached", boom)
    monkeypatch.setattr(server, "source_on", lambda name: True)
    r = server.app.test_client().get("/api/neighborhood")
    assert r.status_code == 502 and b"FAKEPOLLENKEY12345" not in r.data
