"""Setup uses invented keys, places and monitors. No network or listening ports."""
import json
import os
import stat
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from config import DEFAULT_LIMITS, load_config

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import setup

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

ORIGINAL_HTTP_GET = setup.http_get_json
ORIGINAL_ACCOUNT_ROWS = setup.account_rows
TOKEN = "invented-account-token"
NOW = datetime.now(timezone.utc).isoformat()
INDOOR = {"locationId": 7001, "locationType": "indoor", "locationName": "Bedroom", "timestamp": NOW}
OUTDOOR = {"locationId": 7002, "locationType": "outdoor", "locationName": "Porch", "timestamp": NOW}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.requests, "get", lambda *a, **k: pytest.fail("Unexpected network request"))
    monkeypatch.setattr(setup, "account_rows", lambda token, **k: [dict(INDOOR)])
    monkeypatch.setattr(setup.publicmap, "fetch_world", lambda: [])
    monkeypatch.setattr(setup.check_config.publicmap, "fetch_world", lambda: [])
    def geo(url, params):
        if url == setup.NOMINATIM_SEARCH:
            return OGDEN
        if url == setup.NOMINATIM_REVERSE:
            return OGDEN[0]
        assert url == setup.OPEN_METEO_FORECAST
        return {"timezone": "America/Denver"}
    monkeypatch.setattr(setup, "http_get_json", geo)
    return tmp_path


def run(root, capsys, *args, env=None):
    code = setup.main(list(args), {"AIRGRADIENT_TOKEN": TOKEN} if env is None else env, root)
    output = capsys.readouterr()
    return code, output.out + output.err


def home(root):
    return load_config({}, root)


def test_default_command_prepares_editor_file(root, capsys):
    code, out = run(root, capsys, env={})
    assert code == 0 and ".env" in out
    assert (root / ".env").read_text() == "AIRGRADIENT_TOKEN=\n"
    assert stat.S_IMODE((root / ".env").stat().st_mode) == 0o600
    assert not (root / "config.toml").exists()


@pytest.mark.parametrize("text", ["# keep\nOTHER=x\n", "export AIRGRADIENT_TOKEN=\nOTHER=x\n", f"AIRGRADIENT_TOKEN={TOKEN}\nOTHER=x\n"])
def test_editor_preparation_keeps_existing_lines_and_values(root, capsys, text):
    path = root / ".env"
    path.write_text(text)
    code, out = run(root, capsys, env={})
    assert code == 0 and TOKEN not in out
    expected = text if "AIRGRADIENT_TOKEN=" in text else text + "AIRGRADIENT_TOKEN=\n"
    assert path.read_text() == expected
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_missing_token_stops_before_lookups(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", lambda *a: pytest.fail("token must come first"))
    code, out = run(root, capsys, "--address", "Denver", env={})
    assert code == 1 and ".env" in out and not (root / "config.toml").exists()


def test_small_config_defaults_and_single_resolution(root, monkeypatch, capsys):
    seen = []
    real = setup.http_get_json
    monkeypatch.setattr(setup, "http_get_json", lambda u, p: seen.append(u) or real(u, p))
    calls = []
    monkeypatch.setattr(setup, "account_rows", lambda token: calls.append(token) or [INDOOR])
    code, out = run(root, capsys, "--address", "Ogden Theatre, Denver", "--profiles", "sinus,runner")
    assert code == 0, out
    assert seen == [setup.NOMINATIM_SEARCH, setup.OPEN_METEO_FORECAST]
    assert calls == [TOKEN]  # discovery and the live check share one account reading
    cfg = home(root)
    assert cfg.place.name == "Denver" and cfg.place.timezone == "America/Denver"
    assert cfg.place.indoor == "Bedroom" and cfg.place.indoor_id == 7001
    assert cfg.place.outdoor is None and cfg.outdoor_from == "model"
    assert cfg.appliances == () and cfg.profiles == {"toddler": False, "sinus": True, "runner": True}
    assert cfg.limits == DEFAULT_LIMITS and cfg.road is None
    raw = tomllib.loads((root / "config.toml").read_text())
    assert set(raw) == {"place", "profiles", "sources", "home"}
    assert cfg.temp_unit == "F" and "Temperatures in °F" in out   # a US home starts in °F (decision 8), and setup says so
    assert "estimate" in out and "Config OK" in out and out.rstrip().endswith("Live OK")
    assert "Ogden Theatre" not in out and TOKEN not in out


def test_ambiguous_monitors_ask_with_candidates_and_flag(root, monkeypatch, capsys):
    rows = [INDOOR, {**INDOOR, "locationId": 7003, "locationName": "Kitchen"}, OUTDOOR]
    monkeypatch.setattr(setup, "account_rows", lambda token: rows)
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 1 and "Choose one of:" in out and "Bedroom" in out and "Kitchen" in out and "--indoor-id" in out
    assert not (root / "config.toml").exists()
    code, out = run(root, capsys, "--address", "Denver", "--indoor-id", "7003")
    assert code == 0, out
    assert home(root).place.indoor_id == 7003 and home(root).place.outdoor_id == 7002
    assert 'indoor "Kitchen"' in out


@pytest.mark.parametrize("rows", [[], [{"locationId": 1, "locationName": "Unknown"}]])
def test_empty_or_unclassified_account_does_not_guess(root, monkeypatch, capsys, rows):
    monkeypatch.setattr(setup, "account_rows", lambda token: rows)
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 1 and "AirGradient" in out and not (root / "config.toml").exists()


def test_unclassified_monitor_requires_an_explicit_choice(root, monkeypatch, capsys):
    row = {**INDOOR, "locationType": None}
    monkeypatch.setattr(setup, "account_rows", lambda token: [row])
    code, out = run(root, capsys, "--address", "Denver", "--indoor-id", "7001")
    assert code == 0, out
    assert home(root).place.indoor_id == 7001


def test_wrong_monitor_choice_is_refused(root, capsys):
    code, out = run(root, capsys, "--address", "Denver", "--indoor-id", "999")
    assert code == 1 and "Choose one of:" in out and not (root / "config.toml").exists()


def test_public_lookup_failure_is_an_estimate(root, monkeypatch, capsys):
    def down():
        raise requests.ConnectionError(TOKEN)
    monkeypatch.setattr(setup.publicmap, "fetch_world", down)
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 0 and "estimate" in out and TOKEN not in out
    assert home(root).outdoor_from == "model"


def test_accepts_public_source_suggestion(root, monkeypatch, capsys):
    monkeypatch.setattr(setup.publicmap, "fetch_world", lambda: [{"locationId": 9001, "model": "O-1PST", "latitude": 39.74, "longitude": -104.98, "timestamp": NOW}])
    monkeypatch.setattr(setup.publicmap, "suggest", lambda *a: (9001, None, 1))
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 0, out
    assert home(root).outdoor_from == 9001


def test_existing_config_is_copied_before_replacement(root, capsys):
    path = root / "config.toml"
    path.write_text("old config\n")
    path.chmod(0o600)
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 0, out
    backup = next(root.glob("config.toml.bak-*"))
    assert backup.read_text() == "old config\n" and str(backup) in out
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 0 and len(list(root.glob("config.toml.bak-*"))) == 1


@pytest.mark.parametrize("results,country,smoke,zip_code,name,unit", [(MARAIS, "FR", False, None, "Le Marais", "C"),
                                                                     (BACK_BAY, "US", True, "02116", "Back Bay", "F")])
def test_geographic_corrections(root, monkeypatch, capsys, results, country, smoke, zip_code, name, unit):
    def geo(url, params):
        return results if url == setup.NOMINATIM_SEARCH else {"timezone": "Europe/Paris" if country == "FR" else "America/New_York"}
    monkeypatch.setattr(setup, "http_get_json", geo)
    code, out = run(root, capsys, "--address", name)
    assert code == 0, out
    cfg = home(root)
    assert cfg.sources["smoke"] is smoke and cfg.place.pollen_zip == zip_code and cfg.place.name == name
    assert cfg.pollen_seasons == ()
    assert cfg.temp_unit == unit and f"Temperatures in °{unit}" in out


def test_one_nominatim_request_with_user_agent_and_no_second_geocoder(root, monkeypatch, capsys):
    seen = []
    class Reply:
        def raise_for_status(self):
            pass
        def json(self):
            return []
    def get(url, **kwargs):
        seen.append((url, kwargs))
        return Reply()
    monkeypatch.setattr(setup.requests, "get", get)
    monkeypatch.setattr(setup, "http_get_json", ORIGINAL_HTTP_GET)
    code, out = run(root, capsys, "--address", "Missing place")
    assert code == 1 and "Couldn't find it" in out
    assert len(seen) == 1 and seen[0][0] == setup.NOMINATIM_SEARCH
    assert "sguyon/home-air-quality" in seen[0][1]["headers"]["User-Agent"]


def test_stale_monitor_fails_live_check_after_writing(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "account_rows", lambda token: [{**INDOOR, "timestamp": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}])
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 1 and "no recent reading" in out and (root / "config.toml").exists()


def test_account_request_is_read_only_and_errors_never_expose_keys(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "account_rows", ORIGINAL_ACCOUNT_ROWS)
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        raise requests.ConnectionError(TOKEN)
    monkeypatch.setattr(setup.requests, "get", get)
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 1 and TOKEN not in out and "AirGradient" in out
    assert len(calls) == 1 and calls[0][1]["params"] == {"token": TOKEN}
    assert calls[0][1]["allow_redirects"] is False


def test_railway_uses_stdin_and_prints_only_names(root, monkeypatch, capsys):
    config = '[place]\nname = "Private home"\n'
    (root / "config.toml").write_text(config)
    (root / ".env").write_text(f'AIRGRADIENT_TOKEN="{TOKEN}"\nGOOGLE_POLLEN_API_KEY=invented-pollen-key\nOTHER=ignored\n')
    fake = root / "railway"
    fake.write_text("#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\np=Path(os.environ['RAILWAY_CAPTURE'])\nwith p.open('a') as f: f.write(json.dumps({'args':sys.argv[1:], 'value':sys.stdin.read()})+'\\n')\nprint('should never appear')\n")
    fake.chmod(0o755)
    capture = root / "capture.jsonl"
    monkeypatch.setenv("PATH", str(root) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("RAILWAY_CAPTURE", str(capture))
    code, out = run(root, capsys, "railway", "--service", "home-air", env={})
    assert code == 0, out
    sent = [json.loads(line) for line in capture.read_text().splitlines()]
    assert [s['value'] for s in sent] == [config, TOKEN, "invented-pollen-key"]
    assert [s['args'] for s in sent] == [["variable", "set", name, "--stdin", "--service", "home-air", "--skip-deploys"]
                                         for name in ("CONFIG_TOML", "AIRGRADIENT_TOKEN", "GOOGLE_POLLEN_API_KEY")]
    assert TOKEN not in out and "invented-pollen-key" not in out and "Private home" not in out and "should never appear" not in out
    assert all(name in out for name in ("CONFIG_TOML", "AIRGRADIENT_TOKEN", "GOOGLE_POLLEN_API_KEY"))
    # No deploy starts per variable: the last line says how to deploy with all of them.
    assert "railway up --service home-air --detach" in out and "railway redeploy --service home-air" in out
    assert "ask the user first" in out


def test_railway_omits_empty_keys_and_suppresses_cli_errors(root, monkeypatch, capsys):
    (root / "config.toml").write_text("private config")
    (root / ".env").write_text('AIRGRADIENT_TOKEN=\nGOOGLE_POLLEN_API_KEY=your_key_here\n')
    calls = []
    def fail(args, **kwargs):
        calls.append((args, kwargs))
        raise setup.subprocess.CalledProcessError(1, args, output=TOKEN, stderr=TOKEN)
    monkeypatch.setattr(setup.subprocess, "run", fail)
    code, out = run(root, capsys, "railway", "--service", "home-air")
    assert code == 1 and TOKEN not in out and len(calls) == 1



def test_saved_monitor_ids_filter_the_page_readings(root, monkeypatch, capsys):
    import sources
    from types import SimpleNamespace
    run(root, capsys, "--address", "Denver")
    cfg = home(root)
    rows = [INDOOR, {**INDOOR, "locationId": 999}, OUTDOOR]
    monkeypatch.setattr(sources, "runtime", SimpleNamespace(CFG=cfg))
    assert sources.place_rows(rows) == [INDOOR]
    assert len(rows) == 3


def test_non_integer_monitor_ids_are_invalid(root):
    from config import ConfigError
    text = '[place]\nname="Home"\nlat=40\nlon=-74\ntimezone="America/New_York"\nindoor="Room"\nindoor_id="bad"\n[sources]\noutdoor_from="model"\n'
    with pytest.raises(ConfigError, match="indoor_id"):
        load_config({"CONFIG_TOML": text}, root)


def test_unknown_outdoor_can_be_chosen_without_inventing_an_indoor_monitor(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "account_rows", lambda token: [{**OUTDOOR, "locationType": None}])
    code, out = run(root, capsys, "--address", "Denver", "--outdoor-id", "7002")
    assert code == 0, out
    assert home(root).place.indoor is None and home(root).place.outdoor_id == 7002


@pytest.mark.parametrize("args,words", [
    (["--lat", "40"], "go together"),
    (["--timezone", "Wrong/Zone"], "timezone name"),
    (["--zip", "123"], "5 digits"),
])
def test_lookup_corrections_are_validated(root, capsys, args, words):
    code, out = run(root, capsys, "--address", "Denver", *args)
    assert code == 2 and words in out and not (root / "config.toml").exists()


def test_ambiguous_places_still_require_city(root, monkeypatch, capsys):
    monkeypatch.setattr(setup, "http_get_json", lambda *a: TWO_STATES)
    code, out = run(root, capsys, "--address", "Logan Square")
    assert code == 1 and "Several places match" in out and "Illinois" in out and "Pennsylvania" in out


def test_geocoder_outage_is_plain_and_does_not_fall_back(root, monkeypatch, capsys):
    calls = []
    def down(url, params):
        calls.append(url)
        raise requests.ConnectionError("down")
    monkeypatch.setattr(setup, "http_get_json", down)
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 1 and "Couldn't reach OpenStreetMap" in out and calls == [setup.NOMINATIM_SEARCH]


@pytest.mark.parametrize("rows,token,expected,words", [
    ([INDOOR, OUTDOOR], True, 0, "Live OK"),
    ([{**INDOOR, "locationId": 999}, OUTDOOR], True, 1, "no indoor monitor"),
    ([{**INDOOR, "timestamp": None}, OUTDOOR], True, 1, "no recent reading"),
    ([INDOOR, OUTDOOR], False, 1, "add AIRGRADIENT_TOKEN to .env"),
])
def test_live_checks_running_destination_using_only_gets(root, monkeypatch, capsys, rows, token, expected, words):
    from config import public_view
    monkeypatch.setattr(setup, "account_rows", lambda token: [INDOOR, OUTDOOR])
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 0, out
    app = public_view(home(root), root)
    calls = []
    class Reply:
        status_code = 200
        def __init__(self, value):
            self.value = value
            self.text = f'<script>window.APP = {json.dumps(value)};</script>'
        def json(self):
            return self.value
    def get(url, **kwargs):
        calls.append(url)
        return Reply({"status": "ok", "airgradient_token_set": token} if url.endswith("/health") else rows if url.endswith("/api/current") else app)
    monkeypatch.setattr(setup.requests, "get", get)
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(setup.requests, verb, lambda *a, **k: pytest.fail("Only GET is allowed"))
    code, out = run(root, capsys, "--live", "http://destination:8000")
    assert code == expected and words in out, out
    assert calls == ["http://destination:8000/health", "http://destination:8000/"] + (["http://destination:8000/api/current"] if token else [])


def test_after_the_page_connects_the_default_command_names_the_monitors(root, monkeypatch, capsys):
    # The agent tells the user what the account has, without ever seeing the token.
    monkeypatch.setattr(setup, "account_rows", lambda token: [{"locationName": "Living room", "locationType": "indoor"},
                                                                {"locationName": "Back porch", "model": "O-1PST"}])
    code, out = run(root, capsys)
    assert code == 0 and TOKEN not in out
    assert "Connected to AirGradient: 2 monitors: Living room (indoor), Back porch (outdoor)." in out


# --status: what's done and the one next command. Read-only: no file written, no question, exit code 0.

def files(root):
    return {p.relative_to(root): (p.read_bytes(), p.stat().st_mode) for p in root.rglob("*") if p.is_file()}


def status(root, capsys, env=None):
    before = files(root)
    code, out = run(root, capsys, "--status", env=env)
    assert code == 0, out
    assert files(root) == before, "--status must not change any file"
    return out


def next_line(out):
    lines = [l for l in out.splitlines() if l.startswith("Next: ")]
    assert len(lines) == 1, out
    return lines[0].removeprefix("Next: ")


def test_status_on_an_empty_folder_names_the_first_command(root, capsys):
    out = status(root, capsys, env={})
    assert next_line(out) == setup.SETUP_CMD
    assert "not yet" in out and not (root / ".env").exists()


def test_status_after_preparing_says_to_connect_on_the_page(root, capsys):
    (root / ".env").write_text("AIRGRADIENT_TOKEN=\n")
    out = status(root, capsys, env={})
    assert "server.py" in next_line(out) and "?setup=" in next_line(out)


def test_status_with_a_token_but_no_home_names_the_home_command(root, capsys):
    (root / ".env").write_text(f"AIRGRADIENT_TOKEN={TOKEN}\n")
    out = status(root, capsys, env={})
    assert next_line(out).startswith(setup.SETUP_CMD + " --address")
    assert TOKEN not in out


def test_status_on_a_complete_setup_is_done_with_the_address(root, capsys):
    code, out = run(root, capsys, "--address", "Denver")
    assert code == 0, out
    (root / ".env").write_text(f'AIRGRADIENT_TOKEN="{TOKEN}"\n')
    out = status(root, capsys, env={"PORT": "5600"})
    assert "Steps 1–4 done" in out and "http://localhost:5600" in out and TOKEN not in out
    # SETUP.md's done is --live ending with Live OK: the next command starts the page and runs that check.
    nxt = next_line(out)
    assert setup.SERVER_CMD in nxt and str(root) in nxt and "PORT=5600" in nxt
    assert f"{setup.SETUP_CMD} --live http://localhost:5600" in nxt and "the page's address" in nxt


def test_status_reports_a_broken_config_in_plain_words(root, capsys):
    (root / "config.toml").write_text('[place]\nname = "Home"\n')
    out = status(root, capsys)
    assert "config.toml" in out and "lat" in out
    assert next_line(out).startswith(setup.SETUP_CMD + " --address")


def test_status_says_when_a_monitor_has_no_recent_reading(root, monkeypatch, capsys):
    run(root, capsys, "--address", "Denver")
    old = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    monkeypatch.setattr(setup, "account_rows", lambda token, **k: [{**INDOOR, "timestamp": old}])
    out = status(root, capsys)
    assert "no recent reading" in out and "Steps 1–4 done" not in out
    assert setup.STATUS_CMD in next_line(out)


def test_status_when_airgradient_cannot_be_reached_is_plain_and_quick(root, monkeypatch, capsys):
    run(root, capsys, "--address", "Denver")
    monkeypatch.setattr(setup, "account_rows", ORIGINAL_ACCOUNT_ROWS)
    seen = []
    def get(url, **kwargs):
        seen.append(kwargs)
        raise requests.ConnectionError(TOKEN)
    monkeypatch.setattr(setup.requests, "get", get)
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(setup.requests, verb, lambda *a, **k: pytest.fail("Only GET is allowed"))
    out = status(root, capsys)
    assert "couldn't check" in out and TOKEN not in out and "Steps 1–4 done" not in out
    assert len(seen) == 1 and seen[0]["timeout"] == setup.STATUS_TIMEOUT
    assert next_line(out) == setup.STATUS_CMD
    step4 = next(l for l in out.splitlines() if "4. Readings" in l)
    assert ".env" not in step4 and step4.count(".") <= 2   # one short sentence, not where the token isn't


def _status_with_get(root, monkeypatch, capsys, get):
    run(root, capsys, "--address", "Denver")
    monkeypatch.setattr(setup, "account_rows", ORIGINAL_ACCOUNT_ROWS)
    monkeypatch.setattr(setup.requests, "get", get)
    out = status(root, capsys)
    return out, next(l for l in out.splitlines() if "4. Readings" in l)


def test_status_when_airgradient_is_slow_says_so_and_to_try_again(root, monkeypatch, capsys):
    # 2026-11-13: AirGradient took 7 s to connect; a 5 s limit read that as "didn't answer, or refused the token"
    def get(url, **kwargs):
        raise requests.ConnectTimeout(TOKEN)
    out, step4 = _status_with_get(root, monkeypatch, capsys, get)
    assert f"didn't answer within {setup.STATUS_TIMEOUT} s" in step4 and "refused" not in step4 and TOKEN not in out
    assert next_line(out) == setup.STATUS_CMD
    assert setup.STATUS_TIMEOUT >= 15


def test_status_when_airgradient_refuses_the_token_says_to_enter_it_again(root, monkeypatch, capsys):
    class Refused:
        status_code = 401
        def raise_for_status(self):
            raise requests.HTTPError("401", response=self)
        def json(self):
            return {"message": TOKEN}
    out, step4 = _status_with_get(root, monkeypatch, capsys, lambda url, **k: Refused())
    assert "refused the token" in step4 and "didn't answer" not in step4 and TOKEN not in out
    assert setup.SERVER_CMD in next_line(out)


def test_status_never_prints_key_values_even_when_set_in_the_environment(root, capsys):
    (root / ".env").write_text("GOOGLE_POLLEN_API_KEY=invented-pollen-key\n")
    out = status(root, capsys, env={"AIRGRADIENT_TOKEN": TOKEN, "GOOGLE_POLLEN_API_KEY": "invented-pollen-key"})
    assert TOKEN not in out and "invented-pollen-key" not in out


def test_status_names_where_the_config_was_read_from(root, capsys):
    text = ('[place]\nname = "Denver"\nlat = 39.74\nlon = -104.98\ntimezone = "America/Denver"\n'
            'indoor = "Bedroom"\nindoor_id = 7001\n[sources]\noutdoor_from = "model"\n')
    out = status(root, capsys, env={"CONFIG_TOML": text})
    step3 = next(l for l in out.splitlines() if "3. Home" in l)
    assert "CONFIG_TOML" in step3 and "config.toml" not in step3


def test_setup_md_asks_one_question_at_a_time_with_or_without_a_question_tool():
    # rehearse manual-20261110-1812-S1: questions queued while the user typed; the old wording ("no question tool with several
    # questions") read as "never use a question tool", against "Agents with a question tool use it" (0006d85)
    intro = (Path(__file__).resolve().parent.parent / "SETUP.md").read_text().splitlines()[4]
    assert "Ask one question per message, in plain words, then wait for the answer." in intro
    # rehearse manual-20261113-1848-S1 (Claude Code): "claude code didnt use the ask question tool anymore": "use it for one
    # question at a time" read as optional, so every question goes through it, never as plain chat text
    assert "If you have a question tool (Claude Code's AskUserQuestion, for example), ask every question with it" in intro
    assert "don't write a question as plain chat text" in intro
    assert "Don't ask the next one until the user has answered and you've said what you did with it" in intro
    assert "no question tool" not in intro


def test_setup_md_ends_on_the_home_in_the_tab_already_open_and_a_prominent_address():
    # rehearse manual-20261113-1848-S1: "it could make it clear to open the app in browser ... the log line here is not super
    # important and the link to the app should be more prominent"; both agents opened a second tab although the token page
    # had already turned into the home
    doc = (Path(__file__).resolve().parent.parent / "SETUP.md").read_text()
    verify = doc.split("## Start and verify", 1)[1].split("\n## ", 1)[0]
    again = doc.split("## Use it again", 1)[1].split("\n## ", 1)[0]
    assert "the page where the user saved the token turns into the home by itself: don't open another tab" in verify
    assert "Start with the address alone on its own line, in bold" in again
    assert "it's open in the tab where they saved the token" in again
    assert "Mention the log file only if something failed" in again and "log location" not in again


def test_deployment_md_says_which_hosts_are_tested():
    # Sacha, 2026-11-13: "we dont have anything that says we don't support other methods like other hosting providers besides railway"
    intro = (Path(__file__).resolve().parent.parent / "DEPLOYMENT.md").read_text().split("\n## ")[0]
    assert "Only Railway and Docker are tested" in intro
    assert "`Dockerfile`" in intro and "untested" in intro


def test_wait_token_reports_the_account_as_soon_as_the_page_saves_the_token(root, capsys, monkeypatch):
    # Sacha, 2026-11-13: "is there a way to know that the user has entered a token key to avoid having them to type Connected?"
    (root / ".env").write_text("AIRGRADIENT_TOKEN=\n")
    sleeps = []
    def page_saves_it(seconds):   # the token page saves the token while the command waits
        sleeps.append(seconds)
        if len(sleeps) == 2:
            (root / ".env").write_text(f"AIRGRADIENT_TOKEN={TOKEN}\n")
    monkeypatch.setattr(setup.time, "sleep", page_saves_it)
    code, out = run(root, capsys, "--wait-token", env={})
    assert code == 0 and sleeps == [setup.WAIT_POLL_SECONDS] * 2
    assert out.startswith("Connected to AirGradient: 1 monitor:") and TOKEN not in out


def test_wait_token_gives_up_after_its_limit_and_says_what_to_do_next(root, capsys, monkeypatch):
    (root / ".env").write_text("AIRGRADIENT_TOKEN=\n")
    now = [0.0]
    monkeypatch.setattr(setup.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(setup.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(setup, "account_rows", lambda token, **k: pytest.fail("no token: nothing to look up"))
    code, out = run(root, capsys, "--wait-token", env={})
    assert code == 0 and now[0] >= setup.WAIT_TOKEN_SECONDS
    assert out.startswith("Not saved yet.") and "--wait-token" in out and "done" in out
    assert setup.WAIT_TOKEN_SECONDS < 120   # one wait fits Claude Code's default 2-minute command limit


def test_setup_md_waits_for_the_token_and_falls_back_to_done():
    text = (Path(__file__).resolve().parent.parent / "SETUP.md").read_text()
    assert "scripts/setup.py --wait-token" in text and "no need to reply" in text and "type done" in text
    assert "Tell me when the page says Connected" not in text


def test_setup_md_lets_the_user_keep_a_default_without_typing_it():
    # Sacha, 2026-11-13: "is there a way to not have to type "none" in the profile question to select the default answer?"
    text = (Path(__file__).resolve().parent.parent / "SETUP.md").read_text()
    home = text.split("## Describe your home", 1)[1].split("\n## ", 1)[0]
    assert "With a question tool, offer the answers as options with the default first" in home
    assert "Any other reply, like ok, keeps none." in home
    assert "Any other reply, like ok, keeps it." in home
