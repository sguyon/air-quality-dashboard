"""Prepare private files, discover monitors, write household choices and verify them.

Run with no answers to prepare .env; with --address and --profiles to finish setup.
The railway command transfers saved settings through stdin. --live checks a running page.
--status lists what's done and the next command; it changes nothing.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_config
import publicmap
import sources  # installs the request-log filter that hides query credentials
from config import (ENV_FILE_MODE, PLACE_DECIMALS, PROFILES, ConfigError, defines,
                    env_key, load_config, parse_dotenv, public_view, write_env_key)

REPO_URL = "https://github.com/sguyon/home-air-quality"
USER_AGENT = f"home-air-quality-setup/1.0 (+{REPO_URL})"  # Nominatim requires an identifying User-Agent.
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"  # timezone=auto resolves a point's timezone.
LOOKUP_RESULTS = 3  # matches: enough to catch a name shared by different states.
AMBIGUOUS_SHOWN = 3  # matches shown when a place needs its city or state.
LOOKUP_TIMEOUT = 15  # seconds per place or timezone request.
LIVE_TIMEOUT = 30  # seconds: a running page may be waiting on its outside sources.
DEFAULT_PORT = 5555  # server.py's local port without PORT.
AREA_CATEGORIES = ("place", "boundary")  # Nominatim's area names, rather than buildings or streets.
DISTRICT_KEYS = ("suburb", "city_district", "borough", "quarter")  # district before city for a street lookup.
CITY_KEYS = ("city", "town", "village", "hamlet")
NORTHEAST = {"CT": "Connecticut", "ME": "Maine", "MA": "Massachusetts", "NH": "New Hampshire", "RI": "Rhode Island",
             "VT": "Vermont", "NY": "New York", "NJ": "New Jersey", "PA": "Pennsylvania"}  # normalize known state codes.
NOT_FOUND = "Couldn't find it. Try a nearby landmark with its city, or pass --lat and --lon from a map app."
KEY_NAMES = ("AIRGRADIENT_TOKEN", "GOOGLE_POLLEN_API_KEY")  # the only keys transferred to Railway.
STATUS_TIMEOUT = 15  # seconds for --status's one readings request: AirGradient took 7 s to connect on 2026-11-13, and 5 s read that as a refused token.
RUN = "scripts/run.sh"  # how SETUP.md runs every command: uv, else installing uv, else Python 3.11+ (the uv ladder).
SETUP_CMD = f"{RUN} scripts/setup.py"
SERVER_CMD = f"{RUN} server.py"
START_CMD = f"nohup {SERVER_CMD} > app.log 2>&1 < /dev/null &"  # in the background, so it outlives the agent's session; its log in app.log
HOME_CMD = f'{SETUP_CMD} --address "<neighborhood or address>" --profiles <toddler,sinus,runner or none>'
STATUS_CMD = f"{SETUP_CMD} --status"
WAIT_TOKEN_CMD = f"{SETUP_CMD} --wait-token"
WAIT_TOKEN_SECONDS = 90  # one wait: under the shortest default command limit we know (Claude Code stops a command after 120 s).
STARTUP_WAIT = 30  # seconds for the page to answer after the system starts it at login (uv may install packages first).
WAIT_POLL_SECONDS = 2  # how often --wait-token looks for the saved token: the user sees the agent move on within 2 s.


class SetupError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def http_get_json(url, params):
    """One GET with the app's User-Agent. Raises on no answer or an HTTP error."""
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=LOOKUP_TIMEOUT)
    r.raise_for_status()
    return r.json()


@dataclass
class Place:
    lat: float
    lon: float
    name: str | None   # None: OpenStreetMap gave no area or city; resolve_place asks for --name
    found_by: str
    words: str   # what was found, for the user to catch a wrong match: no house number, no street
    country: str | None = None   # ISO code, upper case
    state: str | None = None   # a US state's code for the northeast, else its name
    zip: str | None = None
    region: str | None = None
    timezone: str | None = None


def _uniq(parts):
    out = []
    for p in parts:
        p = str(p or "").strip()
        if p and p.casefold() not in (o.casefold() for o in out):
            out.append(p)
    return out


def _us_state(code_or_name):
    """A US state as its two-letter code when it's in NORTHEAST, else as given."""
    s = str(code_or_name or "").strip()
    if s.upper().startswith("US-"):
        s = s[3:]
    for code, name in NORTHEAST.items():
        if s.upper() == code or s.casefold() == name.casefold():
            return code
    return s or None


def _zip5(code):
    m = re.match(r"^(\d{5})(-\d{4})?$", str(code or "").strip())
    return m.group(1) if m else None


def _osm_city(a):
    return next((a[k] for k in CITY_KEYS if a.get(k)), None)


def _osm_state(a):
    return a.get("ISO3166-2-lvl4") or a.get("state")


def _osm_words(r):
    a = r.get("address") or {}
    return ", ".join(_uniq([r.get("name"), a.get("neighbourhood"), *(a.get(k) for k in DISTRICT_KEYS), _osm_city(a),
                            a.get("state"), str(a.get("country_code") or "").upper()]))


def _first_words(text):
    return text.split(",")[0].strip()


def osm_name(results, text):
    """Decided 4: the user's own words when they named an area ("Logan Square"); after a street address or a building,
    OpenStreetMap's district or suburb, else the city, never its smallest area."""
    first = _first_words(text)
    for r in results if first else []:
        cat = r.get("category") or r.get("class")
        if cat in AREA_CATEGORIES and str(r.get("name") or "").casefold() == first.casefold():
            return r["name"]
    a = results[0].get("address") or {}
    for keys in (DISTRICT_KEYS, CITY_KEYS, ("neighbourhood", "county")):
        found = next((a[k] for k in keys if a.get(k)), None)
        if found:
            return found
    return None   # never the user's own text: it could be a street address, which would end up in config.toml


def place_from_osm(results, text, found_by="OpenStreetMap"):
    groups = []
    for r in results:
        a = r.get("address") or {}
        g = (str(a.get("country_code") or "").upper(), str(_osm_state(a) or ""))
        if g not in [x[0] for x in groups]:
            groups.append((g, r))
    if len(groups) > 1:
        raise SetupError(ambiguous([_osm_words(r) for _, r in groups]))
    r, a = results[0], results[0].get("address") or {}
    country = str(a.get("country_code") or "").upper() or None
    return Place(lat=round(float(r["lat"]), PLACE_DECIMALS), lon=round(float(r["lon"]), PLACE_DECIMALS),
                 name=osm_name(results, text) if text else osm_name([r], ""), found_by=found_by, words=_osm_words(r),
                 country=country, state=_us_state(_osm_state(a)) if country == "US" else None,
                 zip=_zip5(a.get("postcode")) if country == "US" else None, region=_osm_city(a))


def ambiguous(words):
    shown = "\n".join(f"  {i}) {w}" for i, w in enumerate(words[:AMBIGUOUS_SHOWN], 1))
    return (f"Several places match, in different states or countries:\n{shown}\n"
            "Ask the user which one, then add its city or state to --address (e.g. \"Logan Square, Chicago\").")


def find_address(text, get=None):
    get = get or http_get_json
    try:
        results = get(NOMINATIM_SEARCH, {"q": text, "format": "jsonv2", "addressdetails": 1,
                                         "limit": LOOKUP_RESULTS, "accept-language": "en"})
    except (requests.RequestException, ValueError):
        raise SetupError("Couldn't reach OpenStreetMap. Check the connection and run it again.") from None
    results = [r for r in results if isinstance(r, dict) and r.get("lat") and r.get("lon")] if isinstance(results, list) else []
    if not results:
        raise SetupError(NOT_FOUND)
    return place_from_osm(results, text)


def find_coordinates(lat, lon, get=None):
    """The area around coordinates the user gave (one Nominatim reverse lookup), for the name, country and ZIP."""
    get = get or http_get_json
    try:
        r = get(NOMINATIM_REVERSE, {"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1, "accept-language": "en"})
    except (requests.RequestException, ValueError):
        r = None
    if not isinstance(r, dict) or not r.get("address"):
        raise SetupError("Couldn't look up the area around these coordinates (OpenStreetMap didn't answer). "
                         "Run it again, or pass --address.")
    r = {**r, "lat": lat, "lon": lon, "name": ""}
    return place_from_osm([r], "", found_by="OpenStreetMap, from your coordinates")


def valid_timezone(name):
    try:
        ZoneInfo(str(name))
        return bool(name)
    except (ValueError, ZoneInfoNotFoundError):
        return False


def timezone_at(lat, lon, get=None):
    get = get or http_get_json
    try:
        tz = get(OPEN_METEO_FORECAST, {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1}).get("timezone")
    except (requests.RequestException, ValueError, AttributeError):
        tz = None
    if not valid_timezone(tz):
        raise SetupError("Couldn't get the timezone from Open-Meteo. Run it again, or pass --timezone "
                         "(an IANA name, like America/Chicago).")
    return tz



def resolve_place(args, get=None):
    if (args.lat is None) != (args.lon is None):
        raise SetupError("--lat and --lon go together.", 2)
    if args.lat is not None and not (-90 <= args.lat <= 90 and -180 <= args.lon <= 180):
        raise SetupError("--lat is between -90 and 90, --lon between -180 and 180.", 2)
    if args.address:
        place = find_address(args.address.strip(), get)
        if args.lat is not None:   # the user's coordinates win over the lookup's
            place.lat, place.lon = round(args.lat, PLACE_DECIMALS), round(args.lon, PLACE_DECIMALS)
            place.found_by += "; coordinates yours"
    else:
        place = find_coordinates(round(args.lat, PLACE_DECIMALS), round(args.lon, PLACE_DECIMALS), get)
    if args.timezone:
        if not valid_timezone(args.timezone):
            raise SetupError(f'--timezone "{args.timezone}" isn\'t a timezone name, like America/Chicago.', 2)
        place.timezone = args.timezone
    elif not place.timezone:
        place.timezone = timezone_at(place.lat, place.lon, get)
    if args.name is not None:
        place.name = clean_text(args.name, "--name")
    if not place.name:
        raise SetupError("The lookup found no area or city to call the home. Pass --name with what the page should call it "
                         '(like "Logan Square"); it is not taken from the address, which could be a street.')
    if args.region is not None:
        place.region = " ".join(args.region.split()) or None
    if args.zip is not None:
        if place.country not in (None, "US"):
            raise SetupError("--zip is for US homes: it links to pollen.com, which covers the US only.", 2)
        if not _zip5(args.zip):
            raise SetupError(f'--zip "{args.zip}": a US ZIP code has 5 digits.', 2)
        place.zip = _zip5(args.zip)
    return place


def clean_text(value, flag):
    text = " ".join(str(value).split())
    if not text:
        raise SetupError(f"{flag} is empty.", 2)
    return text


def saved_keys(root):
    try:
        return parse_dotenv((root / ".env").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def prepare_env(root):
    path = root / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    if not any(defines(line, "AIRGRADIENT_TOKEN") for line in text.splitlines()):
        write_env_key(path, "AIRGRADIENT_TOKEN", "")
    path.chmod(ENV_FILE_MODE)


class AirGradientSlow(SetupError):
    """AirGradient didn't answer in time (or couldn't be reached): trying again is the fix."""


class TokenRefused(SetupError):
    """AirGradient answered and refused the token: entering it again is the fix."""


def account_rows(token, timeout=LOOKUP_TIMEOUT):
    try:
        response = requests.get(f"{sources.API_BASE}/locations/measures/current", params={"token": token},
                                timeout=timeout, allow_redirects=False)
        if response.status_code in (401, 403):
            raise TokenRefused("AirGradient refused the token. Enter it again on the token page, then try again.")
        response.raise_for_status()
        rows = response.json()
        if response.status_code != 200 or not isinstance(rows, list):
            raise ValueError("Unexpected response")
        return [row for row in rows if isinstance(row, dict)]
    except (requests.Timeout, requests.ConnectionError):
        raise AirGradientSlow(f"AirGradient didn't answer within {timeout} s. Check the internet connection, then try again.") from None
    except (requests.RequestException, ValueError):
        raise SetupError("Couldn't read the monitors from AirGradient. Check the token in .env and API access, then try again.") from None


def wait_token(env, root):
    """Until the token page saves the token (or the wait runs out): then what the account has, so the user needn't say it."""
    end = time.monotonic() + WAIT_TOKEN_SECONDS
    while True:
        token = env_key("AIRGRADIENT_TOKEN", env) or env_key("AIRGRADIENT_TOKEN", saved_keys(root))
        if token:
            print(connected_line(account_rows(token)))
            return 0
        if time.monotonic() >= end:
            print(f"Not saved yet. Run {WAIT_TOKEN_CMD} again to keep waiting, or ask the user to type done when the page says Connected.")
            return 0
        time.sleep(WAIT_POLL_SECONDS)


def connected_line(rows):
    """One line for the user: the account's monitors by name and kind."""
    if not rows:
        return "Connected to AirGradient, but the account has no monitor with readings yet."
    names = [f'{publicmap.plain_text(r.get("locationName") or "") or "Unnamed monitor"} ({sources.monitor_kind(r) or "kind not set"})' for r in rows]
    return f"Connected to AirGradient: {len(rows)} monitor{'s' if len(rows) != 1 else ''}: {', '.join(names)}."


def choose_monitors(rows, args):
    chosen = {}
    unknown = [r for r in rows if r.get("locationType") not in ("indoor", "outdoor")]
    for kind in ("indoor", "outdoor"):
        other = "outdoor" if kind == "indoor" else "indoor"
        available_unknown = [r for r in unknown if str(r.get("locationId")) != str(getattr(args, other + "_id"))]
        candidates = [r for r in rows if r.get("locationType") == kind]
        wanted = getattr(args, kind + "_id")
        options = candidates + available_unknown
        match = [r for r in options if str(r.get("locationId")) == str(wanted)] if wanted is not None else []
        if len(match) == 1:
            chosen[kind] = {**match[0], "locationType": kind}
        elif wanted is not None or len(candidates) > 1 or (available_unknown and not candidates):
            words = "; ".join(f"{r.get('locationId')}: {publicmap.plain_text(r.get('locationName') or 'Unnamed monitor')}" for r in options)
            raise SetupError(f"Choose one of: {words or 'no matching monitors'}. Pass --{kind}-id <id>. "
                             "Set uncertain monitor types in AirGradient's dashboard, then run setup again.")
        elif candidates:
            chosen[kind] = candidates[0]
        if kind in chosen:
            unknown = [r for r in unknown if r.get("locationId") != chosen[kind].get("locationId")]
    if not chosen:
        raise SetupError("AirGradient lists no monitors with readings in this account. A monitor shows up once it has sent its first reading: check it shows readings in the AirGradient app, then run setup again.")
    if len({str(r.get("locationId")) for r in chosen.values()}) != len(chosen):
        raise SetupError("Choose a different monitor for indoors and outdoors in AirGradient.")
    for row in chosen.values():
        if not isinstance(row.get("locationId"), int) or isinstance(row["locationId"], bool) or row["locationId"] <= 0:
            raise SetupError("AirGradient returned a monitor without a valid id. Check it in its dashboard.")
    return chosen


def outdoor_source(place):
    try:
        world = publicmap.fetch_world()
        if not isinstance(world, list):
            raise ValueError("No public list")
        pick, _, _ = publicmap.suggest(world, place.lat, place.lon, datetime.now(timezone.utc))
        return pick
    except Exception:  # optional public discovery must never block household setup
        print("AirGradient's public list didn't answer. Outdoor air will be an estimate from Open-Meteo's forecast.")
        return "model"


def temp_unit(place):
    """°F for a home in the US, °C elsewhere (decision 8): the unit the page starts in; a viewer can still switch."""
    return "F" if place.country == "US" else "C"


def build_config(place, monitors, profiles, outdoor):
    values = {"name": place.name, "lat": place.lat, "lon": place.lon, "timezone": place.timezone}
    for kind, row in monitors.items():
        values[kind] = publicmap.plain_text(row.get("locationName") or kind)
        values[kind + "_id"] = row["locationId"]
    if place.country == "US" and place.zip:
        values["pollen_zip"] = place.zip
    if place.region:
        values["region"] = place.region
    lines = ["[place]", *(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in values.items()),
             "", "[profiles]", *(f"{key} = {str(key in profiles).lower()}" for key in PROFILES),
             ]
    lines += ["", "[home]", f"temp_unit = {json.dumps(temp_unit(place))}"]
    if outdoor is not None or place.country != "US":
        lines += ["", "[sources]"]
        if outdoor is not None:
            lines.append(f"outdoor_from = {json.dumps(outdoor)}")
        if place.country != "US":
            lines.append("smoke = false")
    return "\n".join(lines) + "\n"


def backup_path(path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    candidate, n = path.with_name(f"{path.name}.bak-{stamp}"), 2
    while candidate.exists():
        candidate, n = path.with_name(f"{path.name}.bak-{stamp}-{n}"), n + 1
    return candidate


def setup(args, env, root):
    prepare_env(root)
    profiles = [x for x in re.split(r"[,\s]+", args.profiles.lower()) if x and x != "none"]
    if any(p not in PROFILES for p in profiles):
        raise SetupError(f"Choose profiles from: {', '.join(PROFILES)}, or none. See docs/optional.md for adding one.", 2)
    token = env_key("AIRGRADIENT_TOKEN", env) or env_key("AIRGRADIENT_TOKEN", saved_keys(root))
    if not token:
        raise SetupError("Connect AirGradient first: open the app's printed setup link, or fill AIRGRADIENT_TOKEN in .env and restart.")
    rows = account_rows(token)
    monitors = choose_monitors(rows, args)
    place = resolve_place(args)
    outdoor = outdoor_source(place) if "outdoor" not in monitors else None
    text = build_config(place, monitors, profiles, outdoor)
    cfg = load_config({"CONFIG_TOML": text}, root)
    path = root / "config.toml"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        if old is not None:
            backup = backup_path(path)
            shutil.copy2(path, backup)
            print(f"Saved the previous config at {backup}")
        path.write_text(text, encoding="utf-8")
    print(f"Home: {place.name}, {place.lat}, {place.lon}; timezone {place.timezone}")
    print(f"Profiles: {', '.join(profiles) or 'none'}")
    print(f"Temperatures in °{cfg.temp_unit}" + (" (a US home)" if cfg.temp_unit == "F" else "") + ": change [home] temp_unit in config.toml to switch")
    if outdoor is not None:
        print(f"Outdoor air: {('estimate for your area (' + outdoor + ')') if isinstance(outdoor, str) else 'public monitor ' + str(outdoor)}")
    print(f"Settings: {path}")
    code = check_config.main(["--file", str(path)], env, root)
    if code:
        return code
    # The discovery call already read each monitor once; verify those same readings, without another request.
    problems = []
    for kind, row in monitors.items():
        age, words = age_words(row.get("timestamp"), datetime.now(timezone.utc))
        print(f'{kind} "{getattr(cfg.place, kind)}", {words}')
        if age is None or age > publicmap.STALE_READING:
            problems.append(f'The {kind} monitor has no recent reading. Check that it is plugged in and online.')
    for problem in problems:
        print(problem)
    print("Not live yet: fix the readings above and run setup again." if problems else "Live OK")
    return 1 if problems else 0


def railway(service, root):
    values = {"CONFIG_TOML": (root / "config.toml").read_text(encoding="utf-8")}
    keys = saved_keys(root)
    values.update((name, env_key(name, keys)) for name in KEY_NAMES if env_key(name, keys))
    for name, value in values.items():
        try:
            # --skip-deploys: each variable would otherwise start its own deploy, empty or failing before the code is up.
            subprocess.run(["railway", "variable", "set", name, "--stdin", "--service", service, "--skip-deploys"],
                           input=value, text=True, capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise SetupError(f"Railway did not accept {name}. Check the service name and CLI login, then try again.") from None
        print(f"Sent {name}")
    print(f"Variables set. Deploy with (ask the user first): railway up --service {service} --detach (first deploy), "
          f"or railway redeploy --service {service} --yes (a service already running)")
    return 0


def port_from(env):
    """The server's port: PORT when it is a number, else the default (server.py would not start on a bad one)."""
    try:
        port = int(env.get("PORT") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


APP_RE = re.compile(r"window\.APP = (\{.*?\});</script>", re.S)


def age_words(ts, now):
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None, "no time on the last reading"
    if t.tzinfo is None:
        return None, "no time on the last reading"
    secs = (now - t).total_seconds()
    mins = int(secs // 60)
    words = ("just now" if mins < 1 else f"{mins} min ago" if mins < 60 else
             f"{mins // 60} h ago" if mins < 24 * 60 else f"{mins // (24 * 60)} days ago")
    return now - t, f"last reading {words}"


def live(url, env, root, get=None, now=None):
    get = get or (lambda u: requests.get(u, timeout=LIVE_TIMEOUT))
    now = now or datetime.now(timezone.utc)
    base = url.rstrip("/")
    problems = []

    def problem(text):
        problems.append(text)
        print(f"Problem: {text}")

    try:
        health = get(f"{base}/health").json()
    except Exception as e:   # not running, wrong port, not this app
        print(f"The page doesn't answer at {base} ({type(e).__name__}). Start it (SETUP.md, Start and verify), or pass its address: "
              "setup.py --live http://localhost:<port>")
        return 1
    if not isinstance(health, dict) or health.get("status") != "ok":
        print(f"{base}/health didn't say ok: is this Home Air Quality?")
        return 1
    print(f"Page: answers at {base}")
    token = bool(health.get("airgradient_token_set"))
    print(f"Token: {'set' if token else 'missing'}")

    cfg = None
    try:
        cfg = load_config({k: v for k, v in env.items() if k != "DEMO"}, root)
    except ConfigError as e:
        print(f"Note: config.toml here doesn't load ({e}), so the page's settings weren't compared.")
    try:
        m = APP_RE.search(get(f"{base}/").text)
        app = json.loads(m.group(1)) if m else None
    except Exception:
        app = None
    if app is None:
        problem("the page has no settings (window.APP): is this Home Air Quality?")
    elif "now" in app:
        problem("the page runs the demo (made-up data). Restart it from the folder with config.toml.")
    elif cfg is not None:
        settings_check(app, cfg, problem)

    if token:
        current_check(get, base, cfg, now, problem)
    if problems:
        print("Not live yet: fix the problems above, then run setup.py --live again.")
        return 1
    if not token:
        print("Not live yet: add AIRGRADIENT_TOKEN to .env and restart the app.")
        return 1
    print("Live OK")
    return 0


def settings_check(app, cfg, problem):
    place = app.get("place") or {}
    p = cfg.place
    wanted = {"name": p.name, "indoor monitor": p.indoor, "outdoor monitor": p.outdoor}
    shown = {"name": place.get("name"), "indoor monitor": place.get("indoor"), "outdoor monitor": place.get("outdoor")}
    of = cfg.outdoor_from
    if of is not None:
        wanted["outdoor source"] = of
        o = app.get("outdoor_from") or {}
        shown["outdoor source"] = o.get("id") if o.get("kind") == "monitor" else o.get("kind")
    wanted["profiles"] = sorted(k for k, v in cfg.profiles.items() if v)
    shown["profiles"] = sorted(k for k, v in (app.get("profiles") or {}).items() if v)
    off = [k for k in wanted if wanted[k] != shown[k]]
    for k in off:
        problem(f"the page's {k} is {json.dumps(shown[k])}, config.toml's is {json.dumps(wanted[k])}. Restart the "
                "server: it reads config.toml when it starts.")
    if not off:
        print("Settings: the name, monitors, profiles" + (" and outdoor source" if of is not None else "")
              + " match config.toml")


def current_check(get, base, cfg, now, problem):
    try:
        r = get(f"{base}/api/current")
        data = r.json()
    except Exception as e:
        problem(f"/api/current didn't answer ({type(e).__name__}).")
        return
    if getattr(r, "status_code", 200) >= 400:
        err = data.get("error") if isinstance(data, dict) else None
        problem(f"AirGradient answered with an error: {publicmap.plain_text(err or r.status_code)}. Check the token "
                "in .env, then restart the server.")
        return
    if isinstance(data, dict) and data.get("state") == "no_token":
        problem("the page has no token yet. Open the app's printed setup link, or fill AIRGRADIENT_TOKEN in .env and restart.")
        return
    rows = [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
    expect = ([k for k, n in (("indoor", cfg.place.indoor), ("outdoor", cfg.place.outdoor)) if n is not None]
              if cfg else ["indoor", "outdoor"])
    for kind in expect:
        wanted_id = getattr(cfg.place, kind + "_id") if cfg else None
        row = next((x for x in rows if x.get("locationType") == kind and "source" not in x
                    and (wanted_id is None or x.get("locationId") == wanted_id)), None)
        if row is None:
            problem(f"no {kind} monitor: the token's account has no monitor set as {kind}. Set one as {kind} in "
                    "AirGradient's dashboard, or check it's the right account's token.")
            continue
        age, words = age_words(row.get("timestamp"), now)
        name = publicmap.plain_text(row.get("locationName") or "") or f"Monitor {row.get('locationId')}"
        model = f" ({publicmap.plain_text(row['model'])})" if row.get("model") else ""
        print(f'{kind} "{name}"{model}, {words}')
        if age is None or age > publicmap.STALE_READING:
            problem(f'the {kind} monitor "{name}" has no recent reading: is it plugged in and online?')
    if cfg is not None and cfg.place.outdoor is None:
        src = next((x for x in rows if isinstance(x.get("source"), dict)), None)
        if src is None:
            problem("no outdoor source on the page, though the home has no outdoor monitor.")
            return
        s = src["source"]
        if s.get("kind") == "monitor":
            _, words = age_words(src.get("timestamp"), now)
            km = f", {s['distance_km']:.1f} km" if isinstance(s.get("distance_km"), (int, float)) else ""
            print(f'outdoor source: public monitor "{publicmap.plain_text(s.get("name") or s.get("id"))}"{km}, {words}')
        elif s.get("kind") == "area":
            print("outdoor source: the estimate for your area"
                  + (f", from {s['area_count']} public monitors" if s.get("area_count") else ""))
        else:
            print("outdoor source: Open-Meteo's forecast for your area")
        if s.get("fallback"):
            print("Note: the chosen public monitor isn't reporting now (or AirGradient's list didn't answer): the page "
                  "shows the estimate for your area until it's back.")


def status(env, root):
    """What's done and the one next command, as SETUP.md names it. Read-only: writes nothing, asks nothing; its one
    network request (the account's latest readings) is a GET. Keys are reported as set or not, never their values."""
    env = {k: v for k, v in env.items() if k != "DEMO"}
    rows, next_cmd = [], None

    def step(name, done, words, cmd):
        nonlocal next_cmd
        rows.append(f"  {name}: {'done' if done else 'not yet'}" + (f": {words}" if words else ""))
        if not done and next_cmd is None:
            next_cmd = cmd

    try:
        text = (root / ".env").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    token_set = check_config.keys_present(env, root)["AIRGRADIENT_TOKEN"]
    prepared = token_set or any(defines(line, "AIRGRADIENT_TOKEN") for line in text.splitlines())
    step("1. Token entry (.env)", prepared, "" if prepared else "no AIRGRADIENT_TOKEN line yet", SETUP_CMD)
    step("2. AirGradient connected", token_set, "" if token_set else "no token yet",
         f"{START_CMD} (then open the ?setup= link it writes to app.log; the user enters the token on that page)")

    cfg, problem = None, None
    # where load_config reads the home from, in its order: the variables win over the file
    source = next((k for k in ("CONFIG_TOML", "CONFIG_FILE") if env.get(k, "").strip()), "config.toml")
    try:
        cfg = load_config(env, root)
    except ConfigError as e:
        problem = str(e)
    if cfg is not None:
        p = cfg.place
        monitors = [f'{kind} "{getattr(p, kind)}"' for kind in ("indoor", "outdoor") if getattr(p, kind) is not None]
        profiles = ", ".join(k for k, v in cfg.profiles.items() if v) or "none"
        words = f"{p.name}; monitors: {', '.join(monitors)}; profiles: {profiles}"
    elif problem and source == "config.toml":
        words = f"{problem}. Running setup again replaces it and keeps a copy"
    elif problem:
        words = f"{problem}. Fix the {source} variable: it wins over config.toml"
    else:
        words = "no config.toml yet"
    fix = HOME_CMD if source == "config.toml" else f"{RUN} scripts/check_config.py"
    step(f"3. Home and monitors ({source})", cfg is not None, words, fix)

    if not (token_set and cfg is not None):
        rows.append("  4. Readings come in: not checked yet (needs the steps above)")
    else:
        token = env_key("AIRGRADIENT_TOKEN", env) or env_key("AIRGRADIENT_TOKEN", saved_keys(root))
        try:
            account = account_rows(token, timeout=STATUS_TIMEOUT)
        except AirGradientSlow:
            step("4. Readings come in", False, f"couldn't check: AirGradient didn't answer within {STATUS_TIMEOUT} s; try again in a minute", STATUS_CMD)
        except TokenRefused:
            step("4. Readings come in", False, "AirGradient refused the token",
                 f"{START_CMD} (then open the ?setup= link it writes to app.log and enter the token again)")
        except SetupError:
            step("4. Readings come in", False, "couldn't check: AirGradient's answer couldn't be read; try again in a minute", STATUS_CMD)
        else:
            seen, missing, stale = [], [], []
            for kind in ("indoor", "outdoor"):
                name, wanted = getattr(cfg.place, kind), getattr(cfg.place, kind + "_id")
                if name is None:
                    continue
                row = next((r for r in account if (r.get("locationId") == wanted if wanted is not None
                                                   else r.get("locationType") == kind)), None)
                if row is None:
                    missing.append(f'the {kind} monitor "{name}" isn\'t in this account')
                    continue
                age, when = age_words(row.get("timestamp"), datetime.now(timezone.utc))
                seen.append(f'{kind} "{name}", {when}')
                if age is None or age > publicmap.STALE_READING:
                    stale.append(f'the {kind} monitor "{name}" has no recent reading')
            if missing:
                step("4. Readings come in", False, "; ".join(missing + stale),
                     f"run setup again to choose from this account's monitors: {HOME_CMD}")
            else:
                step("4. Readings come in", not stale, "; ".join(stale or seen),
                     f"check the monitor is plugged in and shows readings in the AirGradient app, then run {STATUS_CMD}")

    print("Setup status:")
    for row in rows:
        print(row)
    if next_cmd is not None:
        print(f"Next: {next_cmd}")
        return 0
    # Done is SETUP.md's "Done when": the running page's --live check ends with Live OK, which needs the page started.
    port = port_from(env)
    start = f"cd {root} && {'PORT=' + str(port) + ' ' if port != DEFAULT_PORT else ''}{START_CMD}"
    print("Steps 1–4 done. Last, check the running page: it should end with Live OK.")
    print(f"Page: http://localhost:{port}")
    print(f"Next: {start}, then {SETUP_CMD} --live http://localhost:{port} "
          "(Railway or Docker: --live <the page's address>)")
    return 0


def page_answers(url, env, root):
    """After the system starts the app: wait for /health, then the --live check."""
    end = time.monotonic() + STARTUP_WAIT
    while time.monotonic() < end:
        try:
            if requests.get(f"{url}/health", timeout=WAIT_POLL_SECONDS).ok:
                return live(url, env, root)
        except requests.RequestException:
            pass
        time.sleep(WAIT_POLL_SECONDS)
    return 1


def start_at_login(state, env, root):
    import autostart
    run = lambda cmd: subprocess.run(cmd, capture_output=True).returncode
    home = Path(env.get("HOME") or Path.home())
    if state == "off":
        return autostart.turn_off(root, home, run, shutil.which, sys.platform)
    url = f"http://localhost:{port_from(env)}"
    return autostart.turn_on(root, home, env, run, shutil.which, sys.platform, lambda: page_answers(url, env, root))


def parser():
    ap = argparse.ArgumentParser(description="Set up a home from its location and profiles. With no answers, prepare .env.")
    ap.add_argument("--address", help="an address, neighborhood or nearby landmark with its city")
    ap.add_argument("--profiles", default="none", help="toddler,sinus,runner, or none (default)")
    ap.add_argument("--indoor-id", type=int, help="which indoor monitor, only when ambiguous")
    ap.add_argument("--outdoor-id", type=int, help="which outdoor monitor, only when ambiguous")
    ap.add_argument("--name", help="a correction to the area's name")
    ap.add_argument("--lat", type=float, help="latitude, together with --lon")
    ap.add_argument("--lon", type=float, help="longitude, together with --lat")
    ap.add_argument("--zip", help="a correction to a US ZIP code")
    ap.add_argument("--region", help="a correction to the city or region")
    ap.add_argument("--timezone", help="a correction using an IANA timezone name")
    ap.add_argument("--live", nargs="?", const="", metavar="URL", help="check the running page with GET requests")
    ap.add_argument("--status", action="store_true", help="list what's done and the next command; changes nothing")
    ap.add_argument("--start-at-login", choices=("on", "off"),
                    help="start the app by itself at login (a Mac or Linux with systemd), or stop doing so")
    ap.add_argument("--home-server", action="store_true",
                    help="prepare a folder for a home server with Docker (Compose, settings, token) and say the two steps")
    ap.add_argument("--wait-token", action="store_true",
                    help=f"wait up to {WAIT_TOKEN_SECONDS} s for the token page to save the token, then say what the account has")
    return ap


def main(argv, env, root=ROOT):
    if argv[:1] == ["railway"]:
        ap = argparse.ArgumentParser(description="Send saved config and keys to a Railway service through stdin.")
        ap.add_argument("--service", required=True)
        args = ap.parse_args(argv[1:])
    else:
        args = parser().parse_args(argv)
    try:
        if argv[:1] == ["railway"]:
            return railway(args.service, root)
        if args.status:
            return status(env, root)
        if args.wait_token:
            return wait_token(env, root)
        if args.home_server:
            import homeserver
            return homeserver.prepare(root)
        if args.start_at_login:
            return start_at_login(args.start_at_login, env, root)
        if args.live is not None:
            return live(args.live or f"http://localhost:{port_from(env)}", env, root)
        if not args.address and args.lat is None and args.lon is None:
            prepare_env(root)
            token = env_key("AIRGRADIENT_TOKEN", env) or env_key("AIRGRADIENT_TOKEN", saved_keys(root))
            if not token:
                print("Prepared .env. Open the app's startup link to connect AirGradient, or open .env in your text editor.")
                return 0
            print(connected_line(account_rows(token)))   # after the page connected: what the account has, for the agent to say
            return 0
        return setup(args, env, root)
    except (SetupError, ConfigError, OSError, UnicodeError) as error:
        print(str(error) if isinstance(error, (SetupError, ConfigError)) else "Couldn't read or write a setup file. Check its permissions.")
        return error.code if isinstance(error, SetupError) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
