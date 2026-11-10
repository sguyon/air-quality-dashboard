"""Sets up a home in one command, from the answers to SETUP.md's questions: finds the place, picks the outdoor source,
writes config.toml from config.example.toml (its comments kept) and checks it like scripts/check_config.py.

  setup.py --address "Times Square, New York" --monitors indoor [answers] --check   the recap, nothing written
  setup.py --address "Times Square, New York" --monitors indoor [answers]           writes config.toml, then checks it
  setup.py token                     the user, in their own terminal: saves the AirGradient token in .env, unseen
  setup.py --live [URL]              asks the running page whether it reads the monitors (GET requests only)

The address goes to OpenStreetMap's Nominatim once (then Open-Meteo if it finds nothing); only the coordinates rounded
to about 1 km are kept, written or printed. Keys are read only as set or missing (check_config.keys_present).
"""
import argparse
import difflib
import getpass
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_config  # noqa: E402
import publicmap  # noqa: E402
import token_setup  # noqa: E402
from config import APPLIANCES, PLACE_DECIMALS, PROFILES, ConfigError, load_config, real_value, write_env_key  # noqa: E402

REPO_URL = "https://github.com/sguyon/home-air-quality"
# Nominatim's policy asks for a User-Agent naming the app; one request per run keeps under its 1 request a second
USER_AGENT = f"home-air-quality-setup/1.0 (+{REPO_URL})"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
OPEN_METEO_SEARCH = "https://geocoding-api.open-meteo.com/v1/search"   # names and postal codes, not street addresses
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"   # timezone=auto gives a point's timezone
LOOKUP_RESULTS = 3   # matches asked of Nominatim: enough to see two states for one name, and a square behind its street
OPEN_METEO_RESULTS = 10   # matches asked of Open-Meteo: it returns near-namesakes ("Times Square Rock"), filtered out after
AMBIGUOUS_SHOWN = 3   # matches listed when a name is in several states or countries
LOOKUP_TIMEOUT = 15   # s: each lookup's wait
# Nominatim categories that are an area someone could say they live in ("Logan Square"): the name is the user's words
AREA_CATEGORIES = ("place", "boundary")
# OpenStreetMap's address parts for the home's name after a street address, district before city, smallest last
# (Decided 4: "Capitol Hill", not "Swallow Hill Historic District")
DISTRICT_KEYS = ("suburb", "city_district", "borough", "quarter")
CITY_KEYS = ("city", "town", "village", "hamlet")
# the example's pollen seasons are for these states; elsewhere they're left out unless --season gives the region's
NORTHEAST = {"CT": "Connecticut", "ME": "Maine", "MA": "Massachusetts", "NH": "New Hampshire", "RI": "Rhode Island",
             "VT": "Vermont", "NY": "New York", "NJ": "New Jersey", "PA": "Pennsylvania"}
# Google's pollen types: a season named after one shows today's level beside its bar on the pollen card
SEASON_NAMES = ("Tree", "Grass", "Weed")
LEAP_YEAR = 2024   # a year with Feb 29, to check a season's dates
# a month's name, full or short, as its number
MONTH_NUMBERS = {k: n for n in range(1, 13) for k in (datetime(LEAP_YEAR, n, 1).strftime("%B").lower(),
                                                      datetime(LEAP_YEAR, n, 1).strftime("%b").lower())}
DEFAULT_PORT = 5555   # server.py's port without PORT
TOKEN_CHOICES = ("now", "later")   # --token's answers
PORT_TRIES = 20   # ports tried after a taken one, for the run command
LIVE_TIMEOUT = 30   # s: the page's wait on AirGradient and the outdoor source before /api/current answers
GCLOUD_TIMEOUT = 20   # s: `gcloud auth list` can be slow on its first run
PROFILE_WORDS = {"toddler": "toddler", "sinus": "sinus or allergies", "runner": "runner"}
APPLIANCE_WORDS = {"dehumidifier": "the dehumidifier", "ac_dry": "the air conditioner's dry mode"}
NOT_FOUND = ("Couldn't find it. Try a landmark near you, or a house number on your street (it doesn't have to be "
             "yours), or pass --lat and --lon from a map app.")


class SetupError(Exception):
    """A stop, in words for the user. code 1: something to fix or choose; 2: an answer the command can't take."""

    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


# ---------- Finding the place ----------

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


def place_from_open_meteo(results, text):
    parts = [p.strip() for p in text.split(",") if p.strip()]
    first, rest = parts[0], parts[1:]
    same = [r for r in results if str(r.get("name") or "").casefold() == first.casefold()]
    results = same or results
    if rest:   # "Logan Square, Chicago": keep the matches whose state, county, city or country is named after the comma
        keys = ("admin1", "admin2", "admin3", "admin4", "country", "country_code")
        narrowed = [r for r in results if all(any(p.casefold() == str(r.get(k) or "").casefold() for k in keys) for p in rest)]
        results = narrowed or results
    groups = []
    for r in results:
        g = (r.get("country_code"), r.get("admin1"))
        if g not in [x[0] for x in groups]:
            groups.append((g, r))
    words = lambda r: ", ".join(_uniq([r.get("name"), r.get("admin3"), r.get("admin1"), r.get("country_code")]))
    if len(groups) > 1:
        raise SetupError(ambiguous([words(r) for _, r in groups]))
    r = results[0]
    country = str(r.get("country_code") or "").upper() or None
    postcodes = r.get("postcodes") or []
    tz = r.get("timezone")
    return Place(lat=round(float(r["latitude"]), PLACE_DECIMALS), lon=round(float(r["longitude"]), PLACE_DECIMALS),
                 name=r["name"] if same else (r["name"] if first[:1].isdigit() else first), found_by="Open-Meteo",
                 words=words(r), country=country, state=_us_state(r.get("admin1")) if country == "US" else None,
                 zip=_zip5(postcodes[0]) if country == "US" and postcodes else None, region=r.get("admin3"),
                 timezone=tz if valid_timezone(tz) else None)


def find_address(text, get=None):
    """Nominatim with the text as given; if nothing comes back (or it doesn't answer), Open-Meteo with the same text."""
    get = get or http_get_json
    reached = False
    try:
        results = get(NOMINATIM_SEARCH, {"q": text, "format": "jsonv2", "addressdetails": 1, "limit": LOOKUP_RESULTS,
                                         "accept-language": "en"})
        reached = True
        results = [r for r in results if isinstance(r, dict) and r.get("lat") and r.get("lon")] if isinstance(results, list) else []
        if results:
            return place_from_osm(results, text)
    except (requests.RequestException, ValueError):
        pass
    try:
        first = _first_words(text)
        data = get(OPEN_METEO_SEARCH, {"name": first, "count": OPEN_METEO_RESULTS, "language": "en", "format": "json"})
        reached = True
        results = [r for r in (data.get("results") or []) if isinstance(r, dict) and r.get("latitude") is not None] \
            if isinstance(data, dict) else []
        if results:
            return place_from_open_meteo(results, text)
    except (requests.RequestException, ValueError):
        pass
    if not reached:
        raise SetupError("Couldn't reach the place lookups (OpenStreetMap, then Open-Meteo). Check the internet "
                         "connection and run it again.")
    raise SetupError(NOT_FOUND)


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


# ---------- The answers ----------

def parse_list(value, known, what):
    """A comma-separated pick from `known`, or "none". Unknown items stop with the list of known ones."""
    items = [x.strip().lower() for x in re.split(r"[,\s]+", value or "") if x.strip()]
    if items in ([], ["none"]):
        return []
    unknown = [x for x in items if x not in known]
    if unknown:
        raise SetupError(f"Not {what}: {', '.join(unknown)}. Use any of: {', '.join(known)}, or none.", 2)
    return [k for k in known if k in items]


def parse_profiles(value):
    items = [x.strip().lower() for x in re.split(r"[,\s]+", value or "") if x.strip()]
    if items in ([], ["none"]):
        return []
    unknown = [x for x in items if x not in PROFILES]
    if unknown:
        raise SetupError(f"Not a profile yet: {', '.join(unknown)}. The page knows {', '.join(PROFILES)}. Adding one is "
                         "a code change: see SETUP.md, \"Adding a profile\".", 2)
    return [k for k in PROFILES if k in items]


def parse_day(text, where):
    """ "Mar 10" or "March 10" as [3, 10]."""
    m = re.match(r"^([A-Za-z]+)\.?\s+(\d{1,2})$", text.strip())
    month = MONTH_NUMBERS.get(m.group(1).lower()) if m else None
    if month is None:
        raise SetupError(f'{where}: "{text.strip()}" isn\'t a date like "Mar 10".', 2)
    day = int(m.group(2))
    try:
        datetime(LEAP_YEAR, month, day)
    except ValueError:
        raise SetupError(f'{where}: "{text.strip()}" isn\'t a day of the year.', 2) from None
    return [month, day]


def _range(text, where):
    parts = re.split(r"\s*[–—-]\s*|\s+to\s+", text.strip())
    if len(parts) != 2:
        raise SetupError(f'{where}: "{text.strip()}" isn\'t a range like "Mar 10 – May 31".', 2)
    return parse_day(parts[0], where), parse_day(parts[1], where)


SEASON_FORM = 'Use the form "Tree: Mar 10 – May 31, peak Apr 1 – May 10" (the peak is optional; names: Tree, Grass, Weed).'


def parse_season(text):
    """One --season: "Tree: Jan 15 – Apr 30", optionally ", peak Mar 1 – Mar 31". Without a peak, the whole season
    is marked as its peak (no date is made up)."""
    name, sep, rest = text.partition(":")
    if not sep:
        raise SetupError(f'--season "{text}": no name. {SEASON_FORM}', 2)
    name = name.strip().capitalize()
    if name not in SEASON_NAMES:
        raise SetupError(f'--season "{text}": "{name}" isn\'t one of {", ".join(SEASON_NAMES)}, the pollen types '
                         f"Google reports. {SEASON_FORM}", 2)
    parts = re.split(r"\s*,\s*peak\s+", rest.strip(), maxsplit=1, flags=re.I)
    span, peak = parts[0], (parts[1] if len(parts) > 1 else None)
    where = f"--season {name}"
    start, end = _range(span, where)
    if tuple(start) > tuple(end):
        raise SetupError(f"{where}: it runs past the new year, which the season calendar can't draw (it runs January "
                         f"to December). Give the part within one year, e.g. \"{name}: Jan 1 – Mar 15\".", 2)
    peak_from, peak_to = _range(peak, where) if peak else (start, end)
    if not (tuple(start) <= tuple(peak_from) <= tuple(peak_to) <= tuple(end)):
        raise SetupError(f"{where}: the peak has to fall within the season, in order.", 2)
    return {"name": name, "start": start, "peak": [peak_from, peak_to], "end": end, "peak_given": bool(peak)}


def parse_seasons(values):
    seasons = [parse_season(v) for v in values or []]
    names = [s["name"] for s in seasons]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise SetupError(f"--season: {', '.join(twice)} is given twice; give each type once.", 2)
    return seasons


def clean_text(value, flag):
    v = " ".join(str(value).split())
    if not v:
        raise SetupError(f"{flag} is empty.", 2)
    return v


@dataclass
class Answers:
    monitors: str
    indoor: str | None
    outdoor: str | None
    profiles: list
    appliances: list
    outdoor_pick: str | int
    token: str
    pollen: str
    seasons: list | None   # None: no --season given
    notes: list = field(default_factory=list)


def read_answers(args):
    indoor = clean_text(args.indoor_name or "home", "--indoor-name") if args.monitors in ("indoor", "both") else None
    outdoor = clean_text(args.outdoor_name or "outside", "--outdoor-name") if args.monitors in ("outdoor", "both") else None
    notes = []
    if args.indoor_name and indoor is None:
        notes.append("--indoor-name left out: no indoor monitor.")
    if args.outdoor_name and outdoor is None:
        notes.append("--outdoor-name left out: no outdoor monitor.")
    if args.token not in TOKEN_CHOICES:   # not argparse `choices`: its error would repeat the value, maybe a real token
        raise SetupError("--token takes now or later. The token itself is never an argument: run setup.py token.", 2)
    pick = (args.outdoor_from or "suggest").strip().lower()
    if pick not in ("suggest", "area", "model"):
        if not pick.isdigit() or int(pick) <= 0:
            raise SetupError(f'--outdoor-from "{args.outdoor_from}": use suggest, a monitor\'s id (a number), area or model.', 2)
        pick = int(pick)
    if outdoor is not None and args.outdoor_from:
        notes.append("--outdoor-from left out: the outdoor monitor gives the outdoor air.")
    return Answers(args.monitors, indoor, outdoor, parse_profiles(args.profiles),
                   parse_list(args.dry, APPLIANCES, "something the page can turn on"), pick, args.token, args.pollen,
                   parse_seasons(args.season) if args.season else None, notes)


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


# ---------- The outdoor source ----------

@dataclass
class Outdoor:
    choice: int | str | None   # what config.toml gets as outdoor_from; None with an outdoor monitor
    lines: list   # the recap's lines


def pick_outdoor(answers, place, fetch=None, now=None):
    if answers.outdoor is not None:
        return Outdoor(None, [f'Outdoor air: your outdoor monitor, called "{answers.outdoor}"'])
    fetch = fetch or publicmap.fetch_world
    now = now or datetime.now(timezone.utc)
    try:
        world = fetch()
        world = world if isinstance(world, list) else []
    except Exception as e:   # no network, AirGradient down, bad JSON
        if answers.outdoor_pick in ("area", "model"):
            return Outdoor(answers.outdoor_pick, [f"Outdoor air: {source_words(answers.outdoor_pick, None, 0)} "
                                                  f"(AirGradient's public list didn't answer, so no monitors listed)"])
        raise SetupError(f"AirGradient's public list of monitors didn't answer ({type(e).__name__}), so the outdoor "
                         "source can't be chosen. Run it again in a minute, or pass --outdoor-from area or model.") from e
    suggested, _, count = publicmap.suggest(world, place.lat, place.lon, now)
    pick = suggested if answers.outdoor_pick == "suggest" else answers.outdoor_pick
    mon = None
    if isinstance(pick, int):
        mon = publicmap.find(world, pick)
        if mon is None:
            raise SetupError(f"{pick} isn't an outdoor monitor in AirGradient's public list. Pick one from the list "
                             "(--check shows it), or area or model.", 2)
    head = f"Outdoor air: {source_words(pick, mon, count, place, now)}"
    head += " (the suggestion)" if pick == suggested else " (the user's pick)"
    lines = [head] + [f"  {x}" for x in check_config.suggest_list(world, place.lat, place.lon, now)]
    lines.append("  " + check_config.suggest_line(world, place.lat, place.lon, now))
    return Outdoor(pick, lines)


def source_words(pick, mon, count, place=None, now=None):
    if pick == "area":
        return f"an estimate for your area, from the public outdoor monitors within {publicmap.AREA_KM} km ({count} now)"
    if pick == "model":
        return "an estimate for your area, from Open-Meteo's forecast alone"
    km = publicmap.km_between(place.lat, place.lon, mon["latitude"], mon["longitude"])
    state = ("a public monitor reporting now" if publicmap.reporting(mon, now)
             else "a public monitor, not reporting now: the page shows the estimate until it's back")
    return f"{publicmap.name_of(mon)}, {km:.1f} km away, {state}"


# ---------- Writing the file ----------

def toml_str(s):
    return json.dumps(str(s), ensure_ascii=False)   # a JSON string is a TOML basic string


class Lines:
    """config.example.toml as lines, edited by section and key. Every edit must find its line: a changed example
    stops the command instead of writing a half-edited file."""
    HEADER = re.compile(r"^\[\[?([^\]]+)\]\]?\s*$")

    def __init__(self, text):
        self.lines = text.splitlines()

    def find(self, section, key):
        current, commented = None, None
        for i, line in enumerate(self.lines):
            m = self.HEADER.match(line)
            if m:
                current = m.group(1).strip()
                continue
            if current != section:
                continue
            if re.match(rf"^{key}\s*=", line):
                return i
            if commented is None and re.match(rf"^#\s*{key}\s*=", line):
                commented = i
        if commented is None:
            raise SetupError(f"config.example.toml has no {section}.{key} line any more: setup.py needs updating.")
        return commented

    def set(self, section, key, value):
        self.lines[self.find(section, key)] = f"{key} = {value}"

    def drop(self, section, key):
        """The key's line and the comment line just above it."""
        i = self.find(section, key)
        start = i - 1 if i > 0 and self.lines[i - 1].startswith("#") else i
        del self.lines[start:i + 1]

    def replace_from(self, prefix, new_lines):
        i = next((i for i, line in enumerate(self.lines) if line.startswith(prefix)), None)
        if i is None:
            raise SetupError(f'config.example.toml has no line starting "{prefix}" any more: setup.py needs updating.')
        self.lines[i:] = new_lines

    def text(self):
        return "\n".join(self.lines).rstrip("\n") + "\n"


SEASONS_START = "# Pollen seasons:"   # the example's pollen season blocks run from this comment to the end of the file
HEADER_START = "# Copy this file to config.toml"


@dataclass
class Plan:
    place: Place
    answers: Answers
    outdoor: Outdoor
    us: bool
    seasons: str   # "example", "given" or "none"


def plan_seasons(place, answers):
    if answers.seasons is not None:
        return "given"
    return "example" if place.country == "US" and place.state in NORTHEAST else "none"


def season_block(s):
    (pf, pt) = s["peak"]
    return ["[[pollen_seasons]]", f"name = {toml_str(s['name'])}", f"start = [{s['start'][0]}, {s['start'][1]}]",
            f"peak = [[{pf[0]}, {pf[1]}], [{pt[0]}, {pt[1]}]]", f"end = [{s['end'][0]}, {s['end'][1]}]"]


def build_config(example, plan):
    p, a = plan.place, plan.answers
    t = Lines(example)
    i = next((i for i, line in enumerate(t.lines) if line.startswith(HEADER_START)), None)
    if i is None:
        raise SetupError(f'config.example.toml has no line starting "{HEADER_START}" any more: setup.py needs updating.')
    t.lines[i] = "# Written by scripts/setup.py from config.example.toml. Edit it freely; scripts/check_config.py checks it."
    t.set("place", "name", toml_str(p.name))
    t.set("place", "lat", f"{p.lat:.{PLACE_DECIMALS}f}")
    t.set("place", "lon", f"{p.lon:.{PLACE_DECIMALS}f}")
    t.set("place", "timezone", toml_str(p.timezone))
    for key, name in (("indoor", a.indoor), ("outdoor", a.outdoor)):
        t.set("place", key, toml_str(name)) if name is not None else t.drop("place", key)
    if plan.us and p.zip:
        t.set("place", "pollen_zip", toml_str(p.zip))
    else:
        t.drop("place", "pollen_zip")
    if p.region:
        t.set("place", "region", toml_str(p.region))
    for k in PROFILES:
        t.set("profiles", k, "true" if k in a.profiles else "false")
    appliances = a.appliances if a.indoor is not None else []   # drying reads the indoor monitor: none without one
    t.set("home", "appliances", "[" + ", ".join(toml_str(x) for x in appliances) + "]")
    if plan.outdoor.choice is not None:
        c = plan.outdoor.choice
        t.set("sources", "outdoor_from", str(c) if isinstance(c, int) else toml_str(c))
    if not plan.us:
        t.set("sources", "smoke", "false")
    if a.pollen == "off":
        t.set("sources", "pollen", "false")
    if plan.seasons == "given":
        lines = ["# Pollen seasons: typical dates, not a forecast (looked up at setup). Dates are [month, day]."]
        for s in a.seasons:
            lines += [""] + season_block(s)
        t.replace_from(SEASONS_START, lines)
    elif plan.seasons == "none":
        t.replace_from(SEASONS_START, [
            "# Pollen seasons: none here, so the pollen card shows no season calendar. The example's dates are for the",
            "# northeastern US. To add your region's typical dates, add [[pollen_seasons]] blocks with name (Tree, Grass",
            "# or Weed), start, peak ([from, to]) and end, as [month, day]."])
    return t.text()


# ---------- The recap ----------

def day_words(d):
    return f"{datetime(LEAP_YEAR, *d).strftime('%b')} {d[1]}"


def recap(plan, keys):
    p, a = plan.place, plan.answers
    tz_zip = [f"{p.lat:.{PLACE_DECIMALS}f}, {p.lon:.{PLACE_DECIMALS}f} (rounded to about 1 km)", p.timezone]
    if plan.us:
        tz_zip.append(f"ZIP {p.zip}" if p.zip else "no ZIP found, so no pollen.com link (--zip adds one)")
    lines = [f"Place: {p.words} (found by {p.found_by})", "  Kept: " + " · ".join(tz_zip),
             f"  Name on the page: {p.name} (change it with --name)"
             + (f" · in a few sentences: {p.region} (--region)" if p.region else "")]
    if a.monitors == "both":
        lines.append(f'Monitors: indoor, called "{a.indoor}", and outdoor, called "{a.outdoor}"')
    else:
        lines.append(f'Monitors: {a.monitors} only, called "{a.indoor or a.outdoor}"')
    lines += plan.outdoor.lines
    prof = ", ".join(PROFILE_WORDS.get(k, k) for k in a.profiles) or "none"
    if "toddler" in a.profiles and a.indoor is None:
        prof += " (the toddler's stays greyed until an indoor monitor is added)"
    line = f"Profiles: {prof}"
    if a.indoor is not None:
        dry = " or ".join(APPLIANCE_WORDS[x] for x in a.appliances) if a.appliances else "nothing listed"
        line += f" · when it's too humid: {dry}"
    lines.append(line)
    if plan.seasons == "example":
        cal = "season calendar: the northeastern US's typical dates"
    elif plan.seasons == "given":
        cal = "season calendar: " + "; ".join(
            f"{s['name']} {day_words(s['start'])} – {day_words(s['end'])}"
            + (f", peak {day_words(s['peak'][0])} – {day_words(s['peak'][1])}" if s["peak_given"] else ", no peak given")
            for s in a.seasons) + " (typical dates, not a forecast)"
    else:
        cal = "season calendar left out (its dates are for the northeastern US; --season adds your region's)"
    pollen = {"later": "later", "now": "now", "off": "off"}[a.pollen]
    if a.pollen != "off" and keys.get("GOOGLE_POLLEN_API_KEY"):
        pollen = "on, the key is already in .env"
    lines.append(f"Pollen: {pollen} · {cal}" if a.pollen != "off" else f"Pollen: off · {cal}")
    if not plan.us:
        lines.append("Outside the US: wildfire smoke off (NOAA's map is for North America), no pollen.com link"
                     + ("" if plan.seasons == "given" else ", no season calendar"))
    lines.append("Token: already in .env" if keys.get("AIRGRADIENT_TOKEN") else f"Token: {a.token}")
    lines += [f"Note: {n}" for n in a.notes]
    return lines


# ---------- Next steps ----------

def run_prefix():
    """How to run the repo's Python here: uv when it's installed, else this Python (a virtualenv's)."""
    return "uv run --with-requirements requirements.txt" if shutil.which("uv") else shlex.quote(sys.executable)


def port_from(env):
    """The server's port: PORT when it is a number, else the default (server.py would not start on a bad one)."""
    try:
        port = int(env.get("PORT") or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


def port_free(port):
    # IPv4 only, on purpose: a server bound to ::1 alone would still show as free. Rare for Flask/gunicorn, so left as is.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def gcloud_status():
    """None without gcloud, else "signed in", "not signed in" or "installed" (it didn't say). No account is printed."""
    if not shutil.which("gcloud"):
        return None
    try:
        r = subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                           capture_output=True, text=True, timeout=GCLOUD_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return "installed"
    return "signed in" if r.stdout.strip() else "not signed in"


def macos_desktop():
    """The console belongs to the logged-in desktop user; a headless machine has no such user."""
    try:
        return Path("/dev/console").stat().st_uid == os.getuid()
    except OSError:
        return False


def open_page(url, env):
    """An optional agent action after starting the server. Always print the address, even without a desktop."""
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme in ("http", "https") and token_setup.LOCAL_HOST.fullmatch(parsed.netloc)
                 and parsed.path in ("", "/") and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        print("Use the local page's address, such as http://localhost:5555.")
        return 2
    print(f"Open {url}")
    if (any(key in env for key in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"))
            or token_setup.hosted(env) or token_setup.DOCKER_MARKER.exists()):
        return 0
    if sys.platform == "darwin" and macos_desktop():
        command = "open"
    elif sys.platform.startswith("linux") and (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        command = "xdg-open"
    else:
        return 0
    try:
        subprocess.run([command, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass  # the printed address still works when a desktop opener isn't installed
    return 0


def token_steps(root, run, url):
    return [f"  1. Open {url} on the computer running the app.",
            "  2. In the box, follow Open your AirGradient settings, turn API access on if it's off, then copy the token.",
            "  3. Paste your token in the box on the Home Air Quality page and press Save. Never paste it in the chat.",
            "     The page checks it, saves it on this computer and loads your monitors without a restart.",
            f"     For Terminal users and servers: cd {shlex.quote(str(root))} && {run} scripts/setup.py token; then restart."]


def next_steps(plan, keys, root, env):
    a, run = plan.answers, run_prefix()
    lines = ["", "Keep a private copy of config.toml (a password manager note, a private repo): it isn't in git, "
                 "so it has no history and no backup.", "", "Next:"]
    if a.pollen == "now" and not keys.get("GOOGLE_POLLEN_API_KEY"):
        g = gcloud_status()
        lines.append(f"- Pollen: SETUP.md step 5, with gcloud ({g})." if g else
                     "- Pollen: SETUP.md step 5, without gcloud (the Cloud console steps).")
    port = port_from(env)
    free = next((p for p in range(port, port + PORT_TRIES) if port_free(p)), None)
    prefix = "" if free == DEFAULT_PORT else f"PORT={free} "
    if free is None:
        lines.append(f"- Ports {port} to {port + PORT_TRIES - 1} are all in use: pick a free one with PORT=<port>.")
        free, prefix = port, f"PORT={port} "
    elif free != port:
        lines.append(f"- Port {port} is in use (another program, or a server already running), so use {free}.")
    url = f"http://localhost:{free}"
    lines += [f"- Start the page (SETUP.md step 6): cd {shlex.quote(str(root))} && {prefix}{run} server.py",
              f"  Then open {url}. To stop it: Ctrl+C in its terminal.",
              f"  The agent may open it on this computer: {run} scripts/setup.py --open {url}",
              f"- Check it's live: {run} scripts/setup.py --live" + ("" if free == DEFAULT_PORT else f" {url}")]
    if not keys.get("AIRGRADIENT_TOKEN") and a.token == "now":
        lines += ["- The AirGradient token (about 2 minutes). The user does it:"] + token_steps(root, run, url)
    later = []
    if not keys.get("AIRGRADIENT_TOKEN") and a.token == "later":
        later += ["- The AirGradient token: open the page and paste your token in the box when ready."] + token_steps(root, run, url)
    if a.pollen == "later" and not keys.get("GOOGLE_POLLEN_API_KEY"):
        later.append("- Pollen (optional): SETUP.md step 5. The pollen card says \"Off\" until the key is in .env.")
    if later:
        lines += ["", "Later, for the user (put it in the handover as a checklist):"] + later
    return lines


# ---------- The command ----------

def setup(args, env, root, get=None, fetch=None):
    answers = read_answers(args)
    place = resolve_place(args, get)
    plan = Plan(place, answers, pick_outdoor(answers, place, fetch), place.country == "US", plan_seasons(place, answers))
    if args.zip is not None and not plan.us:
        answers.notes.append("--zip ignored: the lookup didn't say this is a US place, and pollen.com covers the US only.")
    example = (root / "config.example.toml").read_text(encoding="utf-8")
    text = build_config(example, plan)
    try:
        load_config({"CONFIG_TOML": text}, root)
    except ConfigError as e:
        raise SetupError(f"The config it would write has a problem: {e}") from e
    keys = check_config.keys_present(env, root)
    for line in recap(plan, keys):
        print(line)
    path = root / "config.toml"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if args.check:
        print("")
        print("The settings it would write in config.toml (the file keeps config.example.toml's comments):")
        for line in text.splitlines():
            if line.strip() and not line.startswith("#"):
                print(f"  {line}")
        if old is not None and old != text:
            print("")
            print("config.toml is already there. Writing will need --replace, which saves the old file first. It would change:")
            print_diff(old, text)
        print("Nothing written (--check).")
        return 0
    print("")
    if old is not None and old == text:
        print("config.toml already has these settings: nothing to write.")
    elif old is not None and not args.replace:
        print("config.toml is already there, so nothing was written. This is what would change:")
        print_diff(old, text)
        print("To replace it, run the same command with --replace: it saves the old file next to it first.")
        return 1
    else:
        if old is not None:
            backup = backup_path(path)
            shutil.copy2(path, backup)   # the copy keeps the original's permissions
            print(f"Saved the old config.toml as {backup.name}, next to it.")
        path.write_text(text, encoding="utf-8")
        print("Wrote config.toml.")
    print("")
    code = check_config.main(["--file", str(path)], env, root)
    if code == 0:
        for line in next_steps(plan, keys, root, env):
            print(line)
    return code


def print_diff(old, new):
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), "config.toml (now)", "config.toml (new)",
                                     lineterm="", n=0):
        print(f"  {line}")


def backup_path(path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    candidate, n = path.with_name(f"{path.name}.bak-{stamp}"), 2
    while candidate.exists():
        candidate, n = path.with_name(f"{path.name}.bak-{stamp}-{n}"), n + 1
    return candidate


# ---------- setup.py token ----------

TOKEN_PROMPT = "Paste your AirGradient token (nothing shows while you paste), then press Enter: "


TOKEN_HINT = ("It needs a terminal to read the token without showing it. Open your own Terminal window, go to the repo "
              "folder and run: python scripts/setup.py token (not through the agent).")


def read_hidden(prompt, stdin):
    """getpass reads /dev/tty, so nothing shows. Only when there is no terminal does it fall back to the piped stdin
    (which nothing echoes). Warnings are turned into errors so getpass's own echoing fallback never runs."""
    if stdin is sys.stdin:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            pass
    return stdin.readline()


def save_token(root, stdin=None, read=None):
    stdin = stdin or sys.stdin
    if read is None:
        read = lambda prompt: read_hidden(prompt, stdin)
    try:
        token = (read(TOKEN_PROMPT) or "").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNothing saved.")
        print(TOKEN_HINT)
        return 1
    if not token:
        print("No token pasted: nothing saved. Run it again and paste the token.")
        print(TOKEN_HINT)
        return 1
    if any(c.isspace() for c in token) or not real_value(token):
        print("That doesn't look like a token (it has spaces, or it's the example's placeholder): nothing saved. "
              "Copy it again from AirGradient's dashboard.")
        return 1
    write_env_key(root / ".env", "AIRGRADIENT_TOKEN", token)
    print("Token saved in .env")
    return 0


# ---------- setup.py --live ----------

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
        print(f"The page doesn't answer at {base} ({type(e).__name__}). Start it (SETUP.md step 6), or pass its address: "
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
        print("Not live yet: open the local page and paste your token in the box, or use setup.py token and restart.")
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
                "(setup.py token saves a new one), then restart the server.")
        return
    if isinstance(data, dict) and data.get("state") == "no_token":
        problem("the page has no token yet. Open the local page and paste your token in the box.")
        return
    rows = [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
    expect = ([k for k, n in (("indoor", cfg.place.indoor), ("outdoor", cfg.place.outdoor)) if n is not None]
              if cfg else ["indoor", "outdoor"])
    for kind in expect:
        row = next((x for x in rows if x.get("locationType") == kind and "source" not in x), None)
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


# ---------- Arguments ----------

def parser():
    ap = argparse.ArgumentParser(
        prog="setup.py",
        description="Set up Home Air Quality for a home: one flag per question in SETUP.md. --check prints the recap "
                    "and writes nothing; without it, writes config.toml and checks it.",
        epilog="Also: 'setup.py token' (the user, in their own terminal: saves the AirGradient token in .env without "
               "showing it) and 'setup.py --live [URL]' (asks the running page whether it reads the monitors).")
    q = ap.add_argument_group("the answers (SETUP.md, How to ask)")
    q.add_argument("--address", help='1. the address, or a landmark or area near it ("Times Square, New York")')
    q.add_argument("--monitors", choices=("indoor", "outdoor", "both"), help="2. which monitors the home has")
    q.add_argument("--indoor-name", help='2. what to call the indoor monitor ("bedroom"; default: home)')
    q.add_argument("--outdoor-name", help='2. what to call the outdoor monitor ("balcony"; default: outside)')
    q.add_argument("--profiles", default="none", help=f"3. any of {','.join(PROFILES)}, or none (default)")
    q.add_argument("--dry", default="none", help=f"4. any of {','.join(APPLIANCES)}, or none (default)")
    q.add_argument("--outdoor-from", help="5. indoor only: suggest (default), a public monitor's id, area or model")
    q.add_argument("--token", default="now", help="6. the AirGradient token: now (default) or later")
    q.add_argument("--pollen", choices=("later", "now", "off"), default="later", help="7. pollen: later (default), now or off")
    q.add_argument("--season", action="append", metavar="SEASON",
                   help='a pollen season, repeatable: "Tree: Mar 10 – May 31, peak Apr 1 – May 10" (peak optional)')
    o = ap.add_argument_group("overrides, when the lookup is wrong or the user knows better")
    o.add_argument("--name", help="what the page calls the home")
    o.add_argument("--lat", type=float, help="latitude, with --lon (rounded to 2 decimals)")
    o.add_argument("--lon", type=float, help="longitude, with --lat")
    o.add_argument("--zip", help="US ZIP code, for the pollen.com link")
    o.add_argument("--region", help='the city or region in a few sentences ("the usual Denver season"); "" for none')
    o.add_argument("--timezone", help="an IANA name, like America/Chicago")
    r = ap.add_argument_group("running it")
    r.add_argument("--check", action="store_true", help="print the recap and the settings; write nothing")
    r.add_argument("--replace", action="store_true", help="replace an existing config.toml, saving it as config.toml.bak-<time> first")
    r.add_argument("--live", nargs="?", const="", metavar="URL",
                   help=f"check the running page (default http://localhost:$PORT, else {DEFAULT_PORT}); GET requests only")
    r.add_argument("--open", nargs="?", const="", metavar="URL",
                   help="open the local page on this desktop; skip over SSH, in containers or without a display")
    return ap


def main(argv, env, root=ROOT, stdin=None):
    if argv[:1] == ["token"]:
        if len(argv) > 1:
            print("Usage: setup.py token (it asks for the token; never pass it as an argument)")
            return 2
        return save_token(root, stdin)
    ap = parser()
    args = ap.parse_args(argv)
    if args.open is not None:
        return open_page(args.open or f"http://localhost:{port_from(env)}", env)
    if args.live is not None:
        return live(args.live or f"http://localhost:{port_from(env)}", env, root)
    if not args.monitors:
        ap.error("--monitors is needed: indoor, outdoor or both")
    if not args.address and args.lat is None:
        ap.error("--address is needed (or --lat and --lon)")
    try:
        return setup(args, env, root)
    except SetupError as e:
        print(e)
        return e.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
