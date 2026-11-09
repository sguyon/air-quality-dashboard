"""Home Air Quality: the server. It serves the page and fetches the readings and the local conditions it shows."""

import base64
import hashlib
import json
import math
import os
import subprocess
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, g, jsonify, request, send_file
import requests

import phrases
import summary as summary_rules
from config import (APPLIANCES, DEFAULT_LIMITS, ConfigError, Here, airgradient_map, bearing_in, env_key, load_config, public_view,
                    real_value, route_path)

# One shared pool for short-lived upstream calls (weather / smoke / pollen).
_UPSTREAM_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="upstream")


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

# ── Server-side cache ──
# One in-memory store for upstream data (AirGradient, Open-Meteo, Google Pollen, NOAA).
# - fresh (age < ttl): served as is
# - a little old (age < ttl + swr): served at once, refreshed in the background
# - older or missing: fetched; concurrent requests for the same key share one fetch
# - fetch fails: the last good value is served if it's younger than `keep`
# Fetch functions must raise on failure (so a bad answer is never stored) and must not call cached() themselves.
import logging
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("aq.cache")
_REFRESH_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cache")   # background refreshes of stale cache entries
_CONTEXT_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="context")   # /api/context fan-out; separate from the pollen deadline pool
_cache, _inflight, _cache_lock = {}, {}, threading.Lock()


def _cache_run(key, fetch):
    t0 = time.time()
    try:
        value = fetch()
    except Exception as e:
        log.warning("upstream %s failed after %.2fs: %s", key, time.time() - t0, str(e)[:160])
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


def _note_cache(info):
    try:
        g.cache_state, g.cache_age = info["state"], int(info["age"])
    except RuntimeError:
        pass


def parse_dotenv(text):
    """KEY=value lines from a .env file. One pair of matching quotes around a value is dropped
    (AIRGRADIENT_TOKEN="abc" is abc); the first line for a key wins, like the environment over the file."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            key, val = key.strip().removeprefix("export ").strip(), val.strip()
            if not key or key == "export":   # "=x" or "export =x": no name to set
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            out.setdefault(key, val)
    return out


# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for key, val in parse_dotenv(env_path.read_text()).items():
        os.environ.setdefault(key, val)

app = Flask(__name__)

API_BASE = "https://api.airgradient.com/public/api/v1"   # AirGradient's public API: the monitors and the world map
TOKEN = env_key("AIRGRADIENT_TOKEN")   # .env.example's placeholder counts as no token
NEARBY_RADIUS_KM = 15   # km: public monitors closer than this show as Nearby monitors (the source note says 15 km)
MAP_LINK_DECIMALS = 4   # a neighbor's link on AirGradient's map: its coordinates to about 10 m (the list gives 14 digits)


def use_config(cfg):
    """Point the server at a config (config.py): the home, its clock, the road and the limits. Runs once at import;
    tests run it again with another config. With None (no config) there is no home: Task 10 decides what happens then.
    The config rounds the home to ~1 km on purpose (public repo): weather, pollen, smoke and the 15 km radius don't
    need more. tzdata (requirements.txt) gives every host the timezone database."""
    global CFG, APP_VIEW, HOME_LAT, HOME_LON, HOME_TZ, ROAD, RUSH_WINDOWS, LIMITS, PM_FINE, PM_HIGH, CO2_OPEN, RH_LOW, RH_DAMP
    CFG = cfg
    APP_VIEW = public_view(cfg) if cfg else {}   # what the page gets as window.APP
    place = cfg.place if cfg else None
    HOME_LAT, HOME_LON = (place.lat, place.lon) if place else (None, None)
    HOME_TZ = ZoneInfo(place.timezone) if place else None
    ROAD = cfg.road if cfg else None
    RUSH_WINDOWS = list(ROAD.rush) if ROAD else []   # [start, end) hours, and the rush's name
    # the TOML reads every limit as a float; whole numbers stay whole so the page says "800", not "800.0"
    LIMITS = {k: int(v) if float(v).is_integer() else v for k, v in (cfg.limits if cfg else DEFAULT_LIMITS).items()}
    PM_FINE, PM_HIGH, CO2_OPEN = LIMITS["pm"], LIMITS["pm_high"], LIMITS["co2"]
    RH_LOW, RH_DAMP = LIMITS["rh_dry"], LIMITS["rh_damp"]
    summary_rules.LIMITS.update(LIMITS)
    summary_rules.APPLIANCES.clear()
    summary_rules.APPLIANCES.update(cfg.appliances if cfg else APPLIANCES)
    phrases.LIMIT_FACTS.update(co2_limit=LIMITS["co2"], rh_damp=LIMITS["rh_damp"], rh_dry=LIMITS["rh_dry"],
                               rh_stop=LIMITS["rh_stop"], pm_limit=LIMITS["pm"], pm_high=LIMITS["pm_high"],
                               **({"indoor": place.indoor, "outdoor": place.outdoor} if place else {}))


def startup_config(env=os.environ, root=None):
    """The config to run with: DEMO=1, CONFIG_TOML, CONFIG_FILE or config.toml (config.load_config). With none of them and no
    AIRGRADIENT_TOKEN either (a fresh copy), the demo's."""
    kw = {} if root is None else {"root": root}
    cfg = load_config(env, **kw)
    if cfg is None and not real_value(env.get("AIRGRADIENT_TOKEN")):
        cfg = load_config({"DEMO": "1"}, **kw)
    return cfg


# what the server prints when it stops for want of a config (a token but no home: it won't guess one)
NO_CONFIG_MESSAGE = "No config: copy config.example.toml to config.toml (or set CONFIG_TOML)"


APP_LOAD_ERROR = 4   # gunicorn's exit code for "the app can't load": the master stops instead of respawning forever


def _stop(message):
    print(message, file=sys.stderr, flush=True)
    sys.exit(APP_LOAD_ERROR)


def boot_config(env=os.environ, root=None):
    """startup_config for the server's start: stops with a plain message instead of a traceback when the config is
    invalid (the ConfigError's text names where) or when there is a token but no config (it won't guess a home)."""
    try:
        cfg = startup_config(env, root)
    except ConfigError as e:
        _stop(str(e))
    if cfg is None:
        _stop(NO_CONFIG_MESSAGE)
    return cfg


def server_mode(cfg, token):
    """"demo" (made-up data, demo/), "live" (a config and a token) or "no_token" (a config, no token yet)."""
    if cfg is not None and cfg.demo:
        return "demo"
    return "live" if real_value(token) else "no_token"


use_config(boot_config())
MODE = server_mode(CFG, TOKEN)   # "demo", "live" or "no_token", fixed at start


def home_here():
    """The configured home as a Here (key "home": its cache keys stay the ones they always were)."""
    return Here("home", HOME_LAT, HOME_LON, CFG.place.timezone if CFG and CFG.place else None)


def _cache_key(base, here):
    """The home keeps its plain cache key; any other place adds its own."""
    return base if here.key == "home" else f"{base}:{here.key}"


def local_now(here=None):
    """The clock at home, or at another place. Railway runs in UTC, so a bare datetime.now() gives the wrong hour there."""
    tz = ZoneInfo(here.tz) if here is not None and here.tz else HOME_TZ
    return datetime.now(tz) if tz else datetime.now(timezone.utc)


def get_build_info():
    """The commit and the time of this page, in the home's timezone. The commit comes from the host's deploy
    variables when it sets them (Railway, Vercel), or from the Docker image's (GIT_COMMIT_SHA, the GIT_SHA build arg),
    else from git."""
    commit = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("VERCEL_GIT_COMMIT_SHA")
              or os.environ.get("GIT_COMMIT_SHA") or "").strip()[:7]
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).parent, stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
        except Exception:
            commit = "no-git"
    return f"v2 · {commit} · {local_now().strftime('%H:%M:%S %Z')}"


def _redact(text):
    """The token never leaves the server: AirGradient error text can carry the request URL (?token=...) or echo it."""
    return str(text).replace(TOKEN, "***") if TOKEN else str(text)


def api_get(path, params=None):
    p = {"token": TOKEN}
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


# NOAA's Hazard Mapping System: the day's smoke polygons, one KML file per day
HMS_KML = "https://satepsanone.nesdis.noaa.gov/pub/FIRE/web/HMS/Smoke_Polygons/KML/{y}/{m}/hms_smoke{d}.kml"


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


SMOKE_RANK = {"Light": 1, "Medium": 2, "Heavy": 3}   # NOAA HMS densities, lightest first: a place gets its densest


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
    data = _call_with_deadline(_fetch_pollen_raw, HOME_LAT, HOME_LON, api_key, deadline_s=5, default=None)
    daily = (data or {}).get("dailyInfo") or []
    if not daily:
        raise RuntimeError("Google Pollen did not answer")
    return {"today": _pollen_types(daily[0]), "tomorrow": _pollen_types(daily[1]) if len(daily) > 1 else []}


def get_pollen_days():
    """{"today": [...], "tomorrow": [...]} from Google (a daily forecast), cached per local day."""
    try:
        value, _ = cached("pollen:" + local_now().strftime("%Y-%m-%d"), _fetch_pollen, ttl=3 * 3600, swr=12 * 3600,
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
    return CFG.sources.get(name, True) if CFG else True


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


def asset_version(rel_path):
    """Short content hash of a file in static/, so a changed file gets a new URL and no cache serves the old one."""
    path = Path(__file__).parent / rel_path.lstrip("/")
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()[:10]
    except OSError:
        return "0"


def version_assets(html):
    """Add ?v=<hash> to the page's CSS, JS, icons and manifest, so a changed file gets a new URL. Safari keeps
    home-screen icons per URL, so a new icon needs a new URL to show."""
    return re.sub(r'"(/static/[\w./-]+\.(?:css|js|png|svg)|/manifest\.json)"', lambda m: f'"{m.group(1)}?v={asset_version(m.group(1))}"', html)


@app.after_request
def api_headers(resp):
    """No browser HTTP caching of live data (the server cache does that); say how fresh the answer is."""
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
        if getattr(g, "cache_state", None):
            resp.headers["X-Cache"] = g.cache_state
            resp.headers["X-Data-Age"] = str(g.cache_age)
    if MODE == "demo" and request.method == "GET" and resp.status_code == 200 and (request.path == "/" or request.path.startswith("/api/")):
        if request_monitor() is not None or request.path == "/api/monitors":
            # a public monitor is live: a CDN keeps it as long as its data stays fresh in the cache (demo/public.py)
            resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
        else:
            # the demo's story is fixed: a CDN keeps each URL (each ?moment=) for a day, so a busy day barely runs the server
            resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400"
    if MODE == "demo" and monitor_missing():
        # a public monitor that can't be shown (unknown id, or the map didn't answer): no one keeps this answer
        resp.headers["Cache-Control"] = "no-store"
    # only the demo is for search engines; someone's home is not, nor a public monitor's page or the picker's list
    # (they carry the owners' names)
    if not (CFG is not None and CFG.demo) or "monitor" in request.args or request.path == "/api/monitors":
        resp.headers["X-Robots-Tag"] = "noindex"
    return resp


def icon_env():
    """"dev" or "preview" or None (a normal deployment). A local address is always "dev"; anywhere else the
    deployment names itself with APP_ENV, never by its address."""
    host = (request.host or "").split(":")[0].lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0") or host.startswith(("127.", "10.", "192.168.")) or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host):
        return "dev"
    env = os.environ.get("APP_ENV", "").strip().lower()
    return env if env in ENV_LABEL else None


ENV_LABEL = {"dev": "DEV", "preview": "PREVIEW"}   # the tag on the page title and app name on dev and preview


def tag_env(html):
    """DEV / PREVIEW icons, tab title and home-screen name, so the environments can't be mixed up."""
    env = icon_env()
    if not env:
        return html
    html = re.sub(r'(<link rel="(?:icon|apple-touch-icon)"[^>]*href=")/static/icons/', rf'\1/static/icons/{env}/', html)
    html = html.replace("<title>Home Air Quality</title>", f"<title>{ENV_LABEL[env]} · Home Air Quality</title>", 1)
    html = html.replace('<meta name="apple-mobile-web-app-title" content="Air Quality">', f'<meta name="apple-mobile-web-app-title" content="AQ {ENV_LABEL[env]}">', 1)
    return html


def inline_touch_icon(html):
    """Put the 180 px home-screen icon in the page itself. Safari's Add to Home Screen sheet loads icons on its own
    and can fail on a network URL, which leaves a letter tile."""
    m = re.search(r'(<link rel="apple-touch-icon"[^>]*href=")(/static/icons/[\w./-]+\.png)(?:\?v=\w+)?"', html)
    if not m:
        return html
    try:
        data = base64.b64encode((Path(__file__).parent / m.group(2).lstrip("/")).read_bytes()).decode()
    except OSError:
        return html
    return html[:m.start()] + f'{m.group(1)}data:image/png;base64,{data}"' + html[m.end():]


@app.route("/")
def index():
    html_path = Path(__file__).parent / "index.html"
    html = inline_touch_icon(tag_env(version_assets(html_path.read_text())))
    html = inject_app(html)

    # Inject build info into a data attribute on the body
    build_info = get_build_info()
    html = html.replace(
        '<body>',
        f'<body data-build="{build_info}">'
    )

    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def page_view():
    """window.APP's config part: the home's (config.public_view). demo/data.py gives a public monitor's instead."""
    return APP_VIEW


def page_clock():
    """The demo's fixed clock for the page (window.APP.now: the moment's time, its key, the moments to switch to),
    or None: a real home runs on the real clock. demo/data.py replaces it."""
    return None


def inject_app(html):
    """The home's config for the page's scripts (config.public_view), as window.APP before the first of them.
    Every "<" is escaped (\\u003c, still the same JSON) so no config value can close the script or open a comment."""
    now = page_clock()
    data = json.dumps({**page_view(), "env": icon_env(), **({"now": now} if now else {}), **({"state": "no_token"} if MODE == "no_token" else {})}, ensure_ascii=False).replace("<", "\\u003c")
    return html.replace("<script src=", f"<script>window.APP = {data};</script>\n<script src=", 1)


@app.route("/api/road/route")
def road_route():
    """The road's route ([lon, lat] points) for the map. 404 without a road."""
    if not ROAD:
        return jsonify({"error": "no road"}), 404
    try:
        return jsonify(json.loads(route_path(ROAD.route).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return jsonify({"error": "road route unreadable"}), 404


@app.route("/manifest.json")
def manifest():
    path = Path(__file__).parent / "manifest.json"
    env = icon_env()
    data = json.loads(path.read_text())
    if env:   # the installed app gets the DEV / PREVIEW icons and name too
        data["name"] = f'{data.get("name", "Home Air Quality")} ({ENV_LABEL[env]})'
        data["short_name"] = f"AQ {ENV_LABEL[env]}"
    for ic in data.get("icons", []):
        src = str(ic.get("src", ""))
        if src.startswith("/static/icons/"):
            ic["src"] = (src.replace("/static/icons/", f"/static/icons/{env}/", 1) if env else src) + f"?v={asset_version(src)}"
    resp = jsonify(data)
    resp.headers["Content-Type"] = "application/manifest+json"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
@app.route("/apple-touch-icon-180x180.png")
@app.route("/apple-touch-icon-180x180-precomposed.png")
@app.route("/favicon.ico")
def root_icon():
    """The icons iOS and browsers ask for at the root, whatever the page declares; with the DEV / PREVIEW set where it applies."""
    env = icon_env()
    name = "favicon-32.png" if request.path == "/favicon.ico" else "apple-touch-icon.png"
    path = Path(__file__).parent / "static" / "icons" / (f"{env}/" if env else "") / name
    resp = send_file(path, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/sw.js")
def service_worker():
    return send_file(Path(__file__).parent / "sw.js", mimetype="application/javascript")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "airgradient_token_set": bool(TOKEN),
    })


@app.route("/api/current")
def current():
    if MODE == "no_token":   # a config but no token yet: the page says so; an expired token is a 502 below
        return jsonify({"state": "no_token"})
    try:
        value, info = cached("ag:current", lambda: api_get("/locations/measures/current"), ttl=30, keep=900, force=_force())
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    _note_cache(info)
    return jsonify(value)


HIST_KEEP = ("timestamp", "pm02", "pm02_corrected", "rco2", "rco2_corrected", "rhum", "rhum_corrected")   # history fields the charts and rules read
# the History ranges (hours) and how long each is cached: (fresh, then served stale while refreshing), in seconds
HIST_TTL = {1: (60, 240), 6: (60, 240), 24: (60, 240), 168: (300, 1800)}


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


@app.route("/api/history/<int:location_id>")
def history(location_id):
    chart_keep = HIST_KEEP   # PM2.5, CO2 and humidity: the three History charts
    try:
        frm, to = _iso(request.args["from"]), _iso(request.args["to"])
        hours = round((to - frm).total_seconds() / 3600)
        standard = hours in HIST_TTL and abs((datetime.now(timezone.utc) - to).total_seconds()) < 120
    except (KeyError, ValueError):
        standard = False
    try:
        if standard:   # the page's ranges ending now: served from the cache, cut to the asked start
            rows, info = history_rows(location_id, hours, force=_force())
            _note_cache(info)
            cut = frm.strftime("%Y-%m-%dT%H:%M:%S")
            rows = [r for r in rows if str(r.get("timestamp", ""))[:19] >= cut]
        else:
            params = {k: request.args[k] for k in ("from", "to") if request.args.get(k)}
            rows = api_get(f"/locations/{location_id}/measures/past", params)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify([{k: r.get(k) for k in chart_keep if r.get(k) is not None} for r in rows or [] if isinstance(r, dict)])


def _fetch_world():
    """Every public AirGradient monitor in the world, as the API lists them. Cached by the caller, in the request
    thread: a fetch that cached() runs in the pool must never call cached() itself (it would wait on its own pool)."""
    r = requests.get(f"{API_BASE}/world/locations/measures/current", timeout=15)
    r.raise_for_status()
    return r.json()


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


# The world list's cache (s): fresh 2 min (as the neighborhood always was), then served stale up to 15 min while it
# refreshes, kept 1 h when AirGradient fails; a request waits up to 20 s for it (it's ~1.5 MB).
WORLD_CACHE = {"ttl": 120, "swr": 900, "keep": 3600, "wait": 20}


@app.route("/api/neighborhood")
def neighborhood():
    if not source_on("nearby"):
        return jsonify([])
    try:
        world, info = cached("ag:world", _fetch_world, force=_force(), **WORLD_CACHE)
        value = _fetch_nearby(world)
    except Exception as e:
        return jsonify({"error": f"Neighborhood data unavailable: {e}"}), 502
    _note_cache(info)
    return jsonify(value)


def get_wind_cardinal(degrees):
    """Convert wind direction degrees to cardinal direction."""
    if degrees is None:
        return "variable"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(degrees / 22.5) % 16]


def hourly_forecast(weather, air):
    """The next 12 hours (13 entries from the current local hour), for Coming up and the model's LATER facts:
    rain, temperature, dew point, UV, the model's outdoor PM2.5, and whether the wind carries the road's exhaust here."""
    hourly = weather.get("hourly") or {}
    times = hourly.get("time") or []
    now_key = local_now().strftime("%Y-%m-%dT%H:00")
    start = next((k for k, t in enumerate(times) if t >= now_key), len(times))
    def col(name, k):
        vals = hourly.get(name) or []
        return vals[k] if k < len(vals) else None
    return [{
        "time": times[k],
        "pop": col("precipitation_probability", k),
        "precip": col("precipitation", k),
        "code": col("weather_code", k),
        "temp": col("temperature_2m", k),
        "dew": col("dew_point_2m", k),
        "wind_dir": col("wind_direction_10m", k),
        "uv": col("uv_index", k),
        "pm25": air.get(times[k]),   # the air-quality model's outdoor PM2.5 for that hour
        # whether that hour's wind carries the road's exhaust here (None without a wind direction; False without a road)
        "bqe_toward": None if col("wind_direction_10m", k) is None else
        road_traffic(int(times[k][11:13]), col("wind_direction_10m", k))["toward"],
    } for k in range(start, min(start + 13, len(times)))]


# The weather card's words. Dew point (°C) under DEW_DRY_C dries sinuses (the Open-Meteo source note says so), under
# DEW_SEVERE_DRY_C badly. Visibility (m) under each line reads very low, reduced, moderate; above the last, clear.
DEW_SEVERE_DRY_C, DEW_DRY_C = 5, 10
VISIBILITY_VERY_LOW_M, VISIBILITY_REDUCED_M, VISIBILITY_MODERATE_M = 2000, 5000, 10000


@app.route("/api/context")
def context():
    """Return external data sources (weather, pollen, the road, smoke) as structured JSON."""
    # Fetch independents in parallel; pollen has its own hard deadline inside get_pollen_data.
    weather_fut = _CONTEXT_POOL.submit(get_open_meteo_data)
    smoke_fut = _CONTEXT_POOL.submit(smoke_status) if source_on("smoke") else None
    pollen_fut = _CONTEXT_POOL.submit(get_pollen_days) if pollen_live() else None
    air_fut = _CONTEXT_POOL.submit(get_air_forecast)

    try:
        weather = weather_fut.result(timeout=12)
    except Exception:
        weather = {"current": {}}
    smoke = no_smoke()
    pollen_days = {"today": [], "tomorrow": []}
    if smoke_fut:
        try:
            smoke = smoke_fut.result(timeout=12)
        except Exception:
            pass
    if pollen_fut:
        try:
            pollen_days = pollen_fut.result(timeout=6)
        except Exception:
            pass
    pollen, pollen_tomorrow = pollen_days["today"], pollen_days["tomorrow"]
    try:
        air = air_fut.result(timeout=12)
    except Exception:
        air = {}

    cur = weather.get("current", {})
    wind_speed = cur.get("wind_speed_10m")
    wind_direction = cur.get("wind_direction_10m")
    visibility = cur.get("visibility")
    uv_index = cur.get("uv_index")
    dew_point = cur.get("dew_point_2m")
    temperature = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m")

    wind_dir = get_wind_cardinal(wind_direction)

    # Dew point sinus risk
    if dew_point is not None and dew_point < DEW_SEVERE_DRY_C:
        dew_point_risk = "Severe dryness"
    elif dew_point is not None and dew_point < DEW_DRY_C:
        dew_point_risk = "Moderate dryness"
    else:
        dew_point_risk = "Comfortable"

    # Visibility interpretation
    if visibility is not None:
        if visibility < VISIBILITY_VERY_LOW_M:
            visibility_status = "Very low — high particulate"
        elif visibility < VISIBILITY_REDUCED_M:
            visibility_status = "Reduced"
        elif visibility < VISIBILITY_MODERATE_M:
            visibility_status = "Moderate"
        else:
            visibility_status = "Clear"
    else:
        visibility_status = "Unknown"

    forecast = hourly_forecast(weather, air)

    # the road's traffic, and whether the wind blows its exhaust here
    current_hour = local_now().hour
    road = road_traffic(current_hour, wind_direction)
    road_cfg = active_road()
    if road_cfg:   # "bqe" is the shape the page reads today; "road" carries the flag (the page moves to it later)
        extra = {"bqe": {"traffic": road["traffic"], "wind_impact": road["wind_impact"],
                         "pollution_pressure": road["pollution_pressure"], "current_hour": current_hour},
                 "road": {"name": road_cfg.name, "toward": road["toward"]}}
    else:
        extra = {}

    # per source: ok, off (config), not_set_up (key missing) or error (on, but it didn't answer)
    pollen_s = pollen_state()
    status = {
        "pollen": ("ok" if pollen else "error") if pollen_s == "ok" else pollen_s,
        "smoke": ("ok" if smoke.get("checked") else "error") if source_on("smoke") else "off",
        "road": "ok" if road_cfg else "off",
        "nearby": "ok" if source_on("nearby") else "off",
    }

    return jsonify({
        "weather": {
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "wind_cardinal": wind_dir,
            "dew_point": dew_point,
            "dew_point_risk": dew_point_risk,
            "visibility": visibility,
            "visibility_status": visibility_status,
            "uv_index": uv_index,
            "temperature": temperature,
            "humidity": humidity,
            "cloud_cover": cur.get("cloud_cover"),
            "weather_code": cur.get("weather_code")
        },
        **extra,
        "smoke": smoke,
        "pollen": pollen,
        "pollen_tomorrow": pollen_tomorrow,
        "forecast": forecast,
        "status": status,
    })


# The road card's "pressure" is these two weights multiplied: an estimate shown as text, not a measurement.
# Traffic by hour: the first rush window, the others, the hour either side of a rush, and the rest of the day.
TRAFFIC_WEIGHT = {"first_rush": 1.5, "rush": 1.4, "shoulder": 1.2, "low": 0.7}
# Wind: blowing the exhaust toward home, away from it, across, or no direction known.
WIND_WEIGHT = {"toward": 1.3, "away": 0.5, "cross": 1.0, "unknown": 1.0}


def active_road():
    """The road /api/context reports: the home's, or None. demo/data.py turns it off for a public monitor."""
    return ROAD


def road_traffic(hour, wind_direction):
    """How much the road's traffic weighs on home at this hour: its rush, and whether the wind carries its exhaust here.

    Peak inside a rush window, shoulders an hour either side. The road's `toward` arc (config) holds the wind
    directions that carry its exhaust toward home (the reference home's BQE: from about 80-200°, E through S, so the road lies
    east through south within 2 km); the opposite arc carries it away; anything else is a crosswind.
    `toward` is the flag to test; wind_impact is display text. Without a road: toward False and nothing else.
    """
    if ROAD is None:
        return {"toward": False, "traffic": None, "wind_impact": None, "pollution_pressure": None}
    hour_int = int(hour)

    # Traffic intensity by hour
    peak = next(((i, name) for i, (a, b, name) in enumerate(RUSH_WINDOWS) if a <= hour_int < b), None)
    if peak:
        traffic_intensity = f"PEAK ({peak[1]} rush)"
        multiplier = TRAFFIC_WEIGHT["first_rush"] if peak[0] == 0 else TRAFFIC_WEIGHT["rush"]
    elif any(a - 1 <= hour_int <= b for a, b, _ in RUSH_WINDOWS):
        traffic_intensity = "HIGH (rush shoulders)"
        multiplier = TRAFFIC_WEIGHT["shoulder"]
    else:
        traffic_intensity = "LOW"
        multiplier = TRAFFIC_WEIGHT["low"]

    # Wind direction impact (wind_direction is where the wind comes FROM, in degrees)
    lo, hi = ROAD.toward
    toward = wind_direction is not None and bearing_in(wind_direction, ROAD.toward)
    if wind_direction is None:
        wind_impact = "Unknown"
        wind_multiplier = WIND_WEIGHT["unknown"]
    elif toward:
        wind_impact = f"Blowing toward {CFG.place.name}"
        wind_multiplier = WIND_WEIGHT["toward"]
    elif bearing_in(wind_direction, ((lo + 180) % 360, (hi + 180) % 360)):
        wind_impact = "Blowing away"
        wind_multiplier = WIND_WEIGHT["away"]
    else:
        wind_impact = "Crosswind"
        wind_multiplier = WIND_WEIGHT["cross"]

    pollution_pressure = multiplier * wind_multiplier

    return {
        "toward": toward,
        "traffic": traffic_intensity,
        "wind_impact": wind_impact,
        "pollution_pressure": round(pollution_pressure, 1)
    }


# ── Air summary (the new page) ──────────────────────────────────────────
# Rules decide every verdict and every sentence.

# RUSH_WINDOWS, PM_FINE (any hour, though WHO's 15 is a 24-hour average), PM_HIGH, CO2_OPEN, RH_LOW and RH_DAMP
# come from the config (use_config). The rest are the rules' own lines, not a household's:
CO2_VERY_HIGH = 1500   # ppm: over it, airing the room is urgent ("bad" tone), not just due ("warn")
RUN_NIGHT = (21, 5)    # hours [from, to): the run verdict speaks of tonight and the early morning
SLEEP_HOURS = (17, 7)  # hours [from, to): the toddler's line is about the air before sleep
MOISTURE_MARGIN_C = 1  # °C: outside air adds moisture when its dew point is this much above the room's
STALE_OUTDOOR = timedelta(hours=2)   # an outdoor reading older than this counts as no reading now (a monitor gone quiet)


def fnum(value):
    """Float or None. Zero is a real reading."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value, digits=1):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}" if digits else f"{round(value)}"


def fmt_hour(hour):
    hour %= 24
    return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"


def dew_point_c(temp_c, rh):
    if temp_c is None or rh is None or rh <= 0:
        return None
    a, b = 17.62, 243.12
    g = math.log(rh / 100) + a * temp_c / (b + temp_c)
    return b * g / (a - g)


def rush_hours():
    """The rush windows of the road in use (active_road()): the home's, or none without a road (a public monitor)."""
    return RUSH_WINDOWS if active_road() else []


def rush_state(hour):
    windows = rush_hours()
    if not windows:   # no road
        return {"in_rush": False, "name": None, "start": None, "end": None, "tomorrow": True}
    for start, end, name in windows:
        if start <= hour < end:
            return {"in_rush": True, "name": name, "start": start, "end": end}
    later = [w for w in windows if w[0] > hour]
    start, end, name = later[0] if later else windows[0]
    return {"in_rush": False, "name": name, "start": start, "end": end, "tomorrow": not later}


def verdict(word, tone, text, action=None):
    """action is the short imperative used in the lead when this verdict needs doing."""
    return {"word": word, "tone": tone, "text": text, "action": action}


def rule_run(outdoor_pm, smoke, rush, wind_toward, hour):
    if outdoor_pm is None:
        return verdict("No reading", "muted", "The outdoor monitor has not reported, so there is no run answer.")
    pm = fmt_num(outdoor_pm)
    if outdoor_pm > PM_HIGH:
        return verdict("Skip it", "bad", f"Outdoor PM2.5 is {pm} µg/m³, over {PM_HIGH}. Skip the run, and keep the toddler in.")
    if outdoor_pm > PM_FINE or smoke:
        why = f"Outdoor PM2.5 is {pm} µg/m³, over {PM_FINE}" if outdoor_pm > PM_FINE else "NOAA reports wildfire smoke over the region"
        return verdict("Keep it short", "warn", f"{why}. Keep a run short and easy.")
    base = f"Outdoor PM2.5 is {pm} µg/m³, under {PM_FINE}."
    if rush["in_rush"] and wind_toward:
        return verdict(f"After {fmt_hour(rush['end'])}", "warn",
                       f"{base} The {ROAD.name} {rush['name']} rush runs until {fmt_hour(rush['end'])} with the wind toward {CFG.place.name}, so run after that.")
    if hour >= RUN_NIGHT[0] or hour < RUN_NIGHT[1]:
        windows = rush_hours()
        return verdict("Fine", "good", f"{base} Tonight is fine, and so is the morning before the {fmt_hour(windows[0][0])} rush."
                       if windows else f"{base} Tonight is fine.")
    if not rush["in_rush"] and not rush.get("tomorrow") and wind_toward:
        return verdict(f"Fine until {fmt_hour(rush['start'])}", "good",
                       f"{base} Fine for a run, and for the toddler outside, until {fmt_hour(rush['start'])}. Then the {ROAD.name} rush starts, with the wind toward {CFG.place.name}.")
    return verdict("Fine", "good", f"{base} Fine for a run, and for the toddler outside.")


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


def clock_label(ts, now_local):
    label = ts.strftime("%-I:%M %p")
    return label if ts.date() == now_local.date() else label + " yesterday"


def stretch(points, key, is_off, now_local, hours=24):
    """The unbroken stretch where is_off holds, running up to the latest reading: {"label": "all day" or "since 3:10 PM"}."""
    vals = [(t, key(r)) for t, r in points]
    vals = [(t, v) for t, v in vals if v is not None]
    if not vals or not is_off(vals[-1][1]):
        return None
    i = len(vals) - 1
    while i > 0 and is_off(vals[i - 1][1]):
        i -= 1
    start = vals[i][0]
    whole = i == 0 and (start - (now_local - timedelta(hours=hours))).total_seconds() < 3600
    return {"label": "all day" if whole else "since " + clock_label(start, now_local)}


def co2_of(r):
    return fnum(r.get("rco2_corrected", r.get("rco2")))


def rh_in_of(r):
    return fnum(r.get("rhum", r.get("rhum_corrected")))


def pm_of(r):
    return fnum(r.get("pm02_corrected", r.get("pm02")))


def build_needs(co2, rh, pm_out, adds_moisture, pollen, top_pollen, actions, run_item, co2_run, now):
    """One line per need, in the header pill's order: Toddler, Sinus & allergy, Runner.
    Each need is paired with the card that holds its evidence (metric)."""
    keyed = {a["key"]: a for a in actions}
    evening = now.hour >= SLEEP_HOURS[0] or now.hour < SLEEP_HOURS[1]

    # Toddler: the indoor air (CO2), unless the outside air keeps them in.
    if pm_out is not None and pm_out > PM_HIGH:
        tod = ("bad", "Keep the toddler inside", f"Outdoor PM2.5 is {fmt_num(pm_out)}, over {PM_HIGH}.")
    elif co2 is not None and co2 > CO2_OPEN:
        since = co2_run["label"] if co2_run else ""
        tod = ("bad" if co2 > CO2_VERY_HIGH else "warn", "Open a window before sleep" if evening else "Air the room",
               f"CO₂ has been over {CO2_OPEN} {since}." if since and since != "all day" else f"CO₂ is {co2:.0f} ppm, over {CO2_OPEN}.")
    elif co2 is not None:
        tod = ("good", "Fresh air for sleep" if evening else "Fresh air indoors", f"CO₂ is {co2:.0f} ppm, under {CO2_OPEN}.")
    else:
        tod = ("muted", "No indoor reading", "The indoor monitor has not reported.")

    # Sinus & allergy: humidity first, then pollen.
    pol = (top_pollen.get("index") or 0) if top_pollen else None
    if "humidity" in keyed:
        a = keyed["humidity"]
        sin = ("warn", a["text"], a["why"])
    elif "pollen" in keyed:
        sin = ("warn", "Limit time outside", keyed["pollen"]["why"])
    elif rh is not None:
        sin = ("good", "Nothing to do", f"Humidity is {rh:.0f}%" + (f" and pollen is {pol} of 5." if pol is not None else "."))
    else:
        sin = ("muted", "No indoor reading", "The indoor monitor has not reported humidity.")

    # Runner: the run verdict from the rules.
    run = keyed.get("run") or run_item
    rn = (run["tone"], run["text"], run["why"]) if run else ("muted", "No outdoor reading", "The outdoor monitor has not reported.")

    def need(nid, name, metric, v):
        return {"id": nid, "name": name, "metric": metric, "tone": v[0], "action": v[1], "why": v[2]}
    out = [need("toddler", "Toddler", "co2", tod), need("sinus", "Sinus & allergy", "humidity", sin), need("runner", "Runner", "pm", rn)]
    out[1]["pollen"] = [{"name": q.get("name"), "index": q.get("index") or 0, "in_season": bool(q.get("in_season"))} for q in (pollen or [])]
    return out


def _local(ts, tz):
    """'2026-11-08T16:00' (Open-Meteo, local) as an aware datetime."""
    return datetime.fromisoformat(ts).replace(tzinfo=tz)


def summary_inputs(payload, co2, rh, rh_out, t_in, t_out, pm_out, pts_in, pts_out, now):
    """Gather what summary.build_summary needs from the caches the page already fills. For a public monitor without
    history (AirGradient's public map has none for it, or didn't answer), the chart's past PM2.5 is the model's."""
    tz = now.tzinfo
    weather = get_open_meteo_data()
    hw, daily = weather.get("hourly") or {}, weather.get("daily") or {}
    col = lambda name, k: (hw.get(name) or [None] * (k + 1))[k] if k < len(hw.get(name) or []) else None
    hourly = [{"t": _local(t, tz), "temp": col("temperature_2m", k), "pop": col("precipitation_probability", k),
               "mm": col("precipitation", k), "uv": col("uv_index", k), "wind_dir": col("wind_direction_10m", k)}
              for k, t in enumerate(hw.get("time") or [])]
    cams = sorted((_local(t, tz), v) for t, v in (get_air_forecast() or {}).items())
    pm_past = [(t, pm_of(x)) for t, x in pts_out]
    model_past = [(t, v) for t, v in cams if t <= now and v is not None]
    # a public monitor only (outdoor_row): a home without history (AirGradient failed) keeps an empty past
    pm_past_model = outdoor_row() is not None and not pm_past and bool(model_past)
    if pm_past_model:
        pm_past = model_past
    road = active_road()
    sun = [{"t": _local(t, tz), "kind": kind} for key, kind in (("sunrise", "Sunrise"), ("sunset", "Sunset"))
           for t in daily.get(key) or [] if t]
    days = get_pollen_days() if pollen_live() else {"today": [], "tomorrow": []}
    top = lambda types: max(types, key=lambda q: q.get("index") or 0) if types else None
    return {"r": {"co2": co2, "rh": rh, "rh_out": rh_out, "t_in": t_in, "t_out": t_out, "pm_now": pm_out},
            "cams": cams, "hourly": hourly,
            "co2_pts": [(t, co2_of(x)) for t, x in pts_in], "rh_pts": [(t, rh_in_of(x)) for t, x in pts_in],
            "pm_past": pm_past, "smoke": get_smoke_data() if source_on("smoke") else False,
            "pollen_today": top(days.get("today")), "pollen_tomorrow": top(days.get("tomorrow")),
            "rush": rush_windows(hourly, now), "road": road.name if road else None, "sun": sun, "now": now,
            # whose reading the PM2.5 forecast is fitted to, in its sentence: a public monitor is "this monitor"
            "monitor_label": "this monitor" if outdoor_row() is not None else f"your {phrases.LIMIT_FACTS['outdoor']} monitor",
            **({"pm_past_model": True} if pm_past_model else {})}


def rush_windows(hourly, now):
    """Today's and tomorrow's rush windows of the road, each with whether the forecast wind blows its exhaust here."""
    road = active_road()
    return summary_rules.rush_windows(hourly, now, rush_hours(), road.toward) if road else []


def needs_on(needs):
    """Only the needs the page's view turns on: the home's config, or a public monitor's (runner only, demo/data.py)."""
    on = page_view().get("needs") or {}
    return [n for n in needs if on.get(n["id"], True)]


def outdoor_row():
    """The outdoor monitor's latest row as AirGradient lists it (timestamp, offline), when the server holds it: None
    for a home, whose page posts its reading. demo/data.py gives a public monitor's."""
    return None


def outdoor_current(row, now):
    """Whether the outdoor reading counts as a reading now: no row to judge by, or online and under STALE_OUTDOOR old."""
    if row is None:
        return True
    if row.get("offline"):
        return False
    try:
        ts = datetime.fromisoformat(str(row.get("timestamp")).replace("Z", "+00:00"))
        return ts.tzinfo is not None and now - ts <= STALE_OUTDOOR
    except ValueError:
        return False


def safe_summary(inputs):
    """The new card, or None (logged) if the rules fail on odd data: the page then keeps its previous card."""
    try:
        s = summary_rules.build_summary(**inputs)
        s["needs"] = needs_on(s["needs"])
        return s
    except Exception as e:  # never let the card take the whole read down
        app.logger.warning("summary failed: %s: %s", type(e).__name__, e)
        return None


def build_air_read(payload):
    now = local_now()
    co2 = fnum(payload.get("indoor_co2"))
    rh = fnum(payload.get("indoor_humidity"))
    t_in = fnum(payload.get("indoor_temp_c"))
    pm_out = fnum(payload.get("outdoor_pm25"))
    rh_out = fnum(payload.get("outdoor_humidity"))
    t_out = fnum(payload.get("outdoor_temp_c"))
    if not outdoor_current(outdoor_row(), now):   # offline or stale: the model speaks for PM2.5 now, not an old reading
        pm_out = rh_out = t_out = None

    weather = get_open_meteo_data().get("current", {})
    wind_direction = weather.get("wind_direction_10m")
    wind_toward = road_traffic(now.hour, wind_direction)["toward"]
    smoke = get_smoke_data() if source_on("smoke") else False
    pollen = get_pollen_data(HOME_LAT, HOME_LON) if pollen_live() else []
    rush = rush_state(now.hour)

    in_dp, out_dp = dew_point_c(t_in, rh), dew_point_c(t_out, rh_out)
    if out_dp is None:
        out_dp = fnum(weather.get("dew_point_2m"))
    adds_moisture = in_dp is not None and out_dp is not None and out_dp - in_dp > MOISTURE_MARGIN_C
    pts_in = history_points(payload.get("indoor_location_id"), now)
    pts_out = history_points(payload.get("outdoor_location_id"), now)

    co2_run = stretch(pts_in, co2_of, lambda v: v > CO2_OPEN, now)

    # ── Actions, ranked by the rules ──
    actions = []  # each: {"key", "text", "why", "tone"}
    if co2 is not None and co2 > CO2_OPEN:
        since = co2_run["label"] if co2_run else ""
        if pm_out is not None and pm_out > PM_HIGH:
            actions.append({"key": "window", "tone": "warn", "text": "Keep windows shut for now",
                            "why": f"CO₂ is {co2:.0f}, but the air outside is not clean ({fmt_num(pm_out)})."})
        else:
            short = adds_moisture and rh is not None and rh > RH_DAMP
            actions.append({"key": "window", "tone": "bad" if co2 > CO2_VERY_HIGH else "warn",
                            "text": "Open a window for a few minutes" if short else "Open a window",
                            "why": f"CO₂ has been over the {CO2_OPEN} limit {since}." if since and since != "all day"
                                   else f"CO₂ is {co2:.0f}, over the {CO2_OPEN} limit."})
    if rh is not None and rh > RH_DAMP:
        window_too = any(a["key"] == "window" for a in actions)
        actions.append({"key": "humidity", "tone": "warn",
                        "text": "Air the room briefly, then dry it" if window_too and adds_moisture else "Dry the indoor air",
                        "why": f"The room is too damp ({rh:.0f}%)" + (", and the air outside holds more water." if adds_moisture else ".")})
    elif rh is not None and rh < RH_LOW:
        actions.append({"key": "humidity", "tone": "warn", "text": "Add moisture to the air",
                        "why": f"The air is dry ({rh:.0f}%), which irritates sinuses."})
    run_v = rule_run(pm_out, smoke, rush, wind_toward, now.hour)
    run_item = None
    w = run_v["word"]
    if w == "Skip it":
        actions.append({"key": "run", "tone": "bad", "text": "Skip the run", "why": f"Outdoor PM2.5 is {fmt_num(pm_out)}, over {PM_HIGH}."})
    elif w == "Keep it short":
        actions.append({"key": "run", "tone": "warn", "text": "Keep a run short and easy", "why": run_v["text"].split(". ")[0] + "."})
    elif w.startswith("After"):
        actions.append({"key": "run", "tone": "warn", "text": "Run " + w.lower(), "why": f"The {ROAD.name} rush runs until {w[6:]}, with the wind toward {CFG.place.name}."})
    elif w.startswith("Fine until"):
        run_item = {"key": "run", "tone": "good", "text": "Run before " + w[11:], "why": f"The air outside is clean; the {w[11:]} rush blows this way."}
    elif w == "Fine":
        night = now.hour >= RUN_NIGHT[0] or now.hour < RUN_NIGHT[1]
        windows = rush_hours()
        run_item = {"key": "run", "tone": "good", "text": f"Run tonight or before {fmt_hour(windows[0][0])}" if night and windows else "Fine to run",
                    "why": "The air outside is clean" + (f"; the {fmt_hour(windows[0][0])} rush blows this way." if night and wind_toward and windows else ".")}
    top_pollen = max(pollen, key=lambda q: q.get("index") or 0) if pollen else None
    if top_pollen and (top_pollen.get("index") or 0) >= LIMITS["pollen"]:
        actions.append({"key": "pollen", "tone": "warn", "text": "Limit time outside", "why": f"{top_pollen['name']} pollen is {top_pollen['index']} of 5."})
    needs = needs_on(build_needs(co2, rh, pm_out, adds_moisture, pollen, top_pollen, actions, run_item, co2_run, now))
    order = {"window": 0, "humidity": 1, "run": 2, "pollen": 3}
    actions.sort(key=lambda a: ({"bad": 0, "warn": 1}.get(a["tone"], 2), order[a["key"]]))

    if actions:
        head, also = actions[0], actions[1:] + ([run_item] if run_item else [])
        tone, why = head["tone"], head["why"]
    else:
        also, tone = [], "good"
        if run_item and run_item["text"].startswith("Run before"):
            why = f"The air outside is clean, and the {ROAD.name} {rush['name']} rush starts at {fmt_hour(rush['start'])}."
        elif run_item:
            why = run_item["why"]
        else:
            why = "Every reading is inside its limit."

    result = {
        "generated_at": now.isoformat(), "clock": now.strftime("%-I:%M %p"), "status": tone, "why": why,
        "also": [{"text": a["text"], "why": a["why"], "tone": a["tone"]} for a in also],
        "needs": needs,
    }
    # the new card: items, needs and the day chart, all from the rules (summary.py)
    summary_in = summary_inputs(payload, co2, rh, rh_out, t_in, t_out, pm_out, pts_in, pts_out, now)
    result["summary"] = safe_summary(summary_in)

    return result


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """The page's air summary as one JSON object. Only "format": "read" is served."""
    data = request.get_json(silent=True) or {}
    if data.get("format") == "read":
        return jsonify(build_air_read(data))
    return jsonify({"error": 'POST {"format": "read", ...}'}), 400


def request_moment():
    """The demo moment this request asked for (?sample=1|2|3 or ?moment=<key>), or the default one."""
    from demo.moments import moment_for
    try:
        return moment_for(request.args.get("moment"), request.args.get("sample"))
    except RuntimeError:   # outside a request
        return moment_for(None)


def monitor_missing():
    """True when this request asked for a public monitor that can't be shown. Demo only: demo/data.py answers it."""
    return False


# digits: the longest ?monitor= read as an id (AirGradient's are 5-6 digits today); a longer one is junk, and past
# about 4,300 digits Python's int() raises instead of reading it
MONITOR_ID_MAX_DIGITS = 12


def request_monitor():
    """The public monitor this request asked for (?monitor=, a positive whole number), or None."""
    try:
        raw = request.args.get("monitor", "")
    except RuntimeError:   # outside a request
        return None
    ok = raw.isascii() and raw.isdigit() and len(raw) <= MONITOR_ID_MAX_DIGITS
    return int(raw) if ok and int(raw) > 0 else None


@app.route("/api/monitors")
def monitors():
    """The demo's monitor picker: the public outdoor monitors nearest ?lat=&lon= (rounded again to 2 decimals, about
    1 km), or nearest New York without them. Demo only."""
    if MODE != "demo":
        return jsonify({"error": "not found"}), 404
    from demo import public
    lat, lon = request.args.get("lat"), request.args.get("lon")
    if lat is None and lon is None:
        near, lat, lon = public.DEFAULT_LIST
    else:
        try:
            lat, lon = round(float(lat), 2), round(float(lon), 2)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "lat and lon must be a place's coordinates"}), 400
        near = "you"
    try:
        world = demo_data.world_list()
    except demo_data.WORLD_ERRORS:
        return jsonify({"error": public.WORLD_DOWN}), 502
    return jsonify({"near": near, "monitors": public.nearest(world, lat, lon)})


if MODE == "demo":   # every outside source becomes made-up data, generated per request (demo/data.py)
    from demo import data as demo_data
    demo_data.install(sys.modules[__name__], request_moment)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5555))
    host = os.environ.get("HOST", "127.0.0.1")   # HOST=0.0.0.0 to open it from a phone on the same network
    print(f"Home Air Quality → http://localhost:{port}")
    app.run(host=host, port=port, debug=False)
