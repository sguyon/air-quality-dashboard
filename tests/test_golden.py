"""The reference home's page, characterized: the summary and /api/context on made-up inputs must stay exactly as they were.

Regenerate only on purpose: UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""
import json
import os
from pathlib import Path

import pytest

import server
from fixtures import golden_inputs as gi

GOLDEN = Path(__file__).parent / "fixtures" / "golden_reference.json"
MOMENTS = {"morning": gi.MORNING, "evening": gi.EVENING}


def run(monkeypatch, now):
    gi.install(server, monkeypatch, now)
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "test-key")   # the reference home has every source on
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        read = c.post("/api/analyze", json={"format": "read", **gi.PAYLOAD}).get_json()
        ctx = c.get("/api/context").get_json()
    return json.loads(json.dumps({"read": read, "context": ctx}))


def test_reference_output_unchanged(monkeypatch):
    out = {name: run(monkeypatch, now) for name, now in MOMENTS.items()}
    # the one addition since the golden was taken: the road flag for the page, next to the old "bqe" text
    for o in out.values():
        assert o["context"].pop("road") == {"name": "BQE", "toward": True}
        assert o["context"].pop("status") == {"pollen": "ok", "smoke": "ok", "road": "ok", "nearby": "ok"}
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("golden written")
    assert out == json.loads(GOLDEN.read_text(encoding="utf-8"))


# ── Someone else's config: the home, the road and the limits come from it ──

def config_from(**changes):
    """The reference config with whole sections replaced (None drops the section)."""
    from conftest import REFERENCE_TOML
    import tomllib
    raw = tomllib.loads(REFERENCE_TOML)
    for section, value in changes.items():
        if value is None:
            raw.pop(section, None)
        else:
            raw[section] = value

    def toml(v):
        return json.dumps(v)   # strings, numbers, booleans and lists read the same in TOML
    lines = []
    for section, table in raw.items():
        if section == "pollen_seasons":
            continue
        lines.append(f"[{section}]")
        lines += [f"{k} = {toml(v)}" for k, v in table.items()]
    for s in raw.get("pollen_seasons", []):
        lines.append("[[pollen_seasons]]")
        lines += [f"{k} = {toml(v)}" for k, v in s.items()]
    from config import load_config
    return load_config({"CONFIG_TOML": "\n".join(lines)})


@pytest.fixture
def use_config():
    before = server.CFG
    yield server.use_config
    server.use_config(before)


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


TESTVILLE = {"name": "Testville", "lat": 41.0, "lon": -74.0, "timezone": "America/New_York",
             "indoor": "kitchen", "outdoor": "yard"}


def test_no_profiles_no_road(monkeypatch, use_config):
    use_config(config_from(place=TESTVILLE, road=None,
                           profiles={"toddler": False, "sinus": False, "runner": False}))
    for now in MOMENTS.values():
        out = run(monkeypatch, now)
        read, ctx = out["read"], out["context"]
        assert read["profiles"] == [] and read["summary"]["profiles"] == []
        assert ctx.get("road") in (None, {"toward": False})
        assert all(f["bqe_toward"] in (False, None) for f in ctx["forecast"])
        said = [s for s in strings(out) if "rush" in s.lower() or "BQE" in s or "Greenpoint" in s]
        assert said == []


def test_place_name_flows_into_text(monkeypatch, use_config):
    use_config(config_from(place=TESTVILLE, road={"name": "I-95", "route": "static/bqe.json",
                                                  "rush": [[7, 10, "morning"], [16, 20, "evening"]], "toward": [80, 200]}))
    morning, evening = run(monkeypatch, gi.MORNING), run(monkeypatch, gi.EVENING)
    runner = next(n for n in morning["read"]["profiles"] if n["id"] == "runner")
    assert runner["why"] == "The I-95 rush runs until 10 AM, with the wind toward Testville."
    pm = next(i for i in evening["read"]["summary"]["items"] if i["id"] == "pm")
    assert "I-95 rush" in pm["ctx"] and "I-95 rush-hour fumes" in pm["why"]
    assert morning["context"]["road"] == {"name": "I-95", "toward": True}
    assert [s for o in (morning, evening) for s in strings(o) if "Greenpoint" in s or "BQE" in s] == []


def test_toward_arc_crossing_north(use_config):
    use_config(config_from(road={"name": "Ring Rd", "route": "static/bqe.json",
                                 "rush": [[7, 10, "morning"]], "toward": [300, 20]}))
    assert server.road_traffic(8, 350)["toward"] is True
    assert server.road_traffic(8, 10)["toward"] is True
    assert server.road_traffic(8, 135)["toward"] is False


def test_limits_come_from_config(monkeypatch, use_config):
    use_config(config_from(limits={"co2": 1000, "pm": 15, "pm_high": 35, "rh_dry": 30, "rh_damp": 60,
                                   "rh_stop": 55, "pollen": 3}))
    co2 = next(i for i in run(monkeypatch, gi.MORNING)["read"]["summary"]["items"] if i["id"] == "co2")
    assert co2["ctx"].startswith("24% over the 1000 limit") and co2["why"].startswith("Above 1000 ")


def test_pollen_limit_reaches_the_read(monkeypatch, use_config):
    # tree pollen is 4 of 5 in the inputs: under a limit of 5, no pollen action anywhere
    use_config(config_from(limits={"co2": 800, "pm": 15, "pm_high": 35, "rh_dry": 30, "rh_damp": 60,
                                   "rh_stop": 55, "pollen": 5}))
    read = run(monkeypatch, gi.MORNING)["read"]
    assert "Limit time outside" not in [a["text"] for a in read["also"]]
    assert "pollen" not in [i["id"] for i in read["summary"]["items"]]


def test_appliances_come_from_config(monkeypatch, use_config):
    use_config(config_from(home={"appliances": ["ac_dry"]}))
    rh = next(i for i in run(monkeypatch, gi.MORNING)["read"]["summary"]["items"] if i["id"] == "rh")
    assert rh["action"]["text"] == "Run the AC’s dry mode" and "works too" not in rh["why"]


def test_road_without_rush_hours(monkeypatch, use_config):
    use_config(config_from(road={"name": "Ring Rd", "route": "static/bqe.json", "rush": [], "toward": [80, 200]}))
    for now in (gi.MORNING, gi.EVENING, gi.MORNING.replace(hour=22, minute=30)):
        read = run(monkeypatch, now)["read"]
        assert read["summary"] is not None and "rush" not in json.dumps(read)
