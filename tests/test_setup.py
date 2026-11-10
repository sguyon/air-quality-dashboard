"""scripts/setup.py: the answers become a config.toml, the token goes into .env unseen, and --live asks the running page.
Made-up geocoders, AirGradient lists and pages: no test touches the network."""
import json
import os
import stat
import sys
import threading
import tomllib
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path

import pytest
import requests

from config import load_config, public_view

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import setup  # noqa: E402

KM_LAT = 1 / 111.2   # degrees of latitude per km
DENVER = (39.7403115, -104.9753154)


def osm(lat, lon, name="", category="building", **address):
    return {"lat": str(lat), "lon": str(lon), "category": category, "name": name, "address": address}


US = {"country": "United States", "country_code": "us"}
OGDEN = [osm(*DENVER, "Ogden Theatre", "amenity", amenity="Ogden Theatre", house_number="935", road="East Colfax Avenue",
             neighbourhood="Swallow Hill Historic District", city="Denver", state="Colorado", postcode="80218",
             **{"ISO3166-2-lvl4": "US-CO"}, **US)]
TIMES_SQUARE = [
    osm(40.7570095, -73.9859724, "Times Square", "highway", road="Times Square", neighbourhood="Manhattan Community Board 5",
        suburb="Manhattan", city="New York", state="New York", postcode="10036", **{"ISO3166-2-lvl4": "US-NY"}, **US),
    osm(40.7572614, -73.9858998, "Times Square", "place", square="Times Square", suburb="Manhattan", city="New York",
        state="New York", postcode="10036", **{"ISO3166-2-lvl4": "US-NY"}, **US)]
FIFTH_AVE = [osm(40.7484421, -73.9856589, "", "building", house_number="350", road="5th Avenue", neighbourhood="Koreatown",
                 suburb="Manhattan", city="New York", state="New York", postcode="10118", **{"ISO3166-2-lvl4": "US-NY"}, **US)]
BACK_BAY = [osm(42.3503, -71.0753, "", "building", house_number="200", road="Clarendon Street", neighbourhood="Copley",
                suburb="Back Bay", city="Boston", state="Massachusetts", postcode="02116-5021",
                **{"ISO3166-2-lvl4": "US-MA"}, **US)]
MARAIS = [osm(48.8589, 2.3618, "Le Marais", "place", suburb="Le Marais", city="Paris", state="Ile-de-France",
              postcode="75004", country="France", country_code="fr", **{"ISO3166-2-lvl4": "FR-IDF"})]
TWO_STATES = [osm(41.92, -87.70, "Logan Square", "place", suburb="Logan Square", city="Chicago", state="Illinois",
                  **{"ISO3166-2-lvl4": "US-IL"}, **US),
              osm(39.95, -75.17, "Logan Square", "place", suburb="Logan Square", city="Philadelphia", state="Pennsylvania",
                  **{"ISO3166-2-lvl4": "US-PA"}, **US)]
OM_LOGAN = [{"name": "Logan Square", "latitude": 41.92337, "longitude": -87.69922, "country_code": "US", "admin1": "Illinois",
             "admin3": "Chicago", "timezone": "America/Chicago", "postcodes": ["60647"]},
            {"name": "Logan Square", "latitude": 39.95569, "longitude": -75.17054, "country_code": "US",
             "admin1": "Pennsylvania", "admin3": "City of Philadelphia", "timezone": "America/New_York"},
            {"name": "Logan Square Rock", "latitude": 43.0, "longitude": -122.7, "country_code": "US", "admin1": "Oregon",
             "timezone": "America/Los_Angeles"}]
TIMEZONES = {(39.74, -104.98): "America/Denver", (39.75, -104.98): "America/Denver", (40.76, -73.99): "America/New_York", (40.75, -73.99): "America/New_York",
             (42.35, -71.08): "America/New_York", (48.86, 2.36): "Europe/Paris", (40.71, -74.01): "America/New_York"}


class Geo:
    """The two geocoders and Open-Meteo's timezone, made up. Each request is kept in `calls` (url, params)."""

    def __init__(self, nominatim=None, open_meteo=None, reverse=None, down=()):
        self.nominatim, self.open_meteo, self.reverse, self.down, self.calls = nominatim or [], open_meteo or [], reverse, down, []

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if any(url.startswith(d) for d in self.down):
            raise requests.ConnectionError("down")
        if url == setup.NOMINATIM_SEARCH:
            return self.nominatim
        if url == setup.NOMINATIM_REVERSE:
            return self.reverse
        if url == setup.OPEN_METEO_SEARCH:
            return {"results": self.open_meteo} if self.open_meteo else {}
        if url == setup.OPEN_METEO_FORECAST:
            return {"timezone": TIMEZONES.get((params["latitude"], params["longitude"]))}
        raise AssertionError(url)

    def urls(self):
        return [u for u, _ in self.calls]


def utc(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def public(lid, km_north, name, model="O-1PST", age=timedelta(minutes=10), home=(39.74, -104.98)):
    return {"locationId": lid, "latitude": home[0] + km_north * KM_LAT, "longitude": home[1], "model": model,
            "locationName": name, "publicLocationName": name, "pm02": 8, "rhum": 40, "atmp": 10,
            "timestamp": utc(datetime.now(timezone.utc) - age), "offline": False}


WORLD = [public(68007, 1.3, "1000 Speer"), public(81334, 2.4, "Baker"), public(5, 0.5, "Someone's kitchen", model="I-9PSL")]


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / "config.example.toml").write_text((REPO / "config.example.toml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(setup.publicmap, "fetch_world", lambda: WORLD)
    monkeypatch.setattr(setup, "gcloud_status", lambda: "signed in")
    monkeypatch.setattr(setup, "port_free", lambda port: True)
    return tmp_path


@pytest.fixture
def geo(monkeypatch):
    g = Geo(nominatim=OGDEN)
    monkeypatch.setattr(setup, "http_get_json", g)
    return g


def run(root, *argv, env=None, capsys=None):
    code = setup.main(list(argv), env or {}, root)
    out = capsys.readouterr()
    return code, out.out + out.err


def config_of(root):
    return load_config({"CONFIG_TOML": (root / "config.toml").read_text(encoding="utf-8")}, root)


DENVER_ARGS = ("--address", "Ogden Theatre, Denver", "--monitors", "indoor")


# ---------- --check and writing ----------

def test_check_writes_nothing(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--indoor-name", "bedroom", "--check", capsys=capsys)
    assert code == 0
    assert not (root / "config.toml").exists()
    assert "Place: Ogden Theatre" in out and "39.74, -104.98" in out and "America/Denver" in out and "ZIP 80218" in out
    assert 'Monitors: indoor only, called "bedroom"' in out
    assert "Outdoor air: 1000 Speer, 1.3 km away, a public monitor reporting now (the suggestion)" in out
    assert "id 81334" in out   # the list turn 3 asks from
    assert '  outdoor_from = 68007' in out
    assert out.rstrip().endswith("Nothing written (--check).")


def test_writes_a_commented_config_and_checks_it(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--indoor-name", "bedroom", "--profiles", "toddler,sinus", "--dry", "ac_dry",
                    capsys=capsys)
    assert code == 0, out
    text = (root / "config.toml").read_text(encoding="utf-8")
    cfg = config_of(root)
    p = cfg.place
    assert (p.name, p.lat, p.lon, p.timezone, p.indoor, p.outdoor, p.pollen_zip, p.region) == \
        ("Denver", 39.74, -104.98, "America/Denver", "bedroom", None, "80218", "Denver")
    assert cfg.profiles == {"toddler": True, "sinus": True, "runner": False}
    assert cfg.appliances == ("ac_dry",)
    assert cfg.outdoor_from == 68007
    assert cfg.sources == {"smoke": True, "pollen": True, "nearby": True}
    assert cfg.pollen_seasons == ()   # Denver isn't in the northeast
    assert "# Latitude and longitude of your home" in text and "# What to call your outdoor monitor" not in text
    assert text.startswith("# Written by scripts/setup.py")
    assert "Wrote config.toml." in out and "Config OK" in out
    assert "Keep a private copy of config.toml" in out


def test_the_address_is_never_written_or_printed(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=FIFTH_AVE))
    code, out = run(root, "--address", "350 5th Ave, New York", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    text = (root / "config.toml").read_text(encoding="utf-8")
    for bit in ("350", "5th Ave", "Koreatown"):
        assert bit not in text
    assert "350" not in out and "5th Ave" not in out


def test_defaults(root, geo, capsys):
    code, out = run(root, "--address", "Ogden Theatre, Denver", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    cfg = config_of(root)
    assert (cfg.place.indoor, cfg.place.outdoor) == ("home", "outside")
    assert cfg.profiles == {"toddler": False, "sinus": False, "runner": False}
    assert cfg.appliances == ()
    assert cfg.outdoor_from is None   # an outdoor monitor gives the outdoor air
    assert cfg.sources["pollen"] is True   # --pollen later leaves it on
    assert "Token: now" in out and "Pollen: later" in out
    assert "scripts/setup.py token" in out   # --token now: the token's steps come next
    assert "Later, for the user" in out and "Pollen (optional)" in out
    assert not [u for u in geo.urls() if "airgradient" in u]


def test_outdoor_only_drops_the_indoor_line_and_the_drying_question(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS[:3], "outdoor", "--outdoor-name", "balcony", "--profiles", "toddler", capsys=capsys)
    assert code == 0, out
    text = (root / "config.toml").read_text(encoding="utf-8")
    assert "indoor =" not in text and "# What to call your indoor monitor" not in text
    assert config_of(root).place.outdoor == "balcony"
    assert "when it's too humid" not in out
    assert "the toddler's stays greyed until an indoor monitor is added" in out
    assert "outdoor_from" not in "".join(line for line in text.splitlines() if not line.startswith("#"))


def test_names_given_for_a_missing_monitor_are_left_out_with_a_note(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--outdoor-name", "balcony", "--check", capsys=capsys)
    assert code == 0 and "Note: --outdoor-name left out: no outdoor monitor." in out


@pytest.mark.parametrize("pick, want", [("area", "area"), ("model", "model"), ("81334", 81334), ("suggest", 68007)])
def test_outdoor_from_picks(root, geo, capsys, pick, want):
    code, out = run(root, *DENVER_ARGS, "--outdoor-from", pick, capsys=capsys)
    assert code == 0, out
    assert config_of(root).outdoor_from == want
    assert ("(the suggestion)" in out) == (pick == "suggest")


@pytest.mark.parametrize("pick", ["5", "999999"])   # an indoor public monitor, an id that isn't listed
def test_outdoor_from_must_be_a_listed_outdoor_monitor(root, geo, capsys, pick):
    code, out = run(root, *DENVER_ARGS, "--outdoor-from", pick, capsys=capsys)
    assert code == 2 and "isn't an outdoor monitor in AirGradient's public list" in out
    assert not (root / "config.toml").exists()


def test_outdoor_from_garbage_is_refused(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--outdoor-from", "nearest", capsys=capsys)
    assert code == 2 and "use suggest, a monitor's id" in out


def test_outdoor_from_next_to_an_outdoor_monitor_is_a_note(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS[:3], "both", "--outdoor-from", "area", capsys=capsys)
    assert code == 0 and "--outdoor-from left out" in out and config_of(root).outdoor_from is None


def test_airgradient_down(root, geo, monkeypatch, capsys):
    def down():
        raise requests.ConnectionError("down")
    monkeypatch.setattr(setup.publicmap, "fetch_world", down)
    code, out = run(root, *DENVER_ARGS, "--check", capsys=capsys)
    assert code == 1 and "didn't answer" in out and "--outdoor-from area or model" in out
    code, out = run(root, *DENVER_ARGS, "--outdoor-from", "area", "--check", capsys=capsys)
    assert code == 0 and "an estimate for your area" in out


def test_unknown_profile_stops_before_any_lookup(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--profiles", "toddler,light_sleeper", capsys=capsys)
    assert code == 2
    assert "Not a profile yet: light_sleeper" in out and "toddler, sinus, runner" in out
    assert 'SETUP.md, "Adding a profile"' in out
    assert geo.calls == [] and not (root / "config.toml").exists()


def test_unknown_drying_equipment(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--dry", "fan", capsys=capsys)
    assert code == 2 and "dehumidifier, ac_dry" in out


def test_missing_answers_are_usage_errors(root, geo):
    with pytest.raises(SystemExit) as e:
        setup.main(["--address", "x"], {}, root)
    assert e.value.code == 2
    with pytest.raises(SystemExit):
        setup.main(["--monitors", "indoor"], {}, root)


# ---------- An existing config.toml ----------

OLD = '[place]\nname = "Old home"\n'


def test_an_existing_config_is_never_replaced_without_asking(root, geo, capsys):
    (root / "config.toml").write_text(OLD, encoding="utf-8")
    code, out = run(root, *DENVER_ARGS, capsys=capsys)
    assert code == 1
    assert (root / "config.toml").read_text(encoding="utf-8") == OLD
    assert "nothing was written" in out and '-name = "Old home"' in out and "--replace" in out
    assert not list(root.glob("config.toml.bak-*"))


def test_check_with_an_existing_config_says_what_would_change(root, geo, capsys):
    (root / "config.toml").write_text(OLD, encoding="utf-8")
    code, out = run(root, *DENVER_ARGS, "--check", capsys=capsys)
    assert code == 0 and "Writing will need --replace" in out and '+name = "Denver"' in out
    assert (root / "config.toml").read_text(encoding="utf-8") == OLD


def test_replace_backs_up_first(root, geo, capsys):
    (root / "config.toml").write_text(OLD, encoding="utf-8")
    code, out = run(root, *DENVER_ARGS, "--replace", capsys=capsys)
    assert code == 0, out
    backups = list(root.glob("config.toml.bak-*"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == OLD
    assert f"Saved the old config.toml as {backups[0].name}" in out
    assert config_of(root).place.name == "Denver"
    # a second replace in the same minute keeps both backups
    (root / "config.toml").write_text(OLD, encoding="utf-8")
    run(root, *DENVER_ARGS, "--replace", capsys=capsys)
    assert len(list(root.glob("config.toml.bak-*"))) == 2


def test_the_same_config_again_writes_nothing(root, geo, capsys):
    run(root, *DENVER_ARGS, capsys=capsys)
    code, out = run(root, *DENVER_ARGS, capsys=capsys)
    assert code == 0 and "already has these settings" in out
    assert not list(root.glob("config.toml.bak-*"))


# ---------- Place, name, US or not ----------

def test_name_is_the_users_words_for_an_area(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=TIMES_SQUARE))
    code, out = run(root, "--address", "times square, New York", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    assert config_of(root).place.name == "Times Square"


def test_name_is_the_district_after_a_street_address(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=FIFTH_AVE))
    run(root, "--address", "350 5th Ave, New York", "--monitors", "both", capsys=capsys)
    assert config_of(root).place.name == "Manhattan"


def test_name_falls_back_to_the_city_not_the_smallest_area(root, geo, capsys):
    run(root, *DENVER_ARGS, capsys=capsys)
    assert config_of(root).place.name == "Denver"   # not "Swallow Hill Historic District", not "Ogden Theatre"


def test_overrides(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--name", "Capitol Hill", "--zip", "80203", "--region", "", "--timezone",
                    "America/Chicago", capsys=capsys)
    assert code == 0, out
    p = config_of(root).place
    assert (p.name, p.pollen_zip, p.region, p.timezone) == ("Capitol Hill", "80203", None, "America/Chicago")
    assert setup.OPEN_METEO_FORECAST not in geo.urls()   # --timezone: no timezone request


@pytest.mark.parametrize("flag, value, words", [("--zip", "8021", "5 digits"), ("--timezone", "Denver", "timezone name"),
                                                ("--name", "  ", "--name is empty")])
def test_bad_overrides(root, geo, capsys, flag, value, words):
    code, out = run(root, *DENVER_ARGS, flag, value, capsys=capsys)
    assert code == 2 and words in out


def test_northeast_keeps_the_example_seasons(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=BACK_BAY))
    code, out = run(root, "--address", "200 Clarendon Street, Boston", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    cfg = config_of(root)
    assert cfg.place.name == "Back Bay" and cfg.place.pollen_zip == "02116"
    assert [s["name"] for s in cfg.pollen_seasons] == ["Tree", "Grass", "Weed"]
    assert "the northeastern US's typical dates" in out


def test_outside_the_us(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=MARAIS))
    code, out = run(root, "--address", "Le Marais, Paris", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    cfg = config_of(root)
    assert cfg.place.name == "Le Marais" and cfg.place.timezone == "Europe/Paris"
    assert cfg.place.pollen_zip is None and cfg.sources["smoke"] is False and cfg.pollen_seasons == ()
    assert "Outside the US: wildfire smoke off" in out and "ZIP" not in out
    code, out = run(root, "--address", "Le Marais, Paris", "--monitors", "both", "--zip", "75004", "--check", capsys=capsys)
    assert code == 2 and "--zip is for US homes" in out


def test_pollen_off_and_now(root, geo, capsys):
    run(root, *DENVER_ARGS, "--pollen", "off", capsys=capsys)
    assert config_of(root).sources["pollen"] is False
    (root / "config.toml").unlink()
    code, out = run(root, *DENVER_ARGS, "--pollen", "now", capsys=capsys)
    assert code == 0 and "Pollen: SETUP.md step 5, with gcloud (signed in)." in out


def test_gcloud_is_checked_only_for_pollen_now(root, geo, monkeypatch, capsys):
    asked = []
    monkeypatch.setattr(setup, "gcloud_status", lambda: asked.append(1) or None)
    run(root, *DENVER_ARGS, capsys=capsys)
    assert asked == []


def test_keys_already_set(root, geo, capsys):
    (root / ".env").write_text("AIRGRADIENT_TOKEN=abc\nGOOGLE_POLLEN_API_KEY=def\n", encoding="utf-8")
    code, out = run(root, *DENVER_ARGS, "--pollen", "now", capsys=capsys)
    assert code == 0
    assert "Token: already in .env" in out and "Pollen: on, the key is already in .env" in out
    assert "scripts/setup.py token" not in out and "abc" not in out and "def" not in out.replace("default", "")


def test_next_steps_give_a_free_port_and_an_absolute_cd(root, geo, monkeypatch, capsys):
    monkeypatch.setattr(setup, "port_free", lambda port: port != 5555)
    code, out = run(root, *DENVER_ARGS, capsys=capsys)
    assert code == 0
    assert "Port 5555 is in use" in out and f"cd {root} && PORT=5556 " in out and "server.py" in out
    assert "--live http://localhost:5556" in out and "Ctrl+C" in out


# ---------- Pollen seasons ----------

def test_seasons_are_written_with_their_comment(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--season", "Tree: Jan 15 – Apr 30", "--season",
                    "grass: May 1 - Jul 31, peak June 1 to June 30", capsys=capsys)
    assert code == 0, out
    text = (root / "config.toml").read_text(encoding="utf-8")
    assert "typical dates, not a forecast (looked up at setup)" in text
    seasons = config_of(root).pollen_seasons
    assert seasons[0] == {"name": "Tree", "start": [1, 15], "peak": [[1, 15], [4, 30]], "end": [4, 30]}
    assert seasons[1] == {"name": "Grass", "start": [5, 1], "peak": [[6, 1], [6, 30]], "end": [7, 31]}
    assert "Tree Jan 15 – Apr 30, no peak given" in out


def test_seasons_replace_the_northeast_ones(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=BACK_BAY))
    run(root, "--address", "200 Clarendon Street, Boston", "--monitors", "both", "--season", "Weed: Aug 1 – Oct 1", capsys=capsys)
    assert [s["name"] for s in config_of(root).pollen_seasons] == ["Weed"]


@pytest.mark.parametrize("season, words", [
    ("Cedar: Dec 1 – Feb 15", "isn't one of Tree, Grass, Weed"),
    ("Tree Jan 1 – Feb 1", "no name"),
    ("Tree: Jan 1", "isn't a range"),
    ("Tree: Jan 1 – Feb 30", "isn't a day of the year"),
    ("Tree: Janvier 1 – Feb 3", "isn't a date"),
    ("Tree: Dec 1 – Feb 15", "runs past the new year"),
    ("Tree: Mar 1 – Apr 30, peak Feb 1 – Mar 10", "peak has to fall within the season"),
])
def test_bad_seasons(root, geo, capsys, season, words):
    code, out = run(root, *DENVER_ARGS, "--season", season, capsys=capsys)
    assert code == 2 and words in out and not (root / "config.toml").exists()


def test_a_season_twice(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--season", "Tree: Jan 1 – Feb 1", "--season", "tree: Mar 1 – Apr 1", capsys=capsys)
    assert code == 2 and "Tree is given twice" in out


# ---------- The geocoders ----------

def test_one_nominatim_request_with_the_apps_user_agent(root, monkeypatch, capsys):
    seen = []

    class Answer:
        def raise_for_status(self):
            pass

        def json(self):
            return OGDEN if "nominatim" in seen[-1][0] else {"timezone": "America/Denver"}

    monkeypatch.setattr(setup.requests, "get", lambda url, **kw: seen.append((url, kw)) or Answer())
    code, out = run(root, *DENVER_ARGS, "--check", capsys=capsys)
    assert code == 0, out
    assert [u for u, _ in seen] == [setup.NOMINATIM_SEARCH, setup.OPEN_METEO_FORECAST]
    for _, kw in seen:
        assert "sguyon/home-air-quality" in kw["headers"]["User-Agent"]
    assert seen[0][1]["params"]["q"] == "Ogden Theatre, Denver"


def test_open_meteo_when_nominatim_finds_nothing(root, monkeypatch, capsys):
    g = Geo(nominatim=[], open_meteo=OM_LOGAN)
    monkeypatch.setattr(setup, "http_get_json", g)
    code, out = run(root, "--address", "Logan Square, Chicago", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    assert g.urls() == [setup.NOMINATIM_SEARCH, setup.OPEN_METEO_SEARCH]   # the timezone came with the place
    assert g.calls[1][1]["name"] == "Logan Square"
    p = config_of(root).place
    assert (p.name, p.lat, p.lon, p.timezone, p.pollen_zip) == ("Logan Square", 41.92, -87.7, "America/Chicago", "60647")
    assert "found by Open-Meteo" in out


def test_open_meteo_when_nominatim_is_down(root, monkeypatch, capsys):
    g = Geo(open_meteo=OM_LOGAN[:1], down=(setup.NOMINATIM_SEARCH,))
    monkeypatch.setattr(setup, "http_get_json", g)
    code, out = run(root, "--address", "Logan Square", "--monitors", "both", "--check", capsys=capsys)
    assert code == 0 and "found by Open-Meteo" in out


def test_nothing_found(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo())
    code, out = run(root, "--address", "E Colfax Ave and N Ogden St, Denver", "--monitors", "both", capsys=capsys)
    assert code == 1 and "Couldn't find it" in out and "--lat and --lon" in out


def test_no_lookup_answers(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(down=("https://",)))
    code, out = run(root, *DENVER_ARGS, capsys=capsys)
    assert code == 1 and "Couldn't reach the place lookups" in out


def test_several_states_stop_and_ask(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=TWO_STATES))
    code, out = run(root, "--address", "Logan Square", "--monitors", "both", "--check", capsys=capsys)
    assert code == 1 and "Several places match" in out and "Illinois" in out and "Pennsylvania" in out
    monkeypatch.setattr(setup, "http_get_json", Geo(open_meteo=OM_LOGAN))
    code, out = run(root, "--address", "Logan Square", "--monitors", "both", "--check", capsys=capsys)
    assert code == 1 and "Several places match" in out and "Oregon" not in out


def test_coordinates_are_rounded_and_win_over_the_lookup(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--lat", "39.7461", "--lon", "-104.9832", capsys=capsys)
    assert code == 0, out
    p = config_of(root).place
    assert (p.lat, p.lon) == (39.75, -104.98)
    assert "lat = 39.75\n" in (root / "config.toml").read_text(encoding="utf-8")


def test_coordinates_alone_look_up_the_area(root, monkeypatch, capsys):
    g = Geo(reverse=FIFTH_AVE[0])
    monkeypatch.setattr(setup, "http_get_json", g)
    code, out = run(root, "--lat", "40.7128", "--lon", "-74.0060", "--monitors", "both", capsys=capsys)
    assert code == 0, out
    assert g.calls[0] == (setup.NOMINATIM_REVERSE, {"lat": 40.71, "lon": -74.01, "format": "jsonv2", "addressdetails": 1,
                                                   "accept-language": "en"})
    p = config_of(root).place
    assert (p.name, p.lat, p.lon) == ("Manhattan", 40.71, -74.01)


def test_lat_without_lon(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--lat", "39.7", capsys=capsys)
    assert code == 2 and "go together" in out


def test_no_timezone(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=OGDEN, down=(setup.OPEN_METEO_FORECAST,)))
    code, out = run(root, *DENVER_ARGS, capsys=capsys)
    assert code == 1 and "pass --timezone" in out


# ---------- setup.py token ----------

TOKEN = "f3b2c1d0-1234-5678-9abc-def012345678"


def save(root, typed, capsys):
    code = setup.main(["token"], {}, root, stdin=StringIO(typed))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_token_is_saved_and_never_printed(root, capsys):
    code, out = save(root, TOKEN + "\n", capsys)
    assert code == 0 and out.strip() == "Token saved in .env" and TOKEN not in out
    env = root / ".env"
    assert env.read_text(encoding="utf-8") == f"AIRGRADIENT_TOKEN={TOKEN}\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_token_replaces_the_line_that_wins_and_keeps_the_rest(root, capsys):
    env = root / ".env"
    env.write_text("# my keys\nexport AIRGRADIENT_TOKEN=your_token_here\nGOOGLE_POLLEN_API_KEY=keep\n"
                   "# AIRGRADIENT_TOKEN=old-comment\nAIRGRADIENT_TOKEN=second\nOTHER=x", encoding="utf-8")
    os.chmod(env, 0o640)
    code, out = save(root, TOKEN + "\n", capsys)
    assert code == 0 and TOKEN not in out
    assert env.read_text(encoding="utf-8") == (f"# my keys\nAIRGRADIENT_TOKEN={TOKEN}\nGOOGLE_POLLEN_API_KEY=keep\n"
                                               "# AIRGRADIENT_TOKEN=old-comment\nOTHER=x\n")
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    from config import parse_dotenv
    assert parse_dotenv(env.read_text(encoding="utf-8"))["AIRGRADIENT_TOKEN"] == TOKEN


@pytest.mark.parametrize("typed", ["\n", "", "your_token_here\n", "two words\n"])
def test_token_refuses_nothing_and_placeholders(root, capsys, typed):
    code, out = save(root, typed, capsys)
    assert code == 1 and "nothing saved" in out.lower() and not (root / ".env").exists()


def test_token_never_as_an_argument(root, capsys):
    code = setup.main(["token", TOKEN], {}, root)
    out = capsys.readouterr().out
    assert code == 2 and TOKEN not in out and not (root / ".env").exists()


# ---------- setup.py --live ----------

class Page(BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        status, body, kind = self.routes.get(self.path, (404, "{}", "application/json"))
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def page():
    """A made-up page on a free port. Returns (base url, routes): set the routes per test."""
    routes = {}
    handler = type("P", (Page,), {"routes": routes})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", routes
    server.shutdown()
    server.server_close()


INDOOR_ONLY = (REPO / "config.example.toml").read_text(encoding="utf-8").replace('outdoor = "porch"\n', "").replace(
    "# outdoor_from = 900002", "outdoor_from = 900002")


def serve(routes, cfg_text, root, token=True, rows=None, current_status=200, app_extra=None):
    cfg = load_config({"CONFIG_TOML": cfg_text}, root)
    app = {**public_view(cfg, root), "env": None, **(app_extra or {})}
    routes["/health"] = (200, json.dumps({"status": "ok", "airgradient_token_set": token}), "application/json")
    routes["/"] = (200, f"<html><script>window.APP = {json.dumps(app)};</script>\n<script src=x></script>", "text/html")
    routes["/api/current"] = (current_status, json.dumps(rows if rows is not None else {"state": "no_token"}), "application/json")


def now_z(minutes=3):
    return utc(datetime.now(timezone.utc) - timedelta(minutes=minutes))


SOURCE_ROW = {"locationType": "outdoor", "locationName": "1000 Speer", "timestamp": now_z(5),
              "source": {"kind": "monitor", "id": 900002, "name": "1000 Speer", "distance_km": 1.3, "fallback": False}}
INDOOR_ROW = {"locationId": 7001, "locationName": "Bedroom", "locationType": "indoor", "model": "I-9PSL", "timestamp": now_z()}


def live(root, url, capsys, env=None):
    code = setup.main(["--live", url], env or {}, root)
    return code, capsys.readouterr().out


def test_live_ok(root, page, capsys):
    url, routes = page
    (root / "config.toml").write_text(INDOOR_ONLY, encoding="utf-8")
    serve(routes, INDOOR_ONLY, root, rows=[INDOOR_ROW, SOURCE_ROW])
    code, out = live(root, url, capsys)
    assert code == 0, out
    assert f"Page: answers at {url}" in out and "Token: set" in out
    assert "Settings: the name, monitors, profiles and outdoor source match config.toml" in out
    assert 'indoor "Bedroom" (I-9PSL), last reading 3 min ago' in out
    assert 'outdoor source: public monitor "1000 Speer", 1.3 km, last reading 5 min ago' in out
    assert out.rstrip().endswith("Live OK")


def test_live_without_a_token(root, page, capsys):
    url, routes = page
    (root / "config.toml").write_text(INDOOR_ONLY, encoding="utf-8")
    serve(routes, INDOOR_ONLY, root, token=False)
    code, out = live(root, url, capsys)
    assert code == 1 and "Token: missing" in out and "Not live yet: open the local page and paste your token in the box" in out


def test_live_settings_differ_from_the_file(root, page, capsys):
    url, routes = page
    (root / "config.toml").write_text(INDOOR_ONLY.replace('name = "Maplewood"', 'name = "Capitol Hill"'), encoding="utf-8")
    serve(routes, INDOOR_ONLY, root, rows=[INDOOR_ROW, SOURCE_ROW])
    code, out = live(root, url, capsys)
    assert code == 1 and "the page's name is \"Maplewood\", config.toml's is \"Capitol Hill\"" in out and "Restart" in out


def test_live_missing_monitor_and_stale_reading(root, page, capsys):
    url, routes = page
    text = (REPO / "config.example.toml").read_text(encoding="utf-8")
    (root / "config.toml").write_text(text, encoding="utf-8")
    old = {**INDOOR_ROW, "timestamp": now_z(5 * 60)}
    serve(routes, text, root, rows=[old])
    code, out = live(root, url, capsys)
    assert code == 1
    assert "last reading 5 h ago" in out and "has no recent reading" in out
    assert "no outdoor monitor: the token's account has no monitor set as outdoor" in out


def test_live_airgradient_error(root, page, capsys):
    url, routes = page
    (root / "config.toml").write_text(INDOOR_ONLY, encoding="utf-8")
    serve(routes, INDOOR_ONLY, root, rows={"error": "AirGradient API error: 401"}, current_status=502)
    code, out = live(root, url, capsys)
    assert code == 1 and "AirGradient answered with an error: AirGradient API error: 401" in out


def test_live_demo_page(root, page, capsys):
    url, routes = page
    (root / "config.toml").write_text(INDOOR_ONLY, encoding="utf-8")
    serve(routes, INDOOR_ONLY, root, rows=[INDOOR_ROW, SOURCE_ROW], app_extra={"now": {"t": 1}})
    code, out = live(root, url, capsys)
    assert code == 1 and "runs the demo" in out


def test_live_no_page(root, capsys):
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    code, out = live(root, f"http://127.0.0.1:{port}", capsys)
    assert code == 1 and "doesn't answer" in out and "SETUP.md step 6" in out


def test_live_default_url_uses_port(root, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(setup, "live", lambda url, env, root: seen.append(url) or 0)
    setup.main(["--live"], {"PORT": "5600"}, root)
    setup.main(["--live"], {}, root)
    assert seen == ["http://localhost:5600", "http://localhost:5555"]


def test_live_sends_only_gets(root, page, monkeypatch, capsys):
    url, routes = page
    (root / "config.toml").write_text(INDOOR_ONLY, encoding="utf-8")
    serve(routes, INDOOR_ONLY, root, rows=[INDOOR_ROW, SOURCE_ROW])
    asked, real = [], requests.get
    monkeypatch.setattr(setup.requests, "get", lambda u, **kw: asked.append(u) or real(u, **kw))
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(setup.requests, verb, lambda *a, **k: pytest.fail("not a GET"))
    live(root, url, capsys)
    assert sorted(asked) == sorted([f"{url}/health", f"{url}/", f"{url}/api/current"])


def test_example_still_has_every_line_setup_edits(root, geo, capsys):
    """setup.py edits config.example.toml by its lines: renaming one there must fail here, not in a user's setup."""
    text = (REPO / "config.example.toml").read_text(encoding="utf-8")
    assert text.startswith(setup.HEADER_START) and setup.SEASONS_START in text
    tomllib.loads(text)


# ---------- review fixes ----------

def test_bad_port_falls_back_to_the_default(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, env={"PORT": "abc"}, capsys=capsys)
    assert code == 0 and "http://localhost:5555" in out and "Traceback" not in out
    assert setup.port_from({"PORT": "99999"}) == setup.DEFAULT_PORT and setup.port_from({"PORT": "8080"}) == 8080


def test_token_flag_never_repeats_its_value(root, geo, capsys):
    code, out = run(root, *DENVER_ARGS, "--token", TOKEN, "--check", capsys=capsys)
    assert code == 2 and TOKEN not in out and "now or later" in out


def test_no_area_means_ask_for_a_name_not_the_users_text(root, monkeypatch, capsys):
    bare = [osm(40.0, -105.0, "", "building", house_number="12", road="Elm Street", state="Colorado", **US)]
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=bare))
    code, out = run(root, "--address", "12 Elm Street", "--monitors", "indoor", "--timezone", "America/Denver", capsys=capsys)
    assert code == 1 and "--name" in out and not (root / "config.toml").exists()
    code, out = run(root, "--address", "12 Elm Street", "--monitors", "indoor", "--timezone", "America/Denver", "--name", "Home", capsys=capsys)
    assert code == 0 and config_of(root).place.name == "Home"


def test_outdoor_only_writes_no_appliances(root, geo, capsys):
    code, out = run(root, "--address", "Ogden Theatre, Denver", "--monitors", "outdoor", "--dry", "ac_dry", capsys=capsys)
    assert code == 0, out
    assert config_of(root).appliances == ()


def test_replace_backup_keeps_permissions(root, geo, capsys):
    (root / "config.toml").write_text(OLD, encoding="utf-8")
    os.chmod(root / "config.toml", 0o600)
    run(root, *DENVER_ARGS, "--replace", capsys=capsys)
    backup = next(root.glob("config.toml.bak-*"))
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_env_temp_file_removed_when_the_write_fails(root, monkeypatch):
    monkeypatch.setattr(setup.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        setup.write_env_key(root / ".env", "AIRGRADIENT_TOKEN", TOKEN)
    assert not list(root.glob(".env*"))


def test_zip_with_an_unknown_country_is_noted_as_ignored(root, monkeypatch, capsys):
    nowhere = [osm(10.0, 20.0, "Somewhere", "place", city="Somewhere")]
    monkeypatch.setattr(setup, "http_get_json", Geo(nominatim=nowhere))
    monkeypatch.setattr(setup, "timezone_at", lambda *a: "Africa/Lagos")
    code, out = run(root, "--address", "Somewhere", "--monitors", "indoor", "--zip", "80218", "--check", capsys=capsys)
    assert code == 0 and "--zip ignored" in out


def test_token_prompt_uses_getpass_on_the_real_stdin(root, monkeypatch, capsys):
    asked = []
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt: asked.append(prompt) or TOKEN)
    monkeypatch.setattr(setup.sys, "stdin", StringIO("never read\n"))
    code = setup.main(["token"], {}, root)
    assert code == 0 and asked and TOKEN not in capsys.readouterr().out


def test_token_without_a_terminal_reads_stdin_and_hints_when_empty(root, monkeypatch, capsys):
    import warnings

    def no_tty(prompt):
        warnings.warn("no tty", setup.getpass.GetPassWarning)
        return "echoed"
    monkeypatch.setattr(setup.getpass, "getpass", no_tty)
    monkeypatch.setattr(setup.sys, "stdin", StringIO(""))
    code = setup.main(["token"], {}, root)
    out = capsys.readouterr().out
    assert code == 1 and "own Terminal window" in out and not (root / ".env").exists()


@pytest.mark.parametrize("platform,env,command", [
    ("darwin", {}, "open"),
    ("linux", {"DISPLAY": ":0"}, "xdg-open"),
    ("linux", {"WAYLAND_DISPLAY": "wayland-0"}, "xdg-open"),
])
def test_open_page_uses_desktop_command_and_prints_address(root, monkeypatch, capsys, platform, env, command):
    monkeypatch.setattr(setup.sys, "platform", platform)
    monkeypatch.setattr(setup.token_setup, "DOCKER_MARKER", root / "no-container")
    monkeypatch.setattr(setup, "macos_desktop", lambda: True)
    launched = []
    monkeypatch.setattr(setup.subprocess, "run", lambda args, **kwargs: launched.append(args))
    assert setup.main(["--open", "http://localhost:5600"], env, root) == 0
    assert launched == [[command, "http://localhost:5600"]]
    assert "http://localhost:5600" in capsys.readouterr().out


@pytest.mark.parametrize("env,container", [
    ({"SSH_CONNECTION": "session", "DISPLAY": ":0"}, False),
    ({"SSH_CLIENT": "session", "DISPLAY": ":0"}, False),
    ({"SSH_TTY": "tty", "DISPLAY": ":0"}, False),
    ({}, False),
    ({"DISPLAY": ":0"}, True),
    ({"DISPLAY": ":0", "RAILWAY_PROJECT_ID": ""}, False),
])
def test_open_page_skips_remote_headless_and_container_but_prints_address(root, monkeypatch, capsys, env, container):
    monkeypatch.setattr(setup.sys, "platform", "linux")
    marker = root / "container-marker"
    if container:
        marker.touch()
    monkeypatch.setattr(setup.token_setup, "DOCKER_MARKER", marker)
    def unexpected(*a, **k):
        pytest.fail("No desktop browser should be launched")
    monkeypatch.setattr(setup.subprocess, "run", unexpected)
    assert setup.main(["--open"], env, root) == 0
    assert "http://localhost:5555" in capsys.readouterr().out


def test_open_page_skips_macos_without_a_desktop(root, monkeypatch, capsys):
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    monkeypatch.setattr(setup.token_setup, "DOCKER_MARKER", root / "no-container")
    monkeypatch.setattr(setup, "macos_desktop", lambda: False)
    def unexpected(*a, **k):
        pytest.fail("No browser should be opened without a desktop")
    monkeypatch.setattr(setup.subprocess, "run", unexpected)
    assert setup.main(["--open"], {}, root) == 0
    assert "http://localhost:5555" in capsys.readouterr().out
