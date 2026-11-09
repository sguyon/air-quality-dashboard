"""The demo: made-up data at three fixed moments, no outside calls. The moments are also the project's fixtures:
each one's summary is pinned here, so a change to the rules or the page that changes the story shows up.

The server reads its config at import, so these tests reload it with DEMO=1 and reload it again afterwards
(the reference config, from conftest) for the other test files."""
import importlib
import json
import math
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

import server as server_module

MOMENTS = ("rush", "clear", "humid")
ROOT = Path(__file__).resolve().parent.parent


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
def c(demo):
    with demo.app.test_client() as client:
        yield client


def pick(m, *keys):
    return next((m[k] for k in keys if m.get(k) is not None), None)


def payload(current):
    """What the page posts to /api/analyze, built from /api/current the way app.js's readPayload does."""
    i = next(m for m in current if m["locationType"] == "indoor")
    o = next(m for m in current if m["locationType"] == "outdoor")
    return {"format": "read",
            "indoor_pm25": pick(i, "pm02_corrected", "pm02"), "indoor_co2": pick(i, "rco2_corrected", "rco2"),
            "indoor_humidity": pick(i, "rhum", "rhum_corrected"), "indoor_temp_c": pick(i, "atmp", "atmp_corrected"),
            "outdoor_pm25": pick(o, "pm02_corrected", "pm02"), "outdoor_humidity": pick(o, "rhum_corrected", "rhum"),
            "outdoor_temp_c": pick(o, "atmp_corrected", "atmp"),
            "indoor_location_id": i["locationId"], "outdoor_location_id": o["locationId"]}


def read(c, moment):
    current = c.get(f"/api/current?moment={moment}").get_json()
    return c.post(f"/api/analyze?moment={moment}", json=payload(current)).get_json()


def week_url(moment, location_id):
    """The page's 7-day history request, ending at the moment's time."""
    from demo.moments import MOMENTS as M
    to = M[moment].at.astimezone(timezone.utc)
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return f"/api/history/{location_id}?from={iso(to - timedelta(hours=168))}&to={iso(to)}&moment={moment}"


def needs_of(summary):
    return {n["id"]: n for n in summary["needs"]}


def test_no_outside_calls(demo, c, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the demo called the network")
    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)
    for m in MOMENTS:
        assert c.get(f"/?moment={m}").status_code == 200
        current = c.get(f"/api/current?moment={m}")
        assert current.status_code == 200
        assert c.get(f"/api/context?moment={m}").status_code == 200
        nearby = c.get(f"/api/neighborhood?moment={m}")
        assert nearby.status_code == 200 and len(nearby.get_json()) >= 8
        for mon in current.get_json():
            hist = c.get(week_url(m, mon["locationId"]))
            assert hist.status_code == 200 and len(hist.get_json()) > 1000   # a week of 5-minute readings
        r = c.post(f"/api/analyze?moment={m}", json=payload(current.get_json()))
        assert r.status_code == 200 and r.get_json()["summary"] is not None


def test_rush_story(c):
    r = read(c, "rush")
    s = r["summary"]
    items = {i["id"]: i for i in s["items"]}
    # three items at most: PM2.5, CO₂ and pollen lead; humidity (63%) is the Also line
    assert set(items) == {"pm", "co2", "pollen"}
    assert "Humidity inside 63%" in s["also"]
    # the tension: stale inside, dirty outside, so air out after the rush
    co2 = items["co2"]
    assert co2["action"]["text"] == "Open a window for 10 min"
    assert co2["action"]["when"] == "after 11 AM"
    assert datetime.fromisoformat(co2["action"]["when_end"]).hour >= 10
    assert co2["facts"]["since"] == "yesterday 9 PM"
    # outdoor PM2.5 rises with the BQE rush, peaks under the 35 line, and is clean again from 11
    pm = items["pm"]
    assert pm["forecast"] is True and pm["facts"]["cause"] == "BQE rush" and pm["facts"]["pm_now"] == 22
    assert 30 <= int(pm["num"]) <= 35
    assert pm["action"]["when"] == "until 11 AM"
    assert items["pollen"]["num"] == "4" and items["pollen"]["facts"]["pollen_type"] == "tree"
    needs = needs_of(s)
    # the runner: run after the dirty stretch ends, at the same 11 AM the windows wait for
    assert needs["runner"]["ok"] is False and needs["runner"]["state"] == "Run after 11 AM"
    # the toddler: stale now, after a stale night that peaked about 1,400
    assert needs["toddler"]["ok"] is False and needs["toddler"]["state"] == "Stale indoors"
    assert 1350 <= needs["toddler"]["facts"]["night_peak"] <= 1450 and "last night" in needs["toddler"]["why"].lower()
    assert needs["sinus"]["state"] == "Damp + pollen"
    ctx = c.get("/api/context?moment=rush").get_json()
    assert ctx["road"] == {"name": "BQE", "toward": True}
    assert ctx["status"] == {"pollen": "ok", "smoke": "ok", "road": "ok", "nearby": "ok"}


def test_rush_nearby_higher_near_the_road(c):
    route = json.loads((ROOT / "static" / "bqe.json").read_text())

    def to_road(n):
        return min(math.hypot((x - n["longitude"]) * 111.32 * math.cos(math.radians(n["latitude"])), (y - n["latitude"]) * 111.32) for x, y in route)
    own = {m["locationId"] for m in c.get("/api/current?moment=rush").get_json()}
    nb = [n for n in c.get("/api/neighborhood?moment=rush").get_json() if n["locationId"] not in own]
    near = [n["pm02"] for n in nb if to_road(n) < 0.6]
    far = [n["pm02"] for n in nb if to_road(n) > 1.5]
    assert near and far and min(near) > max(far)


def test_clear_story(c):
    r = read(c, "clear")
    s = r["summary"]
    assert s["items"] == [] and s["all_clear"] is True
    assert all(n["ok"] is True for n in s["needs"]), s["needs"]
    assert all(n["tone"] == "good" for n in r["needs"]), r["needs"]
    assert c.get("/api/context?moment=clear").get_json()["road"]["toward"] is False


def test_humid_story(c):
    r = read(c, "humid")
    s = r["summary"]
    assert [i["id"] for i in s["items"]] == ["rh"]
    rh = s["items"][0]
    assert rh["num"] == "66"
    assert rh["action"]["text"] == "Run the dehumidifier"   # the rules' action; its explanation names the AC's dry mode
    assert "AC’s dry mode" in rh["why"] and "Outside is wetter (92%)" in rh["why"]
    needs = needs_of(s)
    assert needs["sinus"]["ok"] is False and needs["sinus"]["state"] == "Too damp"
    assert needs["toddler"]["ok"] is True and needs["runner"]["ok"] is True
    ctx = c.get("/api/context?moment=humid").get_json()
    assert ctx["weather"]["weather_code"] >= 61   # rain


def test_moment_urls_differ_and_cache(c):
    rush = c.get("/api/context?moment=rush")
    clear = c.get("/api/context?moment=clear")
    assert rush.get_json() != clear.get_json()
    for resp in (rush, clear, c.get("/?moment=clear"), c.get("/api/current?moment=humid")):
        assert resp.headers["Cache-Control"] == "public, max-age=300, s-maxage=86400"
    nope = c.get("/api/context?moment=nope")
    assert nope.status_code == 200 and nope.get_json() == rush.get_json()
    assert c.get("/api/context").get_json() == rush.get_json()   # no moment: the default


def test_page_carries_the_clock(c):
    html = c.get("/?moment=humid").get_data(as_text=True)
    app = json.loads(html.split("window.APP = ", 1)[1].split(";</script>", 1)[0])
    assert app["now"]["moment"] == "humid"
    assert app["now"]["at"].startswith("2026-10-22T20:30:00")
    assert [m["key"] for m in app["now"]["moments"]] == ["rush", "clear", "humid"]
    assert [m["label"] for m in app["now"]["moments"]] == ["Morning rush", "All clear", "Humid evening"]
    assert app["place"]["name"] == "Williamsburg, Brooklyn NY"
    assert app["road"]["toward"] == [66, 207]
    assert "X-Robots-Tag" not in c.get("/").headers


def test_deterministic(c):
    for url in ("/api/current?moment=rush", "/api/context?moment=clear", "/api/neighborhood?moment=humid"):
        assert c.get(url).get_data() == c.get(url).get_data()
    assert json.dumps(read(c, "rush"), sort_keys=True) == json.dumps(read(c, "rush"), sort_keys=True)


def test_mode(demo):
    assert demo.MODE == "demo"
    cfg = demo.CFG
    assert demo.server_mode(cfg, "") == "demo"
    reference = type(cfg)(**{**cfg.__dict__, "demo": False})
    assert demo.server_mode(reference, "tok") == "live"
    assert demo.server_mode(reference, "") == "no_token"


def test_fresh_copy_opens_as_the_demo(demo, tmp_path):
    """No config and no token: the demo. A config without a token stays that config (Task 10 says what's missing)."""
    shutil.copytree(ROOT / "demo", tmp_path / "demo")
    (tmp_path / "static").mkdir()
    shutil.copy(ROOT / "static" / "bqe.json", tmp_path / "static" / "bqe.json")
    cfg = demo.startup_config({}, tmp_path)
    assert cfg.demo is True and cfg.place.name == "Williamsburg, Brooklyn NY"
    assert demo.startup_config({"AIRGRADIENT_TOKEN": "x"}, tmp_path) is None
    (tmp_path / "config.toml").write_text((ROOT / "config.example.toml").read_text())
    assert demo.startup_config({}, tmp_path).demo is False
