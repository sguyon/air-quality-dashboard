"""The demo's public monitors (?monitor=<id>): any public AirGradient outdoor monitor, live, at its own place.
No test calls the network: requests.get is faked, by URL, with a small world list of four monitors."""
import hashlib
import importlib
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import server as server_module
import summary as summary_rules
import publicmap
from demo import public

ROOF, BANGKOK, INDOOR, TAGGED = 900002, 67255, 4242, 777

WORLD = [
    {"locationId": INDOOR, "locationName": "Kitchen", "publicLocationName": "Kitchen", "latitude": 40.78, "longitude": -73.90,
     "offline": False, "pm02": 3.0, "rco2": 600, "rhum": 45, "atmp": 21.0, "timestamp": "2026-11-09T21:23:00.000Z",
     "publicPlaceName": None, "publicPlaceUrl": None, "publicContributorName": None, "timezone": "America/New_York",
     "model": "I-9PSL", "firmwareVersion": "3.7.0"},
    {"locationId": ROOF, "locationName": "Oak & Elm st ", "publicLocationName": " Maple roof ",
     "latitude": 40.7772, "longitude": -73.9007, "offline": False, "pm01": 1.0, "pm02": 4.2, "pm10": 5.0, "rco2": 406,
     "rhum": 37, "atmp": 17.7, "tvocIndex": 151, "noxIndex": 1, "wifi": -67, "timestamp": "2026-11-09T21:23:38.000Z",
     "publicPlaceName": "Maple Ave", "publicPlaceUrl": "https://example.org/maple-roof",
     "publicContributorName": "Robin", "timezone": "America/New_York", "model": "O-1PST", "firmwareVersion": "3.7.0"},
    {"locationId": BANGKOK, "locationName": "Suriya Thep Alley", "publicLocationName": None, "latitude": 13.7494,
     "longitude": 100.4769, "offline": False, "pm02": 9.8, "rco2": 426, "rhum": 55, "atmp": 28.2,
     "timestamp": "2026-11-09T21:24:03.000Z", "publicPlaceName": None, "publicPlaceUrl": None,
     "publicContributorName": "Thep school", "timezone": "Asia/Bangkok", "model": "O-1PS", "firmwareVersion": "0.6.4"},
    {"locationId": TAGGED, "locationName": "<b>Loud</b> corner", "publicLocationName": "<b>Loud</b> corner",
     "latitude": 34.05, "longitude": -118.25, "offline": True, "pm02": 12.0, "timestamp": "2026-11-09T18:00:00.000Z",
     "publicPlaceName": None, "publicPlaceUrl": None, "publicContributorName": "<i>Owner</i>", "timezone": None,
     "model": "O-1PST", "firmwareVersion": "3.7.0"},
]

WEATHER = {"current": {"time": "2026-11-09T16:30", "temperature_2m": 17.0, "relative_humidity_2m": 40, "dew_point_2m": 3.5,
                       "weather_code": 1, "wind_speed_10m": 9, "wind_direction_10m": 300, "visibility": 24000,
                       "uv_index": 0.5, "cloud_cover": 10},
           "hourly": {"time": ["2026-11-09T16:00", "2026-11-09T17:00"], "temperature_2m": [17, 16]},
           "daily": {"time": ["2026-11-09"], "sunrise": ["2026-11-09T06:33"], "sunset": ["2026-11-09T16:41"]}}
MODEL = {"hourly": {"time": ["2026-11-09T16:00", "2026-11-09T17:00"], "pm2_5": [5.0, 6.0]}}


class FakeResponse:
    def __init__(self, payload=None, status=200, text=""):
        self.payload, self.status_code, self.text = payload, status, text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise server_module.requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self.payload


@pytest.fixture(scope="module")
def demo():
    os.environ["DEMO"] = "1"
    try:
        srv = importlib.reload(server_module)
        srv.app.config["TESTING"] = True
        yield srv
    finally:
        os.environ.pop("DEMO", None)
        importlib.reload(server_module)


@pytest.fixture
def net(demo, monkeypatch):
    """Fake upstreams, by URL; `calls` records each URL asked for. Set net["world_down"] to make the world list fail,
    net["world"] or net["model"] to answer with another world list or PM2.5 model (a function of the request's params
    answers by place). AirGradient's public map: net["area"] (its monitors around a point; none by default) and
    net["history"] (measure → [{"timebucket", "value"}]); either set to a status code or an exception fails that call."""
    demo._cache.clear()
    state = {"calls": [], "world_down": False, "world": WORLD, "model": MODEL, "area": [], "history": {}}

    def map_answer(answer, payload):
        if isinstance(answer, int):
            return FakeResponse(status=answer)
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse({"data": payload(answer), "total": None})

    def get(url, params=None, **kw):
        state["calls"].append(url)
        if url == f"{publicmap.MAP_API}/measurements/current/area":
            return map_answer(state["area"], lambda a: a)
        if url.startswith(f"{publicmap.MAP_API}/locations/") and url.endswith("/measures/history"):
            return map_answer(state["history"], lambda h: h.get(params["measure"], []))
        if "/world/locations/measures/current" in url:
            return FakeResponse(status=503) if state["world_down"] else FakeResponse(state["world"])
        if "air-quality-api.open-meteo.com" in url:
            return FakeResponse(state["model"](params) if callable(state["model"]) else state["model"])
        if "api.open-meteo.com" in url:
            return FakeResponse(WEATHER)
        if "nesdis.noaa.gov" in url:
            return FakeResponse(status=200, text=state["kml"]) if state.get("kml") else FakeResponse(status=404)
        raise AssertionError(f"unexpected call to {url}")
    monkeypatch.setattr(demo.requests, "get", get)
    yield state
    demo._cache.clear()


@pytest.fixture
def c(demo, net):
    with demo.app.test_client() as client:
        yield client


def app_of(resp):
    html = resp.get_data(as_text=True)
    return json.loads(html.split("window.APP = ", 1)[1].split(";</script>", 1)[0])


TRIMMED = {"locationId", "name", "street", "contributor", "distance_km", "pm02", "offline", "timestamp"}


def test_nearest_is_outdoor_and_sorted():
    rows = publicmap.nearest(WORLD, 40.78, -73.90)
    assert INDOOR not in [r["locationId"] for r in rows]
    assert rows[0]["locationId"] == ROOF
    assert all(set(r) == TRIMMED for r in rows)
    assert rows[0]["name"] == "Maple roof" and rows[0]["street"] == "Maple Ave"
    assert rows[0]["contributor"] == "Robin"
    assert [r["distance_km"] for r in rows] == sorted(r["distance_km"] for r in rows)
    assert len(publicmap.nearest(WORLD, 40.78, -73.90, n=1)) == 1


def test_find_is_outdoor_only():
    assert publicmap.find(WORLD, ROOF)["locationId"] == ROOF
    assert publicmap.find(WORLD, INDOOR) is None
    assert publicmap.find(WORLD, 1) is None


def test_view_of_a_monitor(demo):
    roof = public.view_of(publicmap.find(WORLD, ROOF), demo.APP_VIEW)
    assert roof["profiles"] == {"toddler": False, "sinus": False, "runner": True}
    assert roof["sources"] == {"pollen": False, "road": False, "smoke": True, "nearby": True}   # booleans, like the config's
    assert roof["links"]["forecast"].startswith("https://forecast.weather.gov/")
    assert roof["road"] is None
    assert roof["place"]["name"] == "Maple roof" and roof["place"]["outdoor"] == "Maple roof"
    assert roof["place"]["indoor"] is None and roof["place"]["timezone"] == "America/New_York"
    assert roof["public"] == {"id": ROOF, "name": "Maple roof", "street": "Maple Ave", "contributor": "Robin",
                              "url": "https://example.org/maple-roof"}
    bk = public.view_of(publicmap.find(WORLD, BANGKOK), demo.APP_VIEW)
    assert bk["sources"]["smoke"] is False
    assert bk["links"]["forecast"] is None   # NWS forecasts only the US
    assert bk["links"]["map_home"]
    assert bk["place"]["timezone"] == "Asia/Bangkok"
    assert bk["place"]["name"] == "Suriya Thep Alley"
    assert bk["public"]["contributor"] == "Thep school"
    assert demo.APP_VIEW["profiles"]["toddler"] is True   # the base view is not changed


def test_pollen_seasons_only_near_the_demo_home(demo):
    """The demo home's pollen calendar is New York's: a monitor near it keeps it, one across the world gets none."""
    assert demo.APP_VIEW["pollen_seasons"]
    roof = public.view_of(publicmap.find(WORLD, ROOF), demo.APP_VIEW)
    assert roof["pollen_seasons"] == demo.APP_VIEW["pollen_seasons"]
    assert public.view_of(publicmap.find(WORLD, BANGKOK), demo.APP_VIEW)["pollen_seasons"] == []
    assert public.view_of(publicmap.find(WORLD, TAGGED), demo.APP_VIEW)["pollen_seasons"] == []   # Los Angeles: > 300 km


def test_here_and_current_rows():
    here = public.here_of(publicmap.find(WORLD, BANGKOK))
    assert here == (f"m{BANGKOK}", 13.7494, 100.4769, "Asia/Bangkok")
    assert public.here_of(publicmap.find(WORLD, TAGGED)).tz == "UTC"
    rows = public.current_rows(publicmap.find(WORLD, ROOF))
    assert len(rows) == 1 and rows[0]["locationType"] == "outdoor" and rows[0]["locationId"] == ROOF
    assert rows[0]["pm02"] == 4.2 and rows[0]["locationName"] == "Maple roof"


@pytest.mark.parametrize("tz", [None, "", "Mars/Base", "../etc/passwd", "/abs", 5])
def test_here_falls_back_to_utc(tz):
    """The world list's timezone is AirGradient's data: one that names no real zone reads UTC, never a crash later."""
    assert public.here_of({**publicmap.find(WORLD, BANGKOK), "timezone": tz}).tz == "UTC"


def test_monitor_page_and_api(c, net):
    page = c.get(f"/?monitor={ROOF}")
    assert page.status_code == 200
    app = app_of(page)
    assert app["public"]["id"] == ROOF and "error" not in app["public"]
    assert "now" not in app
    assert app["profiles"] == {"toddler": False, "sinus": False, "runner": True}
    assert page.headers["Cache-Control"] == "public, max-age=60, s-maxage=300"

    cur = c.get(f"/api/current?monitor={ROOF}")
    rows = cur.get_json()
    assert cur.status_code == 200 and len(rows) == 1 and rows[0]["locationType"] == "outdoor"
    assert cur.headers["Cache-Control"] == "public, max-age=60, s-maxage=300"
    hist = c.get(f"/api/history/{ROOF}?monitor={ROOF}")
    assert hist.status_code == 200 and hist.get_json() == []

    ctx = c.get(f"/api/context?monitor={ROOF}").get_json()
    assert ctx["weather"]["temperature"] == 17.0 and ctx["weather"]["wind_direction"] == 300
    assert ctx["status"]["pollen"] == "off" and ctx["status"]["road"] == "off"
    assert "road" not in ctx and "bqe" not in ctx and ctx["pollen"] == []
    assert not any("pollen.googleapis.com" in u for u in net["calls"])

    nb = c.get(f"/api/neighborhood?monitor={ROOF}").get_json()
    assert [n["locationId"] for n in nb][:2] == [ROOF, INDOOR]   # the real filter around the monitor
    assert all("distance_km" in n for n in nb)
    # its own row in the table reads what its card reads: the corrected PM2.5 (Task 6c)
    assert nb[0]["pm02_corrected"] == rows[0]["pm02_corrected"] == 4.8 and nb[0]["pm02"] == 4.2
    assert nb[0]["map_url"].startswith("https://www.airgradient.com/map?zoom=15&long=-73.9007&lat=40.7772&")


def test_monitor_data_is_cached_per_monitor(c, net, demo):
    for _ in range(2):
        c.get(f"/api/context?monitor={ROOF}")
        c.get(f"/api/current?monitor={ROOF}")
    weather = [u for u in net["calls"] if "api.open-meteo.com/v1/forecast" in u]
    world = [u for u in net["calls"] if "/world/" in u]
    assert len(weather) == 1 and len(world) == 1
    c.get(f"/api/context?monitor={BANGKOK}")
    assert len([u for u in net["calls"] if "api.open-meteo.com/v1/forecast" in u]) == 2
    assert {f"wx:m{ROOF}", f"aq:m{ROOF}", f"wx:m{BANGKOK}", "ag:world"} <= set(demo._cache)
    assert "wx" not in demo._cache   # the home's key stays untouched


def test_bangkok_clock_and_smoke(c, net, demo):
    page = c.get(f"/?monitor={BANGKOK}")
    app = app_of(page)
    assert app["place"]["timezone"] == "Asia/Bangkok" and app["sources"]["smoke"] is False
    ctx = c.get(f"/api/context?monitor={BANGKOK}").get_json()
    assert ctx["status"]["smoke"] == "off"
    assert not any("nesdis.noaa.gov" in u for u in net["calls"])   # NOAA's map stops at North America
    with demo.app.test_request_context(f"/?monitor={BANGKOK}"):
        assert str(demo.local_now().tzinfo) == "Asia/Bangkok"


def sample_answers(c, mid):
    """A monitor that can't be shown: its API answers are the default sample's (made-up data), and no one keeps them."""
    pairs = [(f"/api/{p}?monitor={mid}", f"/api/{p}?sample=1") for p in ("current", "context", "neighborhood")]
    for bad, sample in pairs:
        got, want = c.get(bad), c.get(sample)
        assert got.status_code == 200 and got.get_json() == want.get_json(), bad
        assert got.headers["Cache-Control"] == "no-store"
    indoor = c.get(f"/api/current?sample=1").get_json()[0]["locationId"]
    hist = c.get(f"/api/history/{indoor}?monitor={mid}")
    assert hist.get_json() and hist.get_json() == c.get(f"/api/history/{indoor}?sample=1").get_json()
    assert hist.headers["Cache-Control"] == "no-store"
    read = c.post(f"/api/analyze?monitor={mid}", json={"format": "read"})
    assert read.status_code == 200 and read.headers["Cache-Control"] == "no-store"


def test_unknown_monitor(c, net):
    for bad in (123456, INDOOR):
        page = c.get(f"/?monitor={bad}")
        assert page.status_code == 200
        app = app_of(page)
        assert app["public"] == {"id": bad, "error": f"Monitor {bad} isn't on AirGradient's public map"}
        assert app["place"]["name"] == "Williamsburg, Brooklyn NY"   # the default sample's page, with the reason
        assert app["now"]["moment"] == app_of(c.get("/?sample=1"))["now"]["moment"]
        assert page.headers["Cache-Control"] == "no-store"
        sample_answers(c, bad)
    assert not any("open-meteo" in u for u in net["calls"])
    for junk in ("abc", "0", "-5", "²"):   # not a monitor id: the plain sample
        resp = c.get(f"/?monitor={junk}")
        assert resp.status_code == 200 and "public" not in app_of(resp)


def test_monitor_answers_are_not_indexed(c, net):
    """A public monitor's page and API carry its owner's name: search engines are told not to index them. The
    samples stay indexable (the demo is for search engines)."""
    for path in ("/", "/api/current", "/api/context", "/api/neighborhood"):
        for mid in (ROOF, 123456):
            assert c.get(f"{path}?monitor={mid}").headers.get("X-Robots-Tag") == "noindex", (path, mid)
    assert c.get("/api/monitors").headers.get("X-Robots-Tag") == "noindex"
    assert c.post(f"/api/analyze?monitor={ROOF}", json={"format": "read"}).headers.get("X-Robots-Tag") == "noindex"
    for path in ("/", "/?sample=1", "/api/context?sample=2"):
        assert "X-Robots-Tag" not in c.get(path).headers, path


def test_huge_monitor_id_is_junk(c, net):
    """Past about 4,300 digits int() raises: a 5,000-digit ?monitor= is junk, not a 500, on the page and the API."""
    huge = "9" * 5000
    resp = c.get(f"/?monitor={huge}")
    assert resp.status_code == 200 and "public" not in app_of(resp)
    for path in ("/api/current", "/api/context", "/api/neighborhood"):
        assert c.get(f"{path}?monitor={huge}").status_code == 200, path
    assert not any("/world/" in u for u in net["calls"])


def test_world_list_down(c, net):
    net["world_down"] = True
    page = c.get(f"/?monitor={ROOF}")
    assert page.status_code == 200
    assert app_of(page)["public"] == {"id": ROOF, "error": "AirGradient's public map didn't answer"}
    resp = c.get("/api/monitors")
    assert resp.status_code == 502 and resp.get_json() == {"error": "AirGradient's public map didn't answer"}
    sample_answers(c, ROOF)


def test_world_list_bug_is_not_a_map_outage(c, monkeypatch, demo):
    """Only a failed or timed-out fetch reads as "the map didn't answer"; a bug in our code still raises."""
    def broken():
        raise KeyError("a bug")
    monkeypatch.setitem(demo.demo_data._REAL, "_fetch_world", broken)
    with pytest.raises(KeyError):
        c.get(f"/?monitor={ROOF}")


def test_monitor_smoke_keeps_its_own_ttl(c, net, demo, monkeypatch):
    seen = {}
    real = demo.demo_data._REAL["cached"]

    def spy(key, fetch, **kw):
        seen[key] = kw["ttl"]
        return real(key, fetch, **kw)
    monkeypatch.setitem(demo.demo_data._REAL, "cached", spy)
    c.get(f"/api/context?monitor={ROOF}")
    assert seen[f"wx:m{ROOF}"] == public.MONITOR_TTL and seen[f"aq:m{ROOF}"] == public.MONITOR_TTL
    assert seen["smoke"] == 1800 and not any(k.startswith("smoke:") for k in seen)   # one key for every monitor


def test_smoke_file_is_downloaded_once_for_every_monitor(c, net, demo):
    """NOAA's file covers North America: two monitors there share one download, and each is tested at its own place."""
    from test_server_place import kml_around
    roof = publicmap.find(WORLD, ROOF)
    net["kml"] = kml_around(roof["latitude"], roof["longitude"], "Medium")
    assert c.get(f"/api/context?monitor={ROOF}").get_json()["smoke"]["density"] == "Medium"
    la = c.get(f"/api/context?monitor={TAGGED}").get_json()["smoke"]
    assert la["checked"] is True and la["detected"] is False
    assert len([u for u in net["calls"] if "nesdis.noaa.gov" in u]) == 1


def test_names_with_html_stay_inert(c):
    html = c.get(f"/?monitor={TAGGED}").get_data(as_text=True)
    raw = html.split("window.APP = ", 1)[1].split(";</script>", 1)[0]
    assert "<" not in raw and json.loads(raw)["public"]["name"] == "<b>Loud</b> corner"


def test_monitors_default_new_york(c):
    body = c.get("/api/monitors").get_json()
    assert body["near"] == "New York"
    assert body["monitors"][0]["locationId"] == ROOF
    assert INDOOR not in [m["locationId"] for m in body["monitors"]]


def test_monitors_route_rounds(c, monkeypatch):
    got = []
    monkeypatch.setattr(publicmap, "nearest", lambda world, lat, lon, n=publicmap.PICKER_COUNT: got.append((lat, lon)) or [])
    body = c.get("/api/monitors?lat=40.73456&lon=-73.95123").get_json()
    assert got == [(40.73, -73.95)] and body == {"near": "you", "monitors": []}
    assert c.get("/api/monitors?lat=x&lon=1").status_code == 400


def test_monitors_route_only_in_the_demo(demo, monkeypatch):
    monkeypatch.setattr(demo, "MODE", "live")
    with demo.app.test_client() as client:
        assert client.get("/api/monitors").status_code == 404


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


# The default sample's answers before public monitors existed (sha256 of the sorted JSON, first 16 hex digits;
# the page is checked in test_demo.py).
SAMPLE_BEFORE = {
    "/api/current": "150a35e45008fe0c", "/api/context": "d70ffdedee6eab84",
    "/api/neighborhood": "8088a41040dae5c0",
    "/api/current?moment=rush": "150a35e45008fe0c",
    "/api/context?moment=rush": "d70ffdedee6eab84", "/api/neighborhood?moment=rush": "8088a41040dae5c0",
    "/api/current?moment=clear": "fd99c0e8c62db6c8",
    "/api/context?moment=clear": "1e5434ff04926b83", "/api/neighborhood?moment=clear": "557e170a3a50a6f8",
    "/api/current?moment=humid": "3f99cb689a5ca5ca",
    "/api/context?moment=humid": "bdeb37422f9bebb7", "/api/neighborhood?moment=humid": "ad37005d02a64f47",
}


def test_samples_unchanged(demo, monkeypatch):
    """The API answers are pinned. The page (`/`) now carries each moment's number, so test_demo.py checks it instead."""
    def refuse(*a, **k):
        raise AssertionError("a sample called the network")
    monkeypatch.setattr(demo.requests, "get", refuse)
    with demo.app.test_client() as client:
        for url, want in SAMPLE_BEFORE.items():
            resp = client.get(url)
            got = resp.get_json()
            assert _h(got) == want, url
            assert resp.headers["Cache-Control"] == "public, max-age=300, s-maxage=86400"


def test_monitor_analyze_answers(c):
    """The summary itself is Task 4's; here the read runs at the monitor's place without failing."""
    row = c.get(f"/api/current?monitor={ROOF}").get_json()[0]
    body = {"format": "read", "outdoor_pm25": row["pm02"], "outdoor_humidity": row["rhum"], "outdoor_temp_c": row["atmp"],
            "outdoor_location_id": row["locationId"]}
    resp = c.post(f"/api/analyze?monitor={ROOF}", json=body)
    assert resp.status_code == 200 and resp.get_json()["status"] in ("good", "warn", "bad")


# ── The summary for a public monitor (Task 4) ──
# A public monitor runs on the real clock at its place: these tests pin that clock, so nothing drifts across an hour.

NOW = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)   # 10 PM in New York (night: the run verdict's rush line), 10 AM in Bangkok


@pytest.fixture
def pinned(demo, monkeypatch):
    """The monitor's clock (demo/data.py's real local_now, at the monitor's place) fixed at NOW."""
    from demo import data as demo_data
    monkeypatch.setitem(demo_data._REAL, "local_now", lambda here=None: NOW.astimezone(ZoneInfo(here.tz if here else "UTC")))
    return NOW


def model_at(tz, value):
    """Open-Meteo's PM2.5 model answer around NOW at tz, the past day and the day ahead: value(k) k hours from now."""
    hour = NOW.astimezone(ZoneInfo(tz)).replace(minute=0)
    times = [hour + timedelta(hours=k) for k in range(-24, 25)]
    return {"hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times], "pm2_5": [value(k) for k in range(-24, 25)]}}


def world_with(mid=ROOF, **changes):
    """The world list with one monitor's row changed."""
    return [{**m, **changes} if m["locationId"] == mid else m for m in WORLD]


def ago(hours):
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def read_of(c, mid=ROOF):
    """What the page posts for a public monitor (its one outdoor row, PM2.5 corrected first, as app.js picks it), and
    the server's answer."""
    row = c.get(f"/api/current?monitor={mid}").get_json()[0]
    body = {"format": "read", "outdoor_pm25": row.get("pm02_corrected", row["pm02"]), "outdoor_humidity": row["rhum"], "outdoor_temp_c": row["atmp"],
            "outdoor_location_id": row["locationId"], "indoor_location_id": None}
    return c.post(f"/api/analyze?monitor={mid}", json=body).get_json()


def test_runner_only(c, net, pinned):
    net["world"], net["model"] = world_with(timestamp=ago(0.1)), model_at("America/New_York", lambda k: 5.0)
    read = read_of(c)
    assert [n["id"] for n in read["summary"]["profiles"]] == ["runner"]
    assert [n["id"] for n in read["profiles"]] == ["runner"]
    assert read["summary"]["profiles"][0]["facts"]["pm_now"] == 4.8   # a fresh reading is the reading now (4.2 raw, 37 % RH)


def test_monitor_chart_past_is_the_model(c, net, pinned):
    """Each monitor's chart draws the model at its own place: a model fetched at the demo home would read 5 in Bangkok."""
    def by_place(params):
        if round(params["latitude"]) == 14:   # Bangkok
            return model_at("Asia/Bangkok", lambda k: 9.0 + k / 10)
        return model_at("America/New_York", lambda k: 5.0 + k / 10)
    net["world"] = [{**m, "timestamp": ago(0.1)} if m["locationId"] in (ROOF, BANGKOK) else m for m in WORLD]
    net["model"] = by_place
    for mid, tz, at_now in ((ROOF, "America/New_York", 5.0), (BANGKOK, "Asia/Bangkok", 9.0)):
        pm = read_of(c, mid)["summary"]["timeline"]["pm"]
        local = NOW.astimezone(ZoneInfo(tz))
        assert pm["source"] == "model" and pm["past"], mid
        assert datetime.fromisoformat(pm["past"][0][0]) < local and pm["past"][-1] == [local.isoformat(), at_now], mid
        assert all(datetime.fromisoformat(t).utcoffset() == local.utcoffset() for t, _ in pm["past"]), mid


def test_monitor_has_no_road(c, net, demo, pinned):
    """The demo home's BQE rush is the home's road: a public monitor has none, in the summary or the run verdict."""
    net["world"] = world_with(timestamp=ago(0.1))
    net["model"] = model_at("America/New_York", lambda k: 30.0 if 1 <= k <= 2 else 5.0)   # a peak ahead: the PM2.5 item
    with demo.app.test_request_context(f"/?monitor={ROOF}"):
        inputs = demo.summary_inputs({}, None, None, None, None, None, 4.2, [], [], demo.local_now())
        assert inputs["road"] is None and inputs["rush"] == []
        assert demo.rush_state(8)["in_rush"] is False and demo.rush_hours() == []
    with demo.app.test_request_context("/"):
        assert demo.rush_state(8)["in_rush"] is True   # a sample keeps the home's road
    read = read_of(c)
    pm = next(i for i in read["summary"]["items"] if i["id"] == "pm")
    assert "cause" not in pm["facts"] and pm["ctx"] == "Peak 12 AM · now 5"   # no ", BQE rush" cause (now: 4.8 corrected)
    # at 10 PM a home with a road says "Run tonight or before 7 AM"; without one, the run verdict has no rush to name
    assert read["profiles"][0]["action"] == "Fine to run" and read["profiles"][0]["why"] == "The air outside is clean."


def test_monitor_pm_timing_names_this_monitor(c, net, pinned):
    """A public monitor without history (the map has no entry for it): the forecast can't be scaled to a day of its
    readings, so it starts from its reading now, and the sentence says so about this monitor, not the demo's balcony."""
    net["world"] = world_with(BANGKOK, timestamp=ago(0.1))
    net["model"] = model_at("Asia/Bangkok", lambda k: 40.0 if 1 <= k <= 2 else 9.0)   # a peak ahead: the PM2.5 item
    pm = next(i for i in read_of(c, BANGKOK)["summary"]["items"] if i["id"] == "pm")
    assert pm["why"].endswith("The forecast is Open-Meteo’s prediction for the wider area, started from this monitor’s reading now.")
    assert "balcony" not in pm["why"] and "your" not in pm["why"] and "scaled" not in pm["why"]


@pytest.mark.parametrize("changes", [{"timestamp": ago(3)}, {"timestamp": ago(0.1), "offline": True}])
def test_stale_public_reading_ignored(c, net, pinned, changes):
    net["world"] = world_with(**changes)
    net["model"] = model_at("America/New_York", lambda k: 30.0 if 1 <= k <= 4 else 5.0)
    read = read_of(c)
    pm = next(i for i in read["summary"]["items"] if i["id"] == "pm")
    assert pm["forecast"] is True and "pm_now" not in pm["facts"]
    assert read["summary"]["profiles"][0]["facts"]["pm_now"] is None
    assert read["profiles"][0]["action"] == "No outdoor reading"


# ── Real history from AirGradient's public map (Task 5b) ──
# The map has its own ids: the roof monitor is MAP_ROOF there, found by its name and place.

MAP_ROOF = 98000001
ROOF_MON = publicmap.find(WORLD, ROOF)


def map_entry(lid, name, north_m=0.0, source="AirGradient"):
    """One monitor of the map's area answer, north_m meters north of the roof monitor."""
    return {"locationId": lid, "locationName": name, "latitude": ROOF_MON["latitude"] + north_m / 111_195,
            "longitude": ROOF_MON["longitude"], "sensorType": "Small Sensor", "pm25": 1, "rhum": 40,
            "measuredAt": "2026-11-09T22:03:39.000Z", "dataSource": source}


def fake_map(monkeypatch, area=None, history=None):
    """requests.get answering the map's area and history calls; returns the list of (url, params) asked for."""
    calls = []

    def get(url, params=None, **kw):
        calls.append((url, dict(params or {})))
        if url.endswith("/measurements/current/area"):
            return FakeResponse({"data": area or [], "total": len(area or [])})
        if url.endswith("/measures/history"):
            return FakeResponse({"data": (history or {}).get(params["measure"], []), "total": None})
        raise AssertionError(f"unexpected call to {url}")
    monkeypatch.setattr(publicmap.requests, "get", get)
    return calls


def test_map_id_matches_by_name_then_distance(monkeypatch):
    named, other, elsewhere = map_entry(1, "Oak & Elm st", 80), map_entry(2, "Roof two", 20), \
        map_entry(3, "Oak & Elm st", 0, source="OpenAQ")
    calls = fake_map(monkeypatch, area=[other, named, elsewhere])
    assert publicmap.map_id(ROOF_MON) == 1   # its name (the world list's has a trailing space), though another is nearer
    (url, params), = calls
    assert url == f"{publicmap.MAP_API}/measurements/current/area" and params["measure"] == "pm25"
    assert params["xmin"] == pytest.approx(ROOF_MON["longitude"] - publicmap.MATCH_BOX)
    assert params["ymax"] == pytest.approx(ROOF_MON["latitude"] + publicmap.MATCH_BOX)
    fake_map(monkeypatch, area=[other, elsewhere, map_entry(4, "Roof four", 60)])
    assert publicmap.map_id(ROOF_MON) == 2   # no name matches: the nearest AirGradient entry
    fake_map(monkeypatch, area=[map_entry(5, "Oak & Elm st", 150), map_entry(6, "Roof six", 120), elsewhere])
    assert publicmap.map_id(ROOF_MON) is None   # none within MATCH_KM
    fake_map(monkeypatch, area=[])
    assert publicmap.map_id(ROOF_MON) is None


def test_history_rows_are_numbers(monkeypatch):
    hist = {"pm25": [{"timebucket": "2026-11-09T21:15:00.000Z", "value": 2.5},
                     {"timebucket": "2026-11-09T21:00:00.000Z", "value": 2.7}],
            "rhum": [{"timebucket": "2026-11-09T21:00:00.000Z", "value": "37.13"},
                     {"timebucket": "2026-11-09T21:15:00.000Z", "value": "38.00"}],
            "atmp": [{"timebucket": "2026-11-09T21:00:00.000Z", "value": "17.45"},
                     {"timebucket": "2026-11-09T21:15:00.000Z", "value": None}],
            "rco2": [{"timebucket": "2026-11-09T21:30:00.000Z", "value": "401.80"}]}
    calls = fake_map(monkeypatch, history=hist)
    rows = publicmap.history(MAP_ROOF, 24)
    assert rows == [{"timestamp": "2026-11-09T21:00:00.000Z", "pm02_corrected": 2.7, "rhum": 37.13, "atmp": 17.45},
                    {"timestamp": "2026-11-09T21:15:00.000Z", "pm02_corrected": 2.5, "rhum": 38.0},
                    {"timestamp": "2026-11-09T21:30:00.000Z", "rco2": 401.8}]
    assert all(isinstance(v, float) for r in rows for k, v in r.items() if k != "timestamp")
    assert sorted(p["measure"] for _, p in calls) == ["atmp", "pm25", "rco2", "rhum"]   # one request per measure
    assert {u for u, _ in calls} == {f"{publicmap.MAP_API}/locations/{MAP_ROOF}/measures/history"}
    assert {p["bucketSize"] for _, p in calls} == {"15m"}
    start, end = (datetime.fromisoformat(calls[0][1][k].replace("Z", "+00:00")) for k in ("start", "end"))
    assert end - start == timedelta(hours=24)
    calls = fake_map(monkeypatch, history=hist)
    publicmap.history(MAP_ROOF, 168)
    assert {p["bucketSize"] for _, p in calls} == {"1h"}


def gp_history(value):
    """The map's hourly PM2.5 for the roof monitor, the 30 hours up to NOW: value(k) k hours before NOW."""
    times = [NOW - timedelta(hours=k) for k in range(30, -1, -1)]
    return {"pm25": [{"timebucket": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "value": value((NOW - t).seconds // 3600 + (NOW - t).days * 24)}
                     for t in times],
            "rhum": [{"timebucket": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "value": "40.50"} for t in times]}


def test_monitor_chart_uses_real_history(c, net, demo, pinned):
    net["world"], net["model"] = world_with(timestamp=ago(0.1)), model_at("America/New_York", lambda k: 5.0)
    net["area"] = [map_entry(MAP_ROOF, "Oak & Elm st", 10)]
    net["history"] = gp_history(lambda k: 2.0 + k / 10)
    tl = read_of(c)["summary"]["timeline"]
    pm, t0, tz = tl["pm"], datetime.fromisoformat(tl["t0"]), ZoneInfo("America/New_York")
    assert "source" not in pm and pm["past"]   # measured, not the model
    want = [[(NOW - timedelta(hours=k)).astimezone(tz).isoformat(), round(2.0 + k / 10, 1)]
            for k in range(30, -1, -1) if NOW - timedelta(hours=k) >= t0]
    assert pm["past"] == want
    # cached per monitor and range: a second read asks the map nothing
    read_of(c)
    assert {f"ag:mapid:m{ROOF}", f"ag:maphist:m{ROOF}:24h"} <= set(demo._cache)
    assert len([u for u in net["calls"] if u.endswith("/measurements/current/area")]) == 1
    assert len([u for u in net["calls"] if u.endswith("/measures/history")]) == len(publicmap.MAP_MEASURES)
    # the History card's rows: the asked span, the fields it charts
    frm, to = NOW - timedelta(hours=6), NOW
    rows = c.get(f"/api/history/{ROOF}?monitor={ROOF}&from={frm.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                 f"&to={to.strftime('%Y-%m-%dT%H:%M:%SZ')}").get_json()
    assert [r["pm02_corrected"] for r in rows] == [round(2.0 + k / 10, 1) for k in range(6, -1, -1)]
    assert all(r["timestamp"].endswith("Z") and r["rhum"] == 40.5 for r in rows)
    assert c.get(f"/api/history/{BANGKOK}?monitor={ROOF}").get_json() == []   # another monitor's id: not this one's


@pytest.mark.parametrize("fail", [
    {"area": 503}, {"area": server_module.requests.ConnectionError("down")}, {"history": 404},
    {"history": server_module.requests.Timeout("slow")}, {"area": []}])
def test_history_falls_back(c, net, pinned, fail):
    net["world"], net["model"] = world_with(timestamp=ago(0.1)), model_at("America/New_York", lambda k: 5.0)
    net["area"] = [map_entry(MAP_ROOF, "Oak & Elm st", 10)]
    net["history"] = gp_history(lambda k: 2.0)
    net.update(fail)
    assert c.get(f"/api/history/{ROOF}?monitor={ROOF}").get_json() == []
    pm = read_of(c)["summary"]["timeline"]["pm"]
    assert pm["source"] == "model" and pm["past"] and all(v == 5.0 for _, v in pm["past"])


def test_history_bug_still_raises(c, net, monkeypatch):
    """Only a failed fetch falls back; a bug in our code still raises."""
    net["area"] = [map_entry(MAP_ROOF, "Oak & Elm st", 10)]
    monkeypatch.setattr(publicmap, "history", lambda *a, **k: {}["a bug"])
    with pytest.raises(KeyError):
        c.get(f"/api/history/{ROOF}?monitor={ROOF}")


def test_map_api_never_called_for_samples(c, net):
    now = datetime.now(timezone.utc)
    for moment in ("", "?moment=clear"):
        hist = c.get(f"/api/history/4202{moment}{'&' if moment else '?'}from={(now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')}"
                     f"&to={now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        assert hist.status_code == 200
        rows = c.get(f"/api/current{moment}").get_json()
        out = next(r for r in rows if r["locationType"] == "outdoor")
        c.post(f"/api/analyze{moment}", json={"format": "read", "outdoor_pm25": out["pm02"], "outdoor_location_id": out["locationId"],
                                              "indoor_location_id": 4201})
    assert net["calls"] == []   # a sample never leaves the machine, the map included


# ── One PM2.5 basis: AirGradient's EPA correction (Task 5b, fix 1) ──
# Pairs checked live on 2026-11-09: the world list's raw pm02 and rhum through corrected_pm, and the map's pm25 for the
# same monitor at the same measuredAt, agreed exactly in every band of the formula.
LIVE_PAIRS = [((21.2, 27), 14.5), ((5.0, 56), 3.5), ((30.3, 55), 17.0), ((38.5, 51), 25.8), ((57.8, 64), 45.7),
              ((87.7, 59), 69.6), ((242.8, 47), 212.3), ((212.3, 53), 169.0), ((382.7, 52), 396.5), ((407.3, 57), 430.7)]


@pytest.mark.parametrize("raw_rh, want", LIVE_PAIRS)
def test_corrected_pm_matches_the_map(raw_rh, want):
    assert summary_rules.corrected_pm(*raw_rh) == want


def test_corrected_pm_has_one_home():
    """The demo's public monitors and every home's neighbors use the same correction (summary.py), not a copy."""
    assert publicmap.corrected_pm is summary_rules.corrected_pm
    assert "def corrected_pm" not in open(publicmap.__file__, encoding="utf-8").read()


def test_corrected_pm_edges():
    corrected_pm = summary_rules.corrected_pm
    assert corrected_pm(0, 50) == 0.0   # a raw 0 stays 0
    assert corrected_pm(1.0, 100) == 0.0   # never below 0
    assert corrected_pm(1.0, 150) == corrected_pm(1.0, 100) == 0.0   # humidity past 100 counts as 100
    assert corrected_pm(10.0, -5) == corrected_pm(10.0, 0) == 11.0   # humidity under 0 counts as 0
    for raw, rh in ((None, 40), (4.2, None), ("x", 40), (float("nan"), 40)):
        assert corrected_pm(raw, rh) is None
    for edge in summary_rules.EPA_BANDS:   # the pieces meet: no jump at a band's edge
        assert abs(corrected_pm(edge - 1e-9, 50) - corrected_pm(edge, 50)) <= 0.1


def test_rows_carry_the_corrected_pm():
    row, = public.current_rows(publicmap.find(WORLD, ROOF))
    assert row["pm02"] == 4.2 and row["pm02_corrected"] == 4.8   # 0.524·4.2 − 0.0862·37 + 5.75
    tagged, = public.current_rows(publicmap.find(WORLD, TAGGED))   # no humidity: nothing to correct with
    assert "pm02_corrected" not in tagged
    picker = {r["locationId"]: r["pm02"] for r in publicmap.nearest(WORLD, 40.78, -73.90)}
    assert picker[ROOF] == 4.8 and picker[TAGGED] == 12.0   # corrected, else raw (as the map shows it)


def test_summary_is_on_the_corrected_basis(c, net, pinned):
    """Raw 12.0 at 37 % reads 8.8 corrected; the map's history is corrected (4.5); the model says 10. The reading now,
    the chart's past and the forecast's calibration all use the corrected numbers."""
    net["world"] = world_with(timestamp=ago(0.1), pm02=12.0)
    net["model"] = model_at("America/New_York", lambda k: 10.0)
    net["area"] = [map_entry(MAP_ROOF, "Oak & Elm st", 10)]
    net["history"] = gp_history(lambda k: 4.5)
    read = read_of(c)
    assert read["summary"]["profiles"][0]["facts"]["pm_now"] == 8.8   # 0.524·12 − 0.0862·37 + 5.75
    pm = read["summary"]["timeline"]["pm"]
    assert "source" not in pm and {v for _, v in pm["past"]} == {4.5}
    k = (4.5 + .5) / (10.0 + .5)   # calibrate_forecast's median ratio against the corrected past
    assert pm["fc"] and {v for _, v in pm["fc"]} == {round(10.0 * k, 1)}


def test_each_range_gets_its_own_cache_key(c, net, demo):
    """The route builds from = now − h a moment before the range is picked: a few seconds late still gets h."""
    net["area"] = [map_entry(MAP_ROOF, "Oak & Elm st", 10)]
    net["history"] = gp_history(lambda k: 2.0)
    for h in (1, 6, 24, 168):
        demo._cache.pop(f"ag:maphist:m{ROOF}:{h}h", None)
        now = datetime.now(timezone.utc)
        frm = now - timedelta(hours=h, seconds=30)
        before = {k for k in demo._cache if k.startswith("ag:maphist:")}
        resp = c.get(f"/api/history/{ROOF}?monitor={ROOF}&from={frm.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                     f"&to={now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        assert resp.status_code == 200
        assert {k for k in demo._cache if k.startswith("ag:maphist:")} - before == {f"ag:maphist:m{ROOF}:{h}h"}, h


def test_map_calls_wait_briefly(c, net, demo, monkeypatch):
    seen = {}
    real = demo.demo_data._REAL["cached"]

    def spy(key, fetch, **kw):
        seen[key] = kw.get("wait")
        return real(key, fetch, **kw)
    monkeypatch.setitem(demo.demo_data._REAL, "cached", spy)
    net["area"] = [map_entry(MAP_ROOF, "Oak & Elm st", 10)]
    c.get(f"/api/history/{ROOF}?monitor={ROOF}")
    assert seen[f"ag:mapid:m{ROOF}"] == seen[f"ag:maphist:m{ROOF}:24h"] == publicmap.MAP_WAIT


def test_monitor_upstreams_keep_to_the_request_budget(c, net, demo, monkeypatch):
    """In the demo a monitor's upstreams run one after another: each waits MONITOR_WAIT at most, and all of a request's
    waits fit in REQUEST_BUDGET (Vercel stops it at 30 s). Here every upstream but the world list times out after
    its whole wait: the page still answers, without them, inside the budget."""
    from demo import data as demo_data
    clock, waits = [0.0], {}
    real = demo_data._REAL["cached"]

    def slow(key, fetch, **kw):
        if key == "ag:world":
            return real(key, fetch, **kw)
        waits[key] = kw["wait"]
        clock[0] += kw["wait"]   # it took its whole wait, then timed out
        raise TimeoutError(key)
    monkeypatch.setattr(demo_data, "monotonic", lambda: clock[0])
    monkeypatch.setitem(demo_data._REAL, "cached", slow)
    monkeypatch.setattr(public, "REQUEST_BUDGET", 2.5 * public.MONITOR_WAIT)   # room for two and a half waits
    ctx = c.get(f"/api/context?monitor={ROOF}")
    assert ctx.status_code == 200 and ctx.get_json()["weather"]["temperature"] is None
    assert set(waits) == {f"wx:m{ROOF}", f"aq:m{ROOF}", "smoke"}
    assert max(waits.values()) <= public.MONITOR_WAIT and clock[0] <= public.REQUEST_BUDGET
    assert sorted(waits.values()) == [0.5 * public.MONITOR_WAIT, public.MONITOR_WAIT, public.MONITOR_WAIT]


def test_a_monitors_name_stays_on_one_line():
    """Owners write their monitors' names: a line break or a bidi override can't fake a line in check_config's output."""
    from publicmap import name_of
    assert name_of({"publicLocationName": "Roof\nSuggested: area\u202e", "locationId": 1}) == "Roof Suggested: area"
    assert name_of({"publicLocationName": " \t ", "locationId": 7}) == "Monitor 7"
