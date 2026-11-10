"""An indoor-only home's outdoor PM2.5 (server.outdoor_source): a nearby public monitor, the area's public monitors, or
the model, with the fallbacks monitor → area → model. Made-up world lists and map answers: no test touches the network."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import requests

import publicmap
import server
from config import load_config
from conftest import REFERENCE_TOML, SAMPLE_PAYLOAD
from summary import corrected_pm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_config  # noqa: E402

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 9, 15, 30, tzinfo=TZ)
HOME = (40.73, -73.95)   # the reference config's place
KM_LAT = 1 / 111.2   # degrees of latitude per km
PINNED = 900002
MODEL_PM = 20   # the model's PM2.5 every hour
PINNED_PM = 5   # what the public monitor's history reads every 15 minutes
AREA_PM = 10   # what each area monitor's history reads


def indoor_only(outdoor_from):
    """The reference config without its outdoor monitor, its outdoor PM2.5 from `outdoor_from`."""
    text = REFERENCE_TOML.replace('outdoor = "backyard"\n', "")
    value = outdoor_from if isinstance(outdoor_from, int) else f'"{outdoor_from}"'
    return load_config({"CONFIG_TOML": text.replace("[sources]\n", f"[sources]\noutdoor_from = {value}\n", 1)})


def utc(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def monitor(lid, km_north, name, age=timedelta(minutes=10), offline=False, model="O-1PP", pm02=10, rhum=50):
    return {"locationId": lid, "latitude": HOME[0] + km_north * KM_LAT, "longitude": HOME[1], "model": model,
            "locationName": name, "publicLocationName": name, "publicPlaceName": f"{name} St",
            "publicContributorName": f"{name} owner", "publicPlaceUrl": f"https://example.org/{lid}",
            "pm02": pm02, "rhum": rhum, "atmp": 12, "timestamp": utc(NOW - age), "offline": offline}


def map_rows(value, hours=24):
    """A day of 15-minute map rows ending now, every one `value`."""
    t, rows = NOW - timedelta(hours=hours), []
    while t <= NOW:
        rows.append({"timestamp": utc(t), "pm02_corrected": value, "rhum": 50, "atmp": 12})
        t += timedelta(minutes=15)
    return rows


@pytest.fixture
def home(monkeypatch, canned):
    """An indoor-only home on made-up upstreams. Returns (set_world, calls): set the world list (None: AirGradient down)
    and see which upstreams were asked."""
    before = server.CFG
    calls = {"world": 0, "map_id": [], "history": []}
    state = {"world": []}
    monkeypatch.setattr(server, "_cache", {})
    monkeypatch.setattr(server, "_inflight", {})
    monkeypatch.setattr(server, "_SOURCE_SEEN", {})
    monkeypatch.setattr(server, "local_now", lambda *a, **k: NOW)
    hours = [NOW.replace(minute=0) + timedelta(hours=h) for h in range(-24, 13)]
    monkeypatch.setattr(server, "get_air_forecast", lambda *a, **k: {t.strftime("%Y-%m-%dT%H:00"): MODEL_PM for t in hours})

    def world():
        calls["world"] += 1
        if state["world"] is None:
            raise requests.ConnectionError("AirGradient down")
        return state["world"]

    def map_id(mon):
        calls["map_id"].append(mon["locationId"])
        return mon["locationId"] + 1_000_000

    def history(mid, hours, now=None, measures=publicmap.MAP_MEASURES):
        calls["history"].append((mid - 1_000_000, hours, tuple(measures)))
        value = PINNED_PM if mid - 1_000_000 == PINNED else AREA_PM
        return [{k: v for k, v in r.items() if k == "timestamp" or k in measures.values()} for r in map_rows(value, hours)]

    monkeypatch.setattr(server, "_fetch_world", world)
    monkeypatch.setattr(publicmap, "map_id", map_id)
    monkeypatch.setattr(publicmap, "history", history)
    monkeypatch.setattr(server, "MODE", "live")
    monkeypatch.setattr(server, "api_get", lambda path, params=None: [{"locationId": 1, "locationType": "indoor", "rco2": 900}])

    def set_world(w):
        state["world"] = w
    yield set_world, calls
    server.use_config(before)


def use(outdoor_from):
    server.use_config(indoor_only(outdoor_from))


def read(client):
    r = client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD})
    assert r.status_code == 200
    return r.get_json()


def test_monitor_online_reads_like_an_own_monitor(home, client):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave"), monitor(2, 4, "Far")])
    src = server.outdoor_source(NOW)
    assert src["kind"] == "monitor" and src["fallback"] is False and src["id"] == PINNED
    assert src["name"] == "Cedar & 2nd Ave" and src["contributor"] == "Cedar & 2nd Ave owner"
    assert src["url"] == f"https://example.org/{PINNED}" and src["distance_km"] == 1.1
    assert src["row"]["pm02_corrected"] == corrected_pm(10, 50) and src["row"]["locationType"] == "outdoor"
    assert src["history"] and src["history"][0]["pm02_corrected"] == PINNED_PM

    current = client.get("/api/current").get_json()
    assert [m["locationType"] for m in current] == ["indoor", "outdoor"]
    out = current[1]
    assert out["locationId"] == PINNED and out["pm02_corrected"] == corrected_pm(10, 50)
    assert out["source"] == {"kind": "monitor", "id": PINNED, "name": "Cedar & 2nd Ave", "street": "Cedar & 2nd Ave St",
                             "contributor": "Cedar & 2nd Ave owner", "url": f"https://example.org/{PINNED}",
                             "distance_km": 1.1, "area_count": 0, "fallback": False}

    r = read(client)
    assert r["outdoor_source"] == {"kind": "monitor", "name": "Cedar & 2nd Ave", "distance_km": 1.1, "area_count": 0,
                                   "fallback": False}
    s = r["summary"]
    runner = next(p for p in s["profiles"] if p["id"] == "runner")
    assert runner["facts"]["pm_now"] == corrected_pm(10, 50)   # the monitor's reading, not what the page posted (4)
    k = (PINNED_PM + .5) / (MODEL_PM + .5)   # calibrated to its history, as with an own monitor
    pm = s["timeline"]["pm"]
    assert pm["fc"] and all(v == round(MODEL_PM * k, 1) for _, v in pm["fc"])
    assert pm["past"] and "source" not in pm   # its measured past, not the model's


def test_monitor_history_served_from_the_map(home, client):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave")])
    frm, to = datetime.now(timezone.utc) - timedelta(hours=6), datetime.now(timezone.utc)
    rows = client.get(f"/api/history/{PINNED}?from={utc(frm)}&to={utc(to)}").get_json()
    assert rows and all(set(r) <= set(server.HIST_KEEP) for r in rows) and "atmp" not in rows[0]
    assert calls["history"][-1][1] == 6   # the 6-hour range


@pytest.mark.parametrize("pinned", [
    monitor(PINNED, 1.1, "Cedar & 2nd Ave", offline=True),
    monitor(PINNED, 1.1, "Cedar & 2nd Ave", age=timedelta(hours=3)),   # stale
])
def test_monitor_not_reporting_falls_back_to_the_area(home, client, pinned):
    set_world, calls = home
    use(PINNED)
    set_world([pinned, monitor(2, 4, "North"), monitor(3, -6, "South")])
    src = server.outdoor_source(NOW)
    assert src["kind"] == "area" and src["fallback"] == "monitor" and src["area_count"] == 2
    assert src["id"] == PINNED and src["name"] == "Cedar & 2nd Ave" and src["row"] is None
    current = client.get("/api/current").get_json()
    assert current[1] == {"locationType": "outdoor", "source": server.source_facts(src)}


def test_monitor_missing_from_the_list_keeps_its_name(home):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave"), monitor(2, 4, "North"), monitor(3, -6, "South")])
    assert server.outdoor_source(NOW)["kind"] == "monitor"
    server._cache.clear()
    set_world([monitor(2, 4, "North"), monitor(3, -6, "South")])   # it stopped reporting: the list drops it
    src = server.outdoor_source(NOW)
    assert src["kind"] == "area" and src["fallback"] == "monitor" and src["name"] == "Cedar & 2nd Ave"


def test_area_scales_the_model(home, client):
    set_world, calls = home
    use("area")
    set_world([monitor(2, 4, "North"), monitor(3, -6, "South"), monitor(4, 30, "Too far")])
    src = server.outdoor_source(NOW)
    assert src["kind"] == "area" and src["area_count"] == 2 and src["fallback"] is False and src["row"] is None
    k = (AREA_PM + .5) / (MODEL_PM + .5)
    assert src["area_factor"] == pytest.approx(k)
    assert all(m[2] == ("pm25",) for m in calls["history"])   # PM2.5 only, one request per monitor
    r = read(client)
    assert r["outdoor_source"] == {"kind": "area", "name": None, "distance_km": None, "area_count": 2, "fallback": False}
    pm = r["summary"]["timeline"]["pm"]
    assert pm["fc"] and all(v == round(MODEL_PM * k, 1) for _, v in pm["fc"])
    assert pm["source"] == "model" and all(v == round(MODEL_PM * k, 1) for _, v in pm["past"])   # the model's, scaled too
    runner = next(p for p in r["summary"]["profiles"] if p["id"] == "runner")
    assert runner["facts"]["pm_now"] is None   # an estimate: no measured "now"


def test_area_on_a_slow_map_resolves_within_the_budget(home, monkeypatch):
    """Every monitor's map id, then every history, is asked at once: three monitors at 0.4 s a request take about
    0.8 s, not 2.4 s, so a 1.5 s budget gives "area" on the first call and the same kind on the next."""
    import time
    set_world, calls = home
    use("area")
    set_world([monitor(2, 4, "North"), monitor(3, -6, "South"), monitor(5, 8, "East")])
    fast_id, fast_history = publicmap.map_id, publicmap.history

    def slow_id(mon):
        time.sleep(.4)
        return fast_id(mon)

    def slow_history(*a, **k):
        time.sleep(.4)
        return fast_history(*a, **k)
    monkeypatch.setattr(publicmap, "map_id", slow_id)
    monkeypatch.setattr(publicmap, "history", slow_history)
    monkeypatch.setattr(server, "SOURCE_BUDGET", 1.5)
    t0 = time.monotonic()
    first = server.outdoor_source(NOW)
    assert time.monotonic() - t0 < 1.5
    assert first["kind"] == "area" and first["area_count"] == 3
    second = server.outdoor_source(NOW)
    assert (second["kind"], second["area_count"]) == ("area", 3)
    assert len(calls["map_id"]) == 3 and len(calls["history"]) == 3   # the second call read the cache


def test_area_counts_only_monitors_reporting_now(home):
    set_world, calls = home
    use("area")
    set_world([monitor(2, 4, "North"), monitor(3, -6, "South"), monitor(5, 2, "Quiet", age=timedelta(hours=3))])
    src = server.outdoor_source(NOW)
    assert src["area_count"] == 2 and 5 not in calls["map_id"]


def test_current_skips_the_monitor_history(home, client):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave")])
    assert client.get("/api/current").get_json()[1]["source"]["kind"] == "monitor"
    assert calls["history"] == []   # /api/current shows the reading only
    read(client)
    assert [c[0] for c in calls["history"]] == [PINNED]   # the read needs it, for the forecast


def test_area_with_one_monitor_is_the_model(home):
    set_world, calls = home
    use("area")
    set_world([monitor(2, 4, "North"), monitor(4, 30, "Too far")])
    src = server.outdoor_source(NOW)
    assert src["kind"] == "model" and src["area_count"] == 0 and src["fallback"] is False


def test_model_fetches_nothing_more(home, client):
    set_world, calls = home
    use("model")
    src = server.outdoor_source(NOW)
    assert src["kind"] == "model"
    r = read(client)
    assert r["outdoor_source"]["kind"] == "model"
    assert r["summary"]["timeline"]["pm"]["source"] == "model"   # the model's past on the chart
    client.get("/api/current")
    assert calls == {"world": 0, "map_id": [], "history": []}


def test_model_reads_as_a_forecast_estimate(home, client):
    """An estimate has no measured "now": the PM2.5 item is a forecast and says where it comes from."""
    use("model")
    s = read(client)["summary"]
    pm = next(i for i in s["items"] if i["id"] == "pm")   # the model's 20 is over the 15 line
    assert pm["forecast"] is True and "pm_now" not in pm["facts"] and " now." not in pm["why"]
    assert pm["why"].endswith("The forecast is Open-Meteo’s prediction for the wider area: an estimate, with no monitor"
                              " outside to check it against.")
    assert "your outdoor monitor" not in str(s) and "config" not in str(s).lower()


def test_fallback_names_the_chosen_monitor(home, client):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave", offline=True)])   # no area monitors: the model
    pm = next(i for i in read(client)["summary"]["items"] if i["id"] == "pm")
    assert "Cedar & 2nd Ave isn’t reporting, so this is an estimate for your area. The forecast is Open-Meteo’s" in pm["why"]


@pytest.mark.parametrize("chosen", [PINNED, "area"])
def test_world_list_down_is_the_model(home, client, chosen):
    set_world, calls = home
    use(chosen)
    set_world(None)
    src = server.outdoor_source(NOW)
    # the chosen monitor may be reporting: it's AirGradient's list that didn't answer, and the fallback says so
    assert src["kind"] == "model" and src["fallback"] == ("list" if chosen == PINNED else False)
    assert client.get("/api/current").status_code == 200
    assert read(client)["outdoor_source"]["kind"] == "model"


def test_world_list_down_doesnt_say_the_chosen_monitor_isnt_reporting(home, client):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave")])
    assert server.outdoor_source(NOW)["kind"] == "monitor"   # seen once: its name is known
    set_world(None)
    server._cache.clear()   # past the world list's keep: nothing cached to fall back on
    src = server.outdoor_source(NOW)
    assert src["kind"] == "model" and src["fallback"] == "list" and src["name"] == "Cedar & 2nd Ave"
    pm = next(i for i in read(client)["summary"]["items"] if i["id"] == "pm")
    assert "AirGradient didn’t answer, so this is an estimate for your area." in pm["why"]
    assert "isn’t reporting" not in pm["why"]


def test_map_down_falls_back_to_the_model(home, monkeypatch):
    set_world, calls = home
    use(PINNED)
    set_world([monitor(PINNED, 1.1, "Cedar & 2nd Ave", offline=True), monitor(2, 4, "North"), monitor(3, -6, "South")])

    def down(mon):
        raise requests.ConnectionError("map down")
    monkeypatch.setattr(publicmap, "map_id", down)
    src = server.outdoor_source(NOW)
    assert src["kind"] == "model" and src["fallback"] == "monitor" and src["name"] == "Cedar & 2nd Ave"


def test_two_monitor_home_has_no_source(client, monkeypatch):
    monkeypatch.setattr(server, "MODE", "live")
    own = [{"locationId": 1, "locationType": "indoor"}, {"locationId": 2, "locationType": "outdoor"}]
    monkeypatch.setattr(server, "_cache", {})
    monkeypatch.setattr(server, "api_get", lambda path, params=None: own)
    assert server.outdoor_source() is None
    assert client.get("/api/current").get_json() == own
    assert "outdoor_source" not in read(client)


def test_a_dropped_monitor_name_does_not_stay(home):
    import phrases
    use(PINNED)
    assert phrases.LIMIT_FACTS["outdoor"] == phrases.PLACE_DEFAULTS["outdoor"]


# ── check_config.py: the chosen source, and --suggest ──

EXAMPLE = (Path(__file__).resolve().parent.parent / "config.example.toml").read_text(encoding="utf-8")
EX = (39.95, -75.16)   # the example config's place


def ex_monitor(lid, km_north, name, age=timedelta(minutes=10), offline=False, model="O-1PP"):
    now = datetime.now(timezone.utc)
    return {"locationId": lid, "latitude": EX[0] + km_north * KM_LAT, "longitude": EX[1], "model": model,
            "locationName": name, "publicLocationName": name, "pm02": 8, "rhum": 50,
            "timestamp": (now - age).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "offline": offline}


def check(tmp_path, capsys, monkeypatch, world, text=EXAMPLE, argv=()):
    asked = []

    def fetch():
        asked.append(1)
        return world
    monkeypatch.setattr(check_config.publicmap, "fetch_world", fetch)
    (tmp_path / "config.toml").write_text(text, encoding="utf-8")
    code = check_config.main(list(argv), {}, tmp_path)
    return code, capsys.readouterr().out, len(asked)


def ex_indoor_only(value):
    text = "\n".join(l for l in EXAMPLE.splitlines() if not l.startswith("outdoor =")) + "\n"
    return text.replace("[sources]\n", f"[sources]\noutdoor_from = {value}\n", 1)


def test_suggest_nearest_within_3_km(tmp_path, capsys, monkeypatch):
    world = [ex_monitor(11, 2.5, "Near"), ex_monitor(12, 1.2, "Nearer"), ex_monitor(13, 0.5, "Off", offline=True)]
    code, out, asked = check(tmp_path, capsys, monkeypatch, world, argv=["--suggest"])
    assert code == 0 and asked == 1
    assert "Suggested outdoor_from = 12: Nearer, 1.2 km away" in out


def test_suggest_lists_the_monitors_it_weighed_before_its_choice(tmp_path, capsys, monkeypatch):
    """Up to check_config.SUGGEST_LIST reporting now within 15 km, nearest first, with distance, corrected PM2.5 and
    id; offline, gone-quiet and far monitors left out; one world-list call."""
    world = [ex_monitor(10 + i, km, f"M{i}") for i, km in enumerate((6, 1.2, 4, 2.5, 9, 14))]
    world += [ex_monitor(20, 0.5, "Off", offline=True), ex_monitor(21, 0.8, "Quiet", age=timedelta(hours=3)),
              ex_monitor(22, 20, "Far"), {**ex_monitor(23, 3.5, "Dry"), "rhum": None}]
    code, out, asked = check(tmp_path, capsys, monkeypatch, world, argv=["--suggest"])
    lines = out.splitlines()
    head = lines.index("Public outdoor monitors reporting now within 15 km, nearest first (the 5 nearest of 7):")
    pm = corrected_pm(8, 50)
    assert lines[head + 1:head + 7] == [
        f"  M1, 1.2 km, corrected PM2.5 {pm:.1f} µg/m³, id 11",
        f"  M3, 2.5 km, corrected PM2.5 {pm:.1f} µg/m³, id 13",
        "  Dry, 3.5 km, no corrected PM2.5 (no humidity reading), id 23",
        f"  M2, 4.0 km, corrected PM2.5 {pm:.1f} µg/m³, id 12",
        f"  M0, 6.0 km, corrected PM2.5 {pm:.1f} µg/m³, id 10",
        "Suggested outdoor_from = 11: M1, 1.2 km away, the nearest public outdoor monitor reporting now "
        "(within 3 km, its readings stand for your street).",
    ]
    assert code == 0 and asked == 1


def test_suggest_lists_nothing_without_a_monitor_nearby(tmp_path, capsys, monkeypatch):
    out = check(tmp_path, capsys, monkeypatch, [ex_monitor(11, 40, "Far")], argv=["--suggest"])[1]
    assert "Public outdoor monitors reporting now" not in out and 'Suggested outdoor_from = "model"' in out


def test_suggest_area(tmp_path, capsys, monkeypatch):
    world = [ex_monitor(11, 5, "A"), ex_monitor(12, -9, "B")]
    out = check(tmp_path, capsys, monkeypatch, world, argv=["--suggest"])[1]
    assert 'Suggested outdoor_from = "area"' in out and "2 public outdoor monitors within 15 km" in out


def test_suggest_model(tmp_path, capsys, monkeypatch):
    world = [ex_monitor(11, 5, "A"), ex_monitor(12, 40, "Far")]
    out = check(tmp_path, capsys, monkeypatch, world, argv=["--suggest"])[1]
    assert 'Suggested outdoor_from = "model"' in out and "1 public outdoor monitor within 15 km" in out


def test_suggest_without_network_is_a_note(tmp_path, capsys, monkeypatch):
    def down():
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(check_config.publicmap, "fetch_world", down)
    (tmp_path / "config.toml").write_text(EXAMPLE, encoding="utf-8")
    code = check_config.main(["--suggest"], {}, tmp_path)
    out = capsys.readouterr().out
    assert code == 0 and "didn't answer (ConnectionError)" in out and "Config OK" in out


def test_pinned_offline_8_days_is_flagged_with_the_next_best(tmp_path, capsys, monkeypatch):
    world = [ex_monitor(11, 1, "Gone quiet", age=timedelta(days=8), offline=True), ex_monitor(12, 2, "Next")]
    code, out, _ = check(tmp_path, capsys, monkeypatch, world, text=ex_indoor_only(11))
    assert code == 0 and "public monitor 11 (Gone quiet) has not reported for 8 days" in out
    assert "The next best: Suggested outdoor_from = 12: Next, 2.0 km away" in out and "Config OK" in out


def test_pinned_reporting(tmp_path, capsys, monkeypatch):
    code, out, asked = check(tmp_path, capsys, monkeypatch, [ex_monitor(11, 1, "Here")], text=ex_indoor_only(11))
    assert code == 0 and asked == 1 and "Outdoor source: public monitor 11 (Here, 1.0 km away) is reporting." in out


def test_pinned_absent_gets_the_next_best(tmp_path, capsys, monkeypatch):
    world = [ex_monitor(12, 5, "A"), ex_monitor(13, -9, "B")]
    out = check(tmp_path, capsys, monkeypatch, world, text=ex_indoor_only(11))[1]
    assert "public monitor 11 is not in AirGradient's public list" in out and 'Suggested outdoor_from = "area"' in out


def test_model_and_two_monitor_homes_ask_nothing(tmp_path, capsys, monkeypatch):
    assert check(tmp_path, capsys, monkeypatch, [], text=ex_indoor_only('"model"'))[2] == 0
    assert check(tmp_path, capsys, monkeypatch, [])[2] == 0


def test_suggest_and_area_count_skip_a_monitor_gone_quiet(tmp_path, capsys, monkeypatch):
    """The server's rule (offline, or older than publicmap.STALE_READING) for check_config too."""
    world = [ex_monitor(11, 0.5, "Quiet", age=timedelta(hours=3)), ex_monitor(12, 2, "Live"), ex_monitor(13, -5, "Other")]
    out = check(tmp_path, capsys, monkeypatch, world, argv=["--suggest"])[1]
    assert "Suggested outdoor_from = 12: Live, 2.0 km away" in out
    out = check(tmp_path, capsys, monkeypatch, [ex_monitor(11, 3, "A"), ex_monitor(12, 5, "B", age=timedelta(hours=3))],
                text=ex_indoor_only('"area"'))[1]
    assert "only 1 public outdoor monitor within 15 km" in out


def test_pinned_gone_quiet_is_not_reporting(tmp_path, capsys, monkeypatch):
    world = [ex_monitor(11, 1, "Quiet", age=timedelta(hours=3))]
    out = check(tmp_path, capsys, monkeypatch, world, text=ex_indoor_only(11))[1]
    assert "public monitor 11 (Quiet) is not reporting now" in out and "is reporting." not in out


def test_pinned_indoor_or_without_position(tmp_path, capsys, monkeypatch):
    code, out, _ = check(tmp_path, capsys, monkeypatch, [ex_monitor(11, 1, "Kitchen", model="I-9PSL")],
                         text=ex_indoor_only(11))
    assert code == 1 and "public monitor 11 is not an outdoor monitor" in out
    unplaced = {**ex_monitor(11, 1, "Somewhere"), "latitude": None, "longitude": None}
    code, out, _ = check(tmp_path, capsys, monkeypatch, [unplaced, ex_monitor(12, 2, "Next")], text=ex_indoor_only(11))
    assert code == 0 and "public monitor 11 has no position in AirGradient's public list" in out
    assert "The next best: Suggested outdoor_from = 12" in out and "not an outdoor monitor" not in out


# ── A home with one monitor reads only its own monitor's rows, whatever else the token sees ──
TOKEN_SEES = [{"locationId": 1, "locationType": "indoor", "rco2": 900}, {"locationId": 2, "locationType": "outdoor", "pm02": 30}]


def test_indoor_only_current_drops_the_tokens_outdoor_rows(home, client, monkeypatch):
    use("model")
    monkeypatch.setattr(server, "api_get", lambda path, params=None: [dict(r) for r in TOKEN_SEES])
    current = client.get("/api/current").get_json()
    assert [m.get("locationId") for m in current] == [1, None]   # the indoor row, then the source entry
    assert current[1]["source"]["kind"] == "model"


def test_indoor_only_summary_ignores_a_posted_outdoor_id(home, client, monkeypatch):
    use("model")
    asked = []
    monkeypatch.setattr(server, "history_points", lambda lid, now, hours=24: asked.append(lid) or [])
    client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_location_id": 1, "outdoor_location_id": 2})
    assert 2 not in asked


def outdoor_only():
    return load_config({"CONFIG_TOML": REFERENCE_TOML.replace('indoor = "apartment"\n', "")})


def test_outdoor_only_current_drops_the_tokens_indoor_rows(client, monkeypatch):
    before = server.CFG
    server.use_config(outdoor_only())
    try:
        monkeypatch.setattr(server, "MODE", "live")
        monkeypatch.setattr(server, "_cache", {})
        monkeypatch.setattr(server, "api_get", lambda path, params=None: [dict(r) for r in TOKEN_SEES])
        assert client.get("/api/current").get_json() == [TOKEN_SEES[1]]
    finally:
        server.use_config(before)


def test_outdoor_only_summary_reads_no_indoor_history(client, monkeypatch):
    before = server.CFG
    server.use_config(outdoor_only())
    try:
        asked = []
        monkeypatch.setattr(server, "history_points", lambda lid, now, hours=24: asked.append(lid) or [])
        client.post("/api/analyze", json={"format": "read", **SAMPLE_PAYLOAD, "indoor_location_id": 1, "outdoor_location_id": 2})
    finally:
        server.use_config(before)
    assert 1 not in asked and 2 in asked   # the outdoor monitor's history only (history_points(None) reads nothing)


def test_two_monitor_home_keeps_every_row(client, monkeypatch):
    monkeypatch.setattr(server, "MODE", "live")
    monkeypatch.setattr(server, "_cache", {})
    monkeypatch.setattr(server, "api_get", lambda path, params=None: [dict(r) for r in TOKEN_SEES])
    assert client.get("/api/current").get_json() == TOKEN_SEES
