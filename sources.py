"""Outside sources, their shared in-memory cache, and monitor history."""

import json
import logging
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import request
import requests

import publicmap
import summary as summary_rules
from config import Here, airgradient_map, env_key

# Config and the Flask app stay owned by server; startup passes its module as runtime.
# Functions read it at call time so use_config() never leaves a copied config behind.

# One shared pool for short-lived upstream calls (weather / smoke / pollen).
_UPSTREAM_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="upstream")

# ── Server-side cache ──
# One in-memory store for upstream data (AirGradient, Open-Meteo, Google Pollen, NOAA).
# - fresh (age < ttl): served as is
# - a little old (age < ttl + swr): served at once, refreshed in the background
# - older or missing: fetched; concurrent requests for the same key share one fetch
# - fetch fails: the last good value is served if it's younger than `keep`
# Fetch functions must raise on failure (so a bad answer is never stored) and must not call cached() themselves.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("aq.cache")
_REFRESH_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cache")   # background refreshes of stale cache entries
_cache, _inflight, _cache_lock = {}, {}, threading.Lock()

API_BASE = "https://api.airgradient.com/public/api/v1"   # AirGradient's public API: the monitors and the world map
# A stand-in for AirGradient's API (a test server with made-up monitors), for simulated setups; unset everywhere else
API_BASE = os.environ.get("AIRGRADIENT_API_BASE", "").rstrip("/") or API_BASE
NEARBY_RADIUS_KM = 15   # km: public monitors closer than this show as Nearby monitors (the source note says 15 km)
MAP_LINK_DECIMALS = 4   # a neighbor's link on AirGradient's map: its coordinates to about 10 m (the list gives 14 digits)
SECRET_ENV = ("AIRGRADIENT_TOKEN", "GOOGLE_POLLEN_API_KEY")   # keys that ride in request URLs, so in error text
# NOAA's Hazard Mapping System: the day's smoke polygons, one KML file per day
HMS_KML = "https://satepsanone.nesdis.noaa.gov/pub/FIRE/web/HMS/Smoke_Polygons/KML/{y}/{m}/hms_smoke{d}.kml"
SMOKE_RANK = {"Light": 1, "Medium": 2, "Heavy": 3}   # NOAA HMS densities, lightest first: a place gets its densest
# The local dev server (`flask run --reload`, which sets WERKZEUG_RUN_MAIN in the process that serves) restarts on every
# .py edit and would ask Google for the day's pollen again each time: with the Pollen API capped at 150 calls a day
# (SETUP.md), a day of edits could use them up. There it keeps the day's answer in a gitignored file. Production
# (gunicorn) never sets the variable and stores nothing.
DEV_CACHE_DIR = Path(__file__).parent / ".cache"
HIST_KEEP = ("timestamp", "pm02", "pm02_corrected", "rco2", "rco2_corrected", "rhum", "rhum_corrected")   # history fields the charts and rules read
# the History ranges (hours) and how long each is cached: (fresh, then served stale while refreshing), in seconds
HIST_TTL = {1: (60, 240), 6: (60, 240), 24: (60, 240), 168: (300, 1800)}
HIST_SLACK = timedelta(minutes=2)   # how far a History range's start may sit before its hours and still read as that range
# The world list's cache (s): fresh 2 min (as the neighborhood always was), then served stale up to 15 min while it
# refreshes, kept 1 h when AirGradient fails; a request waits up to 20 s for it (it's ~1.5 MB).
WORLD_CACHE = {"ttl": 120, "swr": 900, "keep": 3600, "wait": 20}
# ── An indoor-only home's outdoor PM2.5 ([sources] outdoor_from) ────────
# A public monitor's id (its reading and its history on AirGradient's map, like an own outdoor monitor), "area" (the
# public monitors around tune the model) or "model" (Open-Meteo's alone). Chosen once at setup; when the chosen monitor
# isn't reporting, the area stands in (fallback), and the model when the area can't. publicmap.py has the radii.
AREA_MAX_MONITORS = 5   # the nearest area monitors read: a median over 5 shrugs off one bad sensor, in few map requests
SOURCE_HOURS = 24   # h: the history a source is read over, the day calibrate_forecast compares the model with
# s: the most one request waits on the map in all for its source. Every monitor's map id is asked at once, then every
# history at once; past the budget, what isn't cached yet goes on in the background for the next request
SOURCE_BUDGET = 10
# a monitor's map id in the cache (s): it doesn't change, so a stale one is served while it refreshes, for a day more
MAP_ID_CACHE = {"ttl": publicmap.MAP_ID_TTL, "swr": publicmap.MAP_ID_TTL, "keep": publicmap.MAP_ID_TTL}
# a source's day of history for the summary and the area (s): fresh as publicmap.HISTORY_TTL, then served at once
# while it refreshes for up to 3 h (a day's ratio barely moves in that time), so a warm-ish cache never makes a
# request wait on the map; kept 3 h when the map fails
SOURCE_HIST_CACHE = {"ttl": publicmap.HISTORY_TTL, "swr": 3 * 3600, "keep": 3 * 3600}
# the History card's ranges of a public monitor (s): served stale for 30 min at most, as the chart shows the latest hour
CHART_HIST_CACHE = {"ttl": publicmap.HISTORY_TTL, "swr": 1800, "keep": 3 * 3600}
# what "AirGradient didn't answer" means: the request failed (network, HTTP status, bad JSON) or ran out of time
SOURCE_ERRORS = (requests.RequestException, RuntimeError, TimeoutError)
# the facts the page and the summary get about a source; the row and the history stay on the server
SOURCE_FACTS = ("kind", "id", "name", "street", "contributor", "url", "distance_km", "area_count", "fallback")
_SOURCE_SEEN = {}   # public monitor id → its last row in the world list, to name it once it drops out of the list


def _call_with_deadline(fn, *args, deadline_s=5, default=None, **kwargs):
    """Run fn with a hard wall-clock deadline.

    Needed because macOS getaddrinfo can hang well past requests' connect timeout
    (seen with pollen.googleapis.com DNS stalls ~30s).
    """
    fut = _UPSTREAM_POOL.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=deadline_s)
    except FuturesTimeout:
        fut.cancel()
        return default
    except Exception:
        return default


def _cache_run(key, fetch):
    t0 = time.time()
    try:
        value = fetch()
    except Exception as e:
        log.warning("upstream %s failed after %.2fs: %s", key, time.time() - t0, _redact(e)[:160])
        raise
    finally:
        with _cache_lock:
            _inflight.pop(key, None)
    with _cache_lock:
        _cache[key] = (time.time(), value)
        if len(_cache) > 200:   # drop entries untouched for 2 h (old summaries, past days' pollen)
            for k in [k for k, (at, _) in _cache.items() if time.time() - at > 7200]:
                _cache.pop(k, None)
    log.info("upstream %s ok %.2fs", key, time.time() - t0)
    return value


def _cache_start(key, fetch):
    with _cache_lock:
        fut = _inflight.get(key)
        if fut is None:
            fut = _inflight[key] = _REFRESH_POOL.submit(_cache_run, key, fetch)
        return fut


def cached(key, fetch, ttl, swr=0, keep=0, force=False, force_floor=15, wait=15):
    """Returns (value, info) with info = {"state": "hit"|"stale"|"miss"|"fallback", "age": seconds}."""
    with _cache_lock:
        entry = _cache.get(key)
    age = time.time() - entry[0] if entry else None
    if entry and not (force and age > force_floor):
        if age < ttl:
            return entry[1], {"state": "hit", "age": age}
        if age < ttl + swr:
            _cache_start(key, fetch)          # refresh in the background, answer now
            return entry[1], {"state": "stale", "age": age}
    try:
        value = _cache_start(key, fetch).result(timeout=wait)
        return value, {"state": "miss", "age": 0}
    except Exception:
        if entry and age < keep:
            return entry[1], {"state": "fallback", "age": age}
        raise


def _force():
    """The page's Refresh button sends X-Force-Refresh: 1."""
    # Each source has a floor (15 s, 10 min for Google Pollen) so repeats don't refetch.
    try:
        return request.headers.get("X-Force-Refresh") == "1"
    except RuntimeError:   # outside a request
        return False


def home_here():
    """The configured home as a Here (key "home": its cache keys stay the ones they always were)."""
    return Here("home", runtime.HOME_LAT, runtime.HOME_LON, runtime.CFG.place.timezone if runtime.CFG and runtime.CFG.place else None)


def _cache_key(base, here):
    """The home keeps its plain cache key; any other place adds its own."""
    return base if here.key == "home" else f"{base}:{here.key}"


def local_now(here=None):
    """The clock at home, or at another place. Railway runs in UTC, so a bare datetime.now() gives the wrong hour there."""
    tz = ZoneInfo(here.tz) if here is not None and here.tz else runtime.HOME_TZ
    return datetime.now(tz) if tz else datetime.now(timezone.utc)


def _redact(text):
    """Keys never leave the server: error text can carry the request URL (?token=..., ?key=...) or echo it.
    Used for every error the server logs or returns."""
    text = str(text)
    for k in [runtime.TOKEN] + [env_key(name) for name in SECRET_ENV]:
        if k:
            text = text.replace(k, "***")
    return text


class _TokenURLFilter(logging.Filter):
    """urllib3's optional debug output includes request URLs; strip query credentials before any handler sees it."""
    def filter(self, record):
        record.msg = re.sub(r"([?&](?:token|key)=)[^&\s\"']+", r"\1***", record.getMessage())
        record.args = ()
        return True


logging.getLogger("urllib3.connectionpool").addFilter(_TokenURLFilter())


def validate_token(token):
    """One uncached call, without changing the running credential or exposing upstream bodies/errors.
    None: AirGradient refused the token. A list (maybe empty): accepted, with the account's monitors as
    {"name": ..., "kind": "indoor" | "outdoor" | None}, for the page's "connected" card."""
    response = requests.get(f"{API_BASE}/locations/measures/current", params={"token": token}, timeout=10, allow_redirects=False)
    if response.status_code in (400, 401, 403):
        return None
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Unexpected AirGradient status")
    # An account with no monitors is still a valid account; malformed responses aren't credentials we can verify.
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected AirGradient response")
    return [{"name": publicmap.plain_text(row.get("locationName") or "") or "Unnamed monitor", "kind": monitor_kind(row)}
            for row in rows if isinstance(row, dict)]


def monitor_kind(row):
    """Indoor or outdoor, from the place's setting in AirGradient, else the model ("O-…" is an Open Air); None if neither says."""
    if row.get("locationType") in ("indoor", "outdoor"):
        return row["locationType"]
    model = str(row.get("model") or "")
    return "outdoor" if model.startswith(publicmap.OUTDOOR_PREFIX) else "indoor" if model.startswith("I-") else None


def api_get(path, params=None):
    p = {"token": runtime.TOKEN}
    if params:
        p.update(params)
    try:
        r = requests.get(f"{API_BASE}{path}", params=p, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        raise RuntimeError(_redact(f"AirGradient API returned {status}: {e.response.text[:300]}")) from None
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"AirGradient API unreachable ({type(e).__name__})") from None


def _fetch_weather(here):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": here.lat,
            "longitude": here.lon,
            "current": "temperature_2m,relative_humidity_2m,dew_point_2m,weather_code,wind_speed_10m,wind_direction_10m,visibility,uv_index,cloud_cover",
            "hourly": "wind_direction_10m,wind_speed_10m,precipitation_probability,precipitation,weather_code,temperature_2m,dew_point_2m,uv_index",
            "forecast_hours": 24,
            "past_hours": 4,   # the summary chart starts before now
            "daily": "sunrise,sunset",
            "forecast_days": 2,
            "timezone": here.tz
        },
        timeout=10
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("current"):
        raise RuntimeError("Open-Meteo answered without current weather")
    return data


def get_open_meteo_data(here=None):
    """Weather from Open-Meteo (free, no key) at a place (the home by default). Their current data moves on a 15-minute grid."""
    here = here or home_here()
    try:
        value, info = cached(_cache_key("wx", here), lambda: _fetch_weather(here), ttl=600, swr=3600, keep=3 * 3600, force=_force(), force_floor=300)
        return value
    except Exception:
        return no_weather()


def no_weather():
    """The weather's answer when Open-Meteo can't be reached: every reading None."""
    return {
        "current": {"wind_speed_10m": None, "wind_direction_10m": None, "visibility": None, "uv_index": None, "dew_point_2m": None},
        "hourly": {"wind_direction_10m": [], "wind_speed_10m": []}
    }


def _fetch_air_forecast(here):
    """Outdoor PM2.5 for the next 24 hours from Open-Meteo's air-quality model (CAMS, free, no key)."""
    r = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={"latitude": here.lat, "longitude": here.lon, "hourly": "pm2_5",
                "forecast_hours": 24, "past_hours": 24,   # the past day calibrates the forecast to the backyard monitor
                "timezone": here.tz},
        timeout=10
    )
    r.raise_for_status()
    hourly = r.json().get("hourly") or {}
    times, vals = hourly.get("time") or [], hourly.get("pm2_5") or []
    if not times:
        raise RuntimeError("Open-Meteo air quality answered without hours")
    return dict(zip(times, vals))


def get_air_forecast(here=None):
    """{"2026-11-07T18:00": pm2.5, ...}; empty when the model can't be reached. A model, so it can sit above or
    below the monitor: the page reacts to how it changes, not just its level."""
    here = here or home_here()
    try:
        value, _ = cached(_cache_key("aq", here), lambda: _fetch_air_forecast(here), ttl=1800, swr=3600, keep=6 * 3600, force=_force(), force_floor=300)
        return value
    except Exception:
        return {}


def _point_in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def smoke_status(here=None):
    """Whether NOAA HMS mapped wildfire smoke over a place (the home by default), from today's file (or yesterday's until today's is posted).

    Returns {"checked": bool, "detected": bool, "density": "Light"|"Medium"|"Heavy"|None, "date": "YYYY-MM-DD"|None}.
    The day's polygons are one file for all of North America, so they're cached once ("smoke") and each place is
    tested against them here, in the caller's thread.
    """
    here = here or home_here()
    try:
        value, _ = cached("smoke", _fetch_smoke, ttl=1800, swr=6 * 3600, keep=24 * 3600, force=_force(), force_floor=600)
        return smoke_at(value, here)
    except Exception:
        return no_smoke()


def no_smoke():
    """The smoke answer when NOAA wasn't checked."""
    return {"checked": False, "detected": False, "density": None, "date": None}


def _fetch_smoke():
    """Today's NOAA HMS file, or yesterday's until today's is posted, parsed: {"date", "polygons": [(density, ring)]}
    with each ring a list of (lon, lat). Raises when neither loads."""
    now = datetime.now(timezone.utc)
    for back in (0, 1):
        day = now - timedelta(days=back)
        url = HMS_KML.format(y=day.strftime("%Y"), m=day.strftime("%m"), d=day.strftime("%Y%m%d"))
        try:
            r = requests.get(url, timeout=12)
        except requests.exceptions.RequestException:
            continue
        if r.status_code != 200 or "<Placemark>" not in r.text:
            continue
        polygons = []
        for mark in re.findall(r"<Placemark>(.*?)</Placemark>", r.text, re.S):
            dens = re.search(r"Density:\s*(Light|Medium|Heavy)", mark)
            for coords in re.findall(r"<coordinates>(.*?)</coordinates>", mark, re.S):
                ring = []
                for triple in coords.split():
                    parts = triple.split(",")
                    if len(parts) >= 2:
                        ring.append((float(parts[0]), float(parts[1])))
                if len(ring) > 2:
                    polygons.append((dens.group(1) if dens else "Light", ring))
        return {"date": day.strftime("%Y-%m-%d"), "polygons": polygons}
    raise RuntimeError("No NOAA HMS smoke file for today or yesterday")


def smoke_at(hms, here):
    """The smoke answer at a place from the day's parsed polygons (_fetch_smoke): the densest one over it."""
    best = None
    for dens, ring in hms["polygons"]:
        if (best is None or SMOKE_RANK[dens] > SMOKE_RANK[best]) and _point_in_ring(here.lon, here.lat, ring):
            best = dens
    return {"checked": True, "detected": best is not None, "density": best, "date": hms["date"]}


def get_smoke_data():
    """True when NOAA HMS mapped smoke over home. False when clear or not checked."""
    return smoke_status()["detected"]


def _fetch_pollen_raw(lat, lon, api_key):
    r = requests.get(
        "https://pollen.googleapis.com/v1/forecast:lookup",
        params={
            "key": api_key,
            "location.latitude": lat,
            "location.longitude": lon,
            "days": 2   # today, plus tomorrow for Coming up
        },
        timeout=(2, 5),
    )
    r.raise_for_status()
    return r.json()


def _pollen_types(day):
    out = []
    for ptype in (day or {}).get("pollenTypeInfo", []):
        index_info = ptype.get("indexInfo", {})
        out.append({
            "name": ptype.get("displayName", "Unknown"),
            "level": index_info.get("category", "None"),
            "index": index_info.get("value", 0),
            "in_season": ptype.get("inSeason", False),
        })
    return out


def _fetch_pollen():
    """Today's and tomorrow's pollen, one call: {"today": [...], "tomorrow": [...]}."""
    api_key = env_key("GOOGLE_POLLEN_API_KEY")
    if not api_key:
        return {"today": [], "tomorrow": []}
    # Hard deadline: DNS stalls on pollen.googleapis.com have been observed at ~30s
    # even with requests timeout set — that blocked the whole /api/context response.
    data = _call_with_deadline(_fetch_pollen_raw, runtime.HOME_LAT, runtime.HOME_LON, api_key, deadline_s=5, default=None)
    daily = (data or {}).get("dailyInfo") or []
    if not daily:
        raise RuntimeError("Google Pollen did not answer")
    return {"today": _pollen_types(daily[0]), "tomorrow": _pollen_types(daily[1]) if len(daily) > 1 else []}


def _dev_server():
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def _fetch_pollen_kept():
    """_fetch_pollen, kept on disk for the day on the local dev server only."""
    if not _dev_server():
        return _fetch_pollen()
    f = DEV_CACHE_DIR / f"pollen-{local_now():%Y-%m-%d}-{runtime.HOME_LAT:.2f}-{runtime.HOME_LON:.2f}.json"   # the day's, like the cache
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        pass
    value = _fetch_pollen()
    try:
        DEV_CACHE_DIR.mkdir(exist_ok=True)
        f.write_text(json.dumps(value))
    except OSError:
        pass
    return value


def get_pollen_days():
    """{"today": [...], "tomorrow": [...]} from Google, kept for the rest of the home's day: it's a daily forecast, so one
    call a day per running server (plus restarts and the Refresh button), in every season. A new day is a new key."""
    try:
        # the key is the day's, so an answer never outlives its day: a day's ttl keeps it until the key changes
        value, _ = cached("pollen:" + local_now().strftime("%Y-%m-%d"), _fetch_pollen_kept, ttl=24 * 3600,
                          keep=24 * 3600, force=_force(), force_floor=600, wait=7)
        return value if isinstance(value, dict) else {"today": value or [], "tomorrow": []}
    except Exception:
        return {"today": [], "tomorrow": []}


def get_pollen_data(lat=None, lon=None):
    """Today's pollen from Google: [{name, level, index, in_season}, ...]."""
    return get_pollen_days()["today"]


# ── Sources that are off or not set up ──────────────────────────────────
# "off": turned off in the config (or no road). "not_set_up": on, but its key is missing. "ok", or "error" when it
# is on and set up and didn't answer. A source that is off or not set up is never fetched.

def source_on(name):
    return runtime.CFG.sources.get(name, True) if runtime.CFG else True


def pollen_state():
    if not source_on("pollen"):
        return "off"
    return "ok" if env_key("GOOGLE_POLLEN_API_KEY") else "not_set_up"


def pollen_live():
    return pollen_state() == "ok"


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def place_rows(rows):
    """A home with one monitor gets only that monitor's rows: the token may see others (a second monitor, an old one),
    and an indoor-only home's outdoor PM2.5 is its source. Explicit ids choose among account monitors.
    The demo and no config: as they came.
    A copy: the cache keeps its list."""
    if not isinstance(rows, list) or runtime.CFG is None or runtime.CFG.demo or runtime.CFG.place is None:
        return rows
    place = runtime.CFG.place
    selected = {kind: getattr(place, kind + "_id") for kind in ("indoor", "outdoor") if getattr(place, kind) is not None}
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        kind = next((k for k, mid in selected.items() if mid is not None and mid == row.get("locationId")), row.get("locationType"))
        if kind in ("indoor", "outdoor"):
            if kind not in selected or (selected[kind] is not None and selected[kind] != row.get("locationId")):
                continue
            row = {**row, "locationType": kind}
        out.append(row)
    return out


def _iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def history_rows(location_id, hours, force=False):
    """The last `hours` of readings for one monitor, trimmed to the fields the page and the summary use."""
    def fetch():
        now = datetime.now(timezone.utc)
        rows = api_get(f"/locations/{int(location_id)}/measures/past", {
            "from": (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ"), "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
        return [{k: r.get(k) for k in HIST_KEEP if r.get(k) is not None} for r in rows or [] if isinstance(r, dict)]
    ttl, swr = HIST_TTL.get(hours, (60, 240))
    return cached(f"ag:hist:{int(location_id)}:{hours}h", fetch, ttl=ttl, swr=swr, keep=3600, force=force)


def _fetch_world():
    """Every public AirGradient monitor in the world, as the API lists them. Cached by the caller, in the request
    thread: a fetch that cached() runs in the pool must never call cached() itself (it would wait on its own pool)."""
    return publicmap.fetch_world()


def _fetch_nearby(world, here=None):
    """The monitors of the world list within NEARBY_RADIUS_KM of a place (the home by default), nearest first.
    A plain filter: no cache, no network. Each gets its distance, its link on AirGradient's map and, when it has the
    humidity to correct with, pm02_corrected: the world list gives the raw pm02, and the page compares neighbors with
    a home's own monitors on the corrected basis (summary.corrected_pm). The raw pm02 stays as it came."""
    here = here or home_here()
    nearby = []
    for loc in world:
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat and lon:
            d = haversine_km(here.lat, here.lon, lat, lon)
            if d < NEARBY_RADIUS_KM:
                pm = summary_rules.corrected_pm(loc.get("pm02"), loc.get("rhum"))
                link = airgradient_map(round(lat, MAP_LINK_DECIMALS), round(lon, MAP_LINK_DECIMALS))
                nearby.append({**loc, "distance_km": round(d, 1), "map_url": link,   # a copy: the cached list stays as it came
                               **({"pm02_corrected": pm} if pm is not None else {})})
    nearby.sort(key=lambda x: x["distance_km"])
    return nearby


def outdoor_from():
    """The configured outdoor source of an indoor-only home (a public monitor's id, "area" or "model"), or None: a home
    with an outdoor monitor, no config, or the demo (its own seams)."""
    if runtime.CFG is None or runtime.CFG.demo or runtime.CFG.place is None or runtime.CFG.place.outdoor is not None:
        return None
    return runtime.CFG.outdoor_from


def _world_list():
    """The world list ("ag:world", fetched in the request thread), or None when AirGradient doesn't answer."""
    try:
        world, _ = cached("ag:world", _fetch_world, force=_force(), **WORLD_CACHE)
        return world
    except SOURCE_ERRORS:
        return None


def _map_start(key, fetch, **kw):
    """Starts a map fetch through the cache without waiting on it (a value already cached is left as it is)."""
    try:
        cached(key, fetch, wait=0, **kw)
    except SOURCE_ERRORS:   # still running (TimeoutError), or already failed: the wait below answers either way
        pass


def _map_wait(key, fetch, deadline, **kw):
    """The value a _map_start began, waiting no longer than what's left before `deadline` (time.monotonic()), or None
    when the map didn't answer in time (the fetch goes on in the background for the next request)."""
    try:
        value, _ = cached(key, fetch, wait=max(0.0, min(publicmap.MAP_WAIT, deadline - time.monotonic())), **kw)
        return value
    except SOURCE_ERRORS:
        return None


def source_histories(mons, hours, deadline, measures=publicmap.MAP_MEASURES, cache=SOURCE_HIST_CACHE):
    """Each public monitor's last `hours` on AirGradient's map as /api/history rows, oldest first; [] for one the map
    has no entry for or that didn't answer in time. Through the cache, in the request thread, under keys that carry
    each monitor's id (and the measures, when not all of them): every map id is asked at once, then every history at
    once, and the waits share one deadline, so five monitors take about as long as one."""
    tag = "" if measures is publicmap.MAP_MEASURES else ":" + ",".join(measures)
    id_jobs = [(f"src:mapid:{m['locationId']}", lambda m=m: publicmap.map_id(m)) for m in mons]
    for key, fetch in id_jobs:
        _map_start(key, fetch, **MAP_ID_CACHE)
    hist_jobs = []
    for m, (key, fetch) in zip(mons, id_jobs):
        mid = _map_wait(key, fetch, deadline, **MAP_ID_CACHE)
        hist_jobs.append(None if mid is None else (f"src:maphist:{m['locationId']}:{hours}h{tag}",
                                                   lambda mid=mid: publicmap.history(mid, hours, measures=measures)))
    for job in filter(None, hist_jobs):
        _map_start(*job, **cache)
    return [[dict(r) for r in (_map_wait(*job, deadline, **cache) or [])] if job else [] for job in hist_jobs]


def source_history(mon, hours, deadline, measures=publicmap.MAP_MEASURES, cache=SOURCE_HIST_CACHE):
    """One public monitor's source_histories."""
    return source_histories([mon], hours, deadline, measures, cache)[0]


def _row_points(rows, now):
    """/api/history rows as (local time, row), oldest first, like history_points."""
    points = []
    for row in rows:
        try:
            ts = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00")).astimezone(now.tzinfo)
        except (KeyError, ValueError, TypeError):
            continue
        points.append((ts, row))
    return sorted(points, key=lambda p: p[0])


def model_hours(now):
    """The air-quality model's outdoor PM2.5 as (local time, value), oldest first."""
    return sorted((_local(t, now.tzinfo), v) for t, v in (get_air_forecast() or {}).items())


def _source(kind, **facts):
    return {"kind": kind, "id": None, "name": None, "street": None, "contributor": None, "url": None,
            "distance_km": None, "row": None, "history": [], "area_count": 0, "area_factor": None, "fallback": False,
            **facts}


def _monitor_facts(mon):
    """A public monitor's facts for the page: who and where (its owner's credit), and how far from home."""
    return {"id": mon.get("locationId"), "name": publicmap.name_of(mon), "street": mon.get("publicPlaceName"),
            "contributor": mon.get("publicContributorName"), "url": mon.get("publicPlaceUrl"),
            "distance_km": round(publicmap.km_between(runtime.HOME_LAT, runtime.HOME_LON, mon["latitude"], mon["longitude"]), 1)}


def _area_source(world, now, deadline):
    """The area estimate: the nearest AREA_MAX_MONITORS reporting outdoor monitors within AREA_KM, each one's hourly
    PM2.5 over the last day, their median per hour, and its median ratio to the model (calibrate_forecast's factor:
    the median of a per-hour median ratio is the ratio of the per-hour median, as the ratio is linear in the value).
    The model instead with fewer than AREA_MIN_MONITORS with history, or too few hours to compare."""
    near = [m for _, m in publicmap.within(world, runtime.HOME_LAT, runtime.HOME_LON, publicmap.AREA_KM, now)][:AREA_MAX_MONITORS]
    series = []
    for rows in source_histories(near, SOURCE_HOURS, deadline, measures=publicmap.PM_ONLY):
        hourly = {}
        for t, row in _row_points(rows, now):
            v = fnum(row.get("pm02_corrected"))
            if v is not None and now - timedelta(hours=SOURCE_HOURS) <= t <= now:
                hourly.setdefault(t.replace(minute=0, second=0, microsecond=0), []).append(v)
        if hourly:
            series.append({h: sum(vs) / len(vs) for h, vs in hourly.items()})
    if len(series) < publicmap.AREA_MIN_MONITORS:
        return _source("model")
    area = []
    for h in sorted({h for s in series for h in s}):
        vals = sorted(s[h] for s in series if h in s)
        mid = len(vals) // 2
        area.append((h, round(vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2, 1)))
    _, k = summary_rules.calibrate_forecast(model_hours(now), area, now)
    if k is None:
        return _source("model")
    return _source("area", area_count=len(series), area_factor=k,
                   history=[{"timestamp": h.isoformat(), "pm02_corrected": v} for h, v in area])


def outdoor_source(now=None, with_history=True):
    """Where an indoor-only home's outdoor PM2.5 comes from now, or None for a home with an outdoor monitor:
    {"kind": "monitor"|"area"|"model", "id", "name", "street", "contributor", "url", "distance_km" (the chosen public
    monitor's, kept when it falls back), "row" (its reading, with pm02_corrected; kind monitor only), "history" (its
    /api/history rows over SOURCE_HOURS, or the area's hourly medians), "area_count" (area monitors used),
    "area_factor" (the area's ratio to the model), "fallback" (why the chosen monitor's reading isn't used: "monitor",
    it isn't reporting; "list", AirGradient's world list didn't answer, so whether it reports is unknown; else False)}.
    with_history=False skips a public monitor's own history (/api/current shows only its reading); the area still reads
    its monitors', as they decide whether it is "area" or "model".
    Facts only: the page and phrases.py word them. Never raises for an upstream: monitor → area → model."""
    of = outdoor_from()
    if of is None:
        return None
    if of == "model":
        return _source("model")
    now = now or local_now()
    world = _world_list()
    deadline = time.monotonic() + SOURCE_BUDGET
    about, fallback = {}, False
    if isinstance(of, int):
        mon = publicmap.find(world, of)
        if mon is not None:
            _SOURCE_SEEN[of] = mon
        known = mon or _SOURCE_SEEN.get(of)
        about = _monitor_facts(known) if known else {"id": of}
        if mon is not None and outdoor_current(mon, now):
            return _source("monitor", **about, row=publicmap.reading_row(mon),
                           history=source_history(mon, SOURCE_HOURS, deadline) if with_history else [])
        fallback = "list" if world is None else "monitor"
    src = _area_source(world, now, deadline) if world is not None else _source("model")
    return {**src, **about, "fallback": fallback}


def source_facts(src):
    """What the page and the read get about a source: SOURCE_FACTS, without its row and history."""
    return {k: src[k] for k in SOURCE_FACTS}


def source_monitor(src):
    """The source as /api/current's outdoor monitor: a public monitor's reading row, or (area, model) an outdoor entry
    without readings, so the page knows what to draw. Each says where it comes from ("source")."""
    if src["kind"] == "monitor":
        return {**src["row"], "source": source_facts(src)}
    return {"locationType": "outdoor", "source": source_facts(src)}


def source_history_rows(location_id, frm, to):
    """The chosen public monitor's rows between frm and to (UTC datetimes) from AirGradient's map, for /api/history:
    from the shortest History range (HIST_TTL's hours) that reaches back to frm, the longest at most. [] when it isn't
    in the world list (nor seen since start) or the map doesn't answer."""
    mon = publicmap.find(_world_list(), location_id) or _SOURCE_SEEN.get(location_id)
    if mon is None:
        return []
    ranges = sorted(HIST_TTL)
    back = (datetime.now(timezone.utc) - frm - HIST_SLACK).total_seconds() / 3600
    hours = next((h for h in ranges if h >= back), ranges[-1])
    rows = source_history(mon, hours, time.monotonic() + SOURCE_BUDGET, cache=CHART_HIST_CACHE)
    out = []
    for r in rows:
        try:
            t = _iso(str(r["timestamp"]))
        except (KeyError, ValueError):
            continue
        if frm <= t <= to:
            out.append(r)
    return out


def fnum(value):
    """Float or None. Zero is a real reading."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def history_points(location_id, now_local, hours=24):
    if not location_id:
        return []
    try:
        rows, _ = history_rows(location_id, hours)
    except (RuntimeError, ValueError, TypeError):
        return []
    points = []
    for row in rows or []:
        try:
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).astimezone(now_local.tzinfo)
        except (KeyError, ValueError, AttributeError, TypeError):
            continue
        points.append((ts, row))
    points.sort(key=lambda p: p[0])
    return points


def pm_of(r):
    return fnum(r.get("pm02_corrected", r.get("pm02")))


def _local(ts, tz):
    """'2026-11-08T16:00' (Open-Meteo, local) as an aware datetime."""
    return datetime.fromisoformat(ts).replace(tzinfo=tz)


def outdoor_current(row, now):
    """Whether the outdoor reading counts as a reading now: no row to judge by, or online and under
    publicmap.STALE_READING old."""
    return row is None or publicmap.reporting(row, now)   # the same rule as check_config.py's
