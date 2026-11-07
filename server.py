"""AirGradient Dashboard — Local proxy server.

Deployed on Railway with Anthropic API integration for AI analysis.
"""

import hashlib
import json
import math
import os
import subprocess
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_file
import requests

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
# One in-memory store for upstream data (AirGradient, Open-Meteo, Google Pollen, NOAA, the model).
# - fresh (age < ttl): served as is
# - a little old (age < ttl + swr): served at once, refreshed in the background
# - older or missing: fetched; concurrent requests for the same key share one fetch
# - fetch fails: the last good value is served if it's younger than `keep`
# Fetch functions must raise on failure (so a bad answer is never stored) and must not call cached() themselves.
import logging
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("aq.cache")
_REFRESH_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cache")
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


# ── Limits on paid model calls ──
# Every model call costs money, and the page is public. Three caps, in memory (one server process):
# per visitor (IP) per hour, for the whole site per minute, and for the whole site per day.
# Past a cap, the advice falls back to the rules' wording; nothing breaks.
AI_CAP_PER_IP_HOUR = int(os.environ.get("AI_CAP_PER_IP_HOUR", "20"))
AI_CAP_PER_MINUTE = int(os.environ.get("AI_CAP_PER_MINUTE", "10"))
AI_CAP_PER_DAY = int(os.environ.get("AI_CAP_PER_DAY", "300"))
FORCE_CAP_PER_IP_10MIN = 6     # Refresh presses that rewrite the advice, per visitor
_ai_log, _force_log, _ai_lock = [], {}, threading.Lock()


def client_ip():
    """The visitor's address. Railway's proxy puts it first in X-Forwarded-For."""
    try:
        fwd = request.headers.get("X-Forwarded-For", "")
        return (fwd.split(",")[0].strip() or request.remote_addr or "?")
    except RuntimeError:
        return "?"


def ai_allowed(ip):
    """Records a model call and returns None if it's within the caps, else the reason it isn't."""
    now = time.time()
    with _ai_lock:
        _ai_log[:] = [(t, a) for t, a in _ai_log if now - t < 86400]
        if len(_ai_log) >= AI_CAP_PER_DAY:
            return "day"
        if sum(1 for t, _ in _ai_log if now - t < 60) >= AI_CAP_PER_MINUTE:
            return "minute"
        if sum(1 for t, a in _ai_log if a == ip and now - t < 3600) >= AI_CAP_PER_IP_HOUR:
            return "visitor"
        _ai_log.append((now, ip))
    return None


def force_allowed(ip):
    """A visitor can make the server skip its cache a few times per 10 minutes; after that, cached data is served."""
    now = time.time()
    with _ai_lock:
        hits = [t for t in _force_log.get(ip, []) if now - t < 600]
        if len(hits) >= FORCE_CAP_PER_IP_10MIN:
            _force_log[ip] = hits
            return False
        _force_log[ip] = hits + [now]
        if len(_force_log) > 5000:
            _force_log.clear()
    return True


def _force():
    """The page's Refresh button sends X-Force-Refresh: 1."""
    # Free sources only; each has a floor (15 s, 10 min for Google Pollen) so repeats don't refetch.
    # The paid model call has its own per-visitor cap in build_air_read.
    try:
        return request.headers.get("X-Force-Refresh") == "1"
    except RuntimeError:   # outside a request
        return False


def _note_cache(info):
    try:
        g.cache_state, g.cache_age = info["state"], int(info["age"])
    except RuntimeError:
        pass


# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

app = Flask(__name__)

API_BASE = "https://api.airgradient.com/public/api/v1"
TOKEN = os.environ.get("AIRGRADIENT_TOKEN", "")
# Rounded to ~1 km on purpose (public repo): weather, pollen, smoke and the 15 km radius don't need more.
HOME_LAT = 40.73
HOME_LON = -73.95
NEARBY_RADIUS_KM = 15

try:
    from zoneinfo import ZoneInfo
    HOME_TZ = ZoneInfo("America/New_York")
except Exception:  # no tz database on the host
    HOME_TZ = None


def local_now():
    """The clock at home. Railway runs in UTC, so a bare datetime.now() gives the wrong hour there."""
    if HOME_TZ is not None:
        return datetime.now(HOME_TZ)
    # US Eastern without a tz database: DST runs from the second Sunday of March to the first Sunday of November.
    utc = datetime.now(timezone.utc)
    year = utc.year
    march = datetime(year, 3, 8, 7, tzinfo=timezone.utc)
    dst_start = march + timedelta(days=(6 - march.weekday()) % 7)
    november = datetime(year, 11, 1, 6, tzinfo=timezone.utc)
    dst_end = november + timedelta(days=(6 - november.weekday()) % 7)
    offset = -4 if dst_start <= utc < dst_end else -5
    return utc.astimezone(timezone(timedelta(hours=offset)))


def get_build_info():
    """Get git commit hash and deployment time in ET timezone."""
    try:
        # Get latest commit hash (short 7 chars)
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
            timeout=5
        ).decode().strip()
    except Exception:
        commit = "no-git"

    # Current deploy time in ET (NYC timezone) using simple offset calculation
    # ET is UTC-4 (EDT) or UTC-5 (EST)
    import time
    if time.daylight:
        # During daylight saving time (EDT): UTC-4
        offset_hours = -4
    else:
        # During standard time (EST): UTC-5
        offset_hours = -5

    from datetime import timezone, timedelta
    et_tz = timezone(timedelta(hours=offset_hours))
    time_str = datetime.now(et_tz).strftime("%H:%M:%S ET")

    return f"v2 · {commit} · {time_str}"


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
        raise RuntimeError(f"AirGradient API returned {status}: {e.response.text[:300]}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"AirGradient API unreachable: {e}") from e


def _fetch_weather():
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": HOME_LAT,
            "longitude": HOME_LON,
            "current": "temperature_2m,relative_humidity_2m,dew_point_2m,weather_code,wind_speed_10m,wind_direction_10m,visibility,uv_index,cloud_cover",
            "hourly": "wind_direction_10m,wind_speed_10m,precipitation_probability,precipitation,weather_code,temperature_2m,dew_point_2m,uv_index",
            "forecast_hours": 24,
            "timezone": "America/New_York"
        },
        timeout=10
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("current"):
        raise RuntimeError("Open-Meteo answered without current weather")
    return data


def get_open_meteo_data(lat=None, lon=None):
    """Weather from Open-Meteo (free, no key). Their current data moves on a 15-minute grid."""
    try:
        value, info = cached("wx", _fetch_weather, ttl=600, swr=3600, keep=3 * 3600, force=_force(), force_floor=300)
        return value
    except Exception:
        return {
            "current": {"wind_speed_10m": None, "wind_direction_10m": None, "visibility": None, "uv_index": None, "dew_point_2m": None},
            "hourly": {"wind_direction_10m": [], "wind_speed_10m": []}
        }


def _fetch_air_forecast():
    """Outdoor PM2.5 for the next 24 hours from Open-Meteo's air-quality model (CAMS, free, no key)."""
    r = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={"latitude": HOME_LAT, "longitude": HOME_LON, "hourly": "pm2_5",
                "forecast_hours": 24, "timezone": "America/New_York"},
        timeout=10
    )
    r.raise_for_status()
    hourly = r.json().get("hourly") or {}
    times, vals = hourly.get("time") or [], hourly.get("pm2_5") or []
    if not times:
        raise RuntimeError("Open-Meteo air quality answered without hours")
    return dict(zip(times, vals))


def get_air_forecast():
    """{"2026-11-07T18:00": pm2.5, ...}; empty when the model can't be reached. A model, so it can sit above or
    below the monitor: the page reacts to how it changes, not just its level."""
    try:
        value, _ = cached("aq", _fetch_air_forecast, ttl=1800, swr=3600, keep=6 * 3600, force=_force(), force_floor=300)
        return value
    except Exception:
        return {}


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


def smoke_status():
    """Whether NOAA HMS mapped wildfire smoke over home, from today's file (or yesterday's until today's is posted).

    Returns {"checked": bool, "detected": bool, "density": "Light"|"Medium"|"Heavy"|None, "date": "YYYY-MM-DD"|None}.
    """
    try:
        value, _ = cached("smoke", _fetch_smoke, ttl=1800, swr=6 * 3600, keep=24 * 3600, force=_force(), force_floor=600)
        return value
    except Exception:
        return {"checked": False, "detected": False, "density": None, "date": None}


def _fetch_smoke():
    """Today's NOAA HMS file, or yesterday's until today's is posted. Raises when neither loads."""
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
        rank = {"Light": 1, "Medium": 2, "Heavy": 3}
        best = None
        for mark in re.findall(r"<Placemark>(.*?)</Placemark>", r.text, re.S):
            dens = re.search(r"Density:\s*(Light|Medium|Heavy)", mark)
            for coords in re.findall(r"<coordinates>(.*?)</coordinates>", mark, re.S):
                ring = []
                for triple in coords.split():
                    parts = triple.split(",")
                    if len(parts) >= 2:
                        ring.append((float(parts[0]), float(parts[1])))
                if len(ring) > 2 and _point_in_ring(HOME_LON, HOME_LAT, ring):
                    d = dens.group(1) if dens else "Light"
                    if best is None or rank[d] > rank[best]:
                        best = d
        return {"checked": True, "detected": best is not None, "density": best, "date": day.strftime("%Y-%m-%d")}
    raise RuntimeError("No NOAA HMS smoke file for today or yesterday")


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
    api_key = os.environ.get("GOOGLE_POLLEN_API_KEY", "")
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
    """Add ?v=<hash> to every /static/*.css and /static/*.js reference."""
    return re.sub(r'"(/static/[\w./-]+\.(?:css|js))"', lambda m: f'"{m.group(1)}?v={asset_version(m.group(1))}"', html)


@app.after_request
def api_headers(resp):
    """No browser HTTP caching of live data (the server cache does that); say how fresh the answer is."""
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
        if getattr(g, "cache_state", None):
            resp.headers["X-Cache"] = g.cache_state
            resp.headers["X-Data-Age"] = str(g.cache_age)
    return resp


def icon_env():
    """Which icon set this address gets: "dev" locally (localhost and local network IPs), "preview" on the Railway dev
    service, None (the clean icons) everywhere else, production included."""
    host = (request.host or "").split(":")[0].lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0") or host.startswith(("127.", "10.", "192.168.")) or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host):
        return "dev"
    if host == "air-quality-dashboard-dev.up.railway.app":
        return "preview"
    return None


ENV_LABEL = {"dev": "DEV", "preview": "PREVIEW"}


def tag_env(html):
    """DEV / PREVIEW icons, tab title and home-screen name, so the environments can't be mixed up."""
    env = icon_env()
    if not env:
        return html
    html = re.sub(r'(<link rel="(?:icon|apple-touch-icon)"[^>]*href=")/static/icons/', rf'\1/static/icons/{env}/', html)
    html = html.replace("<title>Home Air Quality</title>", f"<title>{ENV_LABEL[env]} · Home Air Quality</title>", 1)
    html = html.replace('<meta name="apple-mobile-web-app-title" content="Air Quality">', f'<meta name="apple-mobile-web-app-title" content="AQ {ENV_LABEL[env]}">', 1)
    return html


@app.route("/")
def index():
    html_path = Path(__file__).parent / "index.html"
    html = tag_env(version_assets(html_path.read_text()))

    # Inject build info into a data attribute on the body
    build_info = get_build_info()
    html = html.replace(
        '<body>',
        f'<body data-build="{build_info}">'
    )

    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/v1")
def v1():
    """Previous live page. The new page is /."""
    html_path = Path(__file__).parent / "v1.html"
    html = html_path.read_text()
    html = html.replace("<body>", f'<body data-build="{get_build_info()}">', 1)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/archive/home-air")
def archive_home_air():
    """Earlier redesign, kept for comparison. Not the live page."""
    html_path = Path(__file__).parent / "archive" / "home-air.html"
    if not html_path.exists():   # local-only mockups, not in the repo
        return "Not found", 404
    html = html_path.read_text()
    html = html.replace("<body>", f'<body data-build="{get_build_info()}">', 1)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/archive/proposal")
def archive_proposal():
    """Static mock. Does not replace the live page."""
    html_path = Path(__file__).parent / "archive" / "proposal.html"
    if not html_path.exists():   # local-only mockups, not in the repo
        return "Not found", 404
    html = html_path.read_text()
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/manifest.json")
def manifest():
    path = Path(__file__).parent / "manifest.json"
    env = icon_env()
    if not env:
        return send_file(path, mimetype="application/manifest+json")
    data = json.loads(path.read_text())   # the installed app gets the DEV / PREVIEW icons and name too
    data["name"] = f'{data.get("name", "Home Air Quality")} ({ENV_LABEL[env]})'
    data["short_name"] = f"AQ {ENV_LABEL[env]}"
    for ic in data.get("icons", []):
        if str(ic.get("src", "")).startswith("/static/icons/"):
            ic["src"] = ic["src"].replace("/static/icons/", f"/static/icons/{env}/", 1)
    resp = jsonify(data)
    resp.headers["Content-Type"] = "application/manifest+json"
    return resp


@app.route("/sw.js")
def service_worker():
    return send_file(Path(__file__).parent / "sw.js", mimetype="application/javascript")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "airgradient_token_set": bool(TOKEN),
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.route("/api/current")
def current():
    try:
        value, info = cached("ag:current", lambda: api_get("/locations/measures/current"), ttl=30, keep=900, force=_force())
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    _note_cache(info)
    return jsonify(value)


HIST_KEEP = ("timestamp", "pm02", "pm02_corrected", "rco2", "rco2_corrected", "rhum", "rhum_corrected")
HIST_TTL = {1: (60, 240), 6: (60, 240), 24: (60, 240), 168: (300, 1800)}   # hours: (ttl, swr)


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
    chart_keep = ("timestamp", "pm02", "pm02_corrected", "rco2", "rco2_corrected")
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


def _fetch_nearby():
    r = requests.get(f"{API_BASE}/world/locations/measures/current", timeout=15)
    r.raise_for_status()
    nearby = []
    for loc in r.json():
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat and lon:
            d = haversine_km(HOME_LAT, HOME_LON, lat, lon)
            if d < NEARBY_RADIUS_KM:
                loc["distance_km"] = round(d, 1)
                nearby.append(loc)
    nearby.sort(key=lambda x: x["distance_km"])
    return nearby


@app.route("/api/neighborhood")
def neighborhood():
    try:
        value, info = cached("ag:nearby", _fetch_nearby, ttl=120, swr=900, keep=3600, force=_force(), wait=20)
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
    rain, temperature, dew point, UV, the model's outdoor PM2.5, and whether the wind carries BQE exhaust here."""
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
        # whether that hour's wind carries the BQE's exhaust here (None without a wind direction)
        "bqe_toward": None if col("wind_direction_10m", k) is None else
        predict_bqe_traffic(int(times[k][11:13]), col("wind_direction_10m", k))["wind_impact"] == "Blowing toward Greenpoint",
    } for k in range(start, min(start + 13, len(times)))]


@app.route("/api/context")
def context():
    """Return external data sources (weather, pollen, BQE, smoke) as structured JSON."""
    # Fetch independents in parallel; pollen has its own hard deadline inside get_pollen_data.
    weather_fut = _CONTEXT_POOL.submit(get_open_meteo_data, HOME_LAT, HOME_LON)
    smoke_fut = _CONTEXT_POOL.submit(smoke_status)
    pollen_fut = _CONTEXT_POOL.submit(get_pollen_days)
    air_fut = _CONTEXT_POOL.submit(get_air_forecast)

    try:
        weather = weather_fut.result(timeout=12)
    except Exception:
        weather = {"current": {}}
    try:
        smoke = smoke_fut.result(timeout=12)
    except Exception:
        smoke = {"checked": False, "detected": False, "density": None, "date": None}
    try:
        pollen_days = pollen_fut.result(timeout=6)
    except Exception:
        pollen_days = {"today": [], "tomorrow": []}
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
    if dew_point is not None and dew_point < 5:
        dew_point_risk = "Severe dryness"
    elif dew_point is not None and dew_point < 10:
        dew_point_risk = "Moderate dryness"
    else:
        dew_point_risk = "Comfortable"

    # Visibility interpretation
    if visibility is not None:
        if visibility < 2000:
            visibility_status = "Very low — high particulate"
        elif visibility < 5000:
            visibility_status = "Reduced"
        elif visibility < 10000:
            visibility_status = "Moderate"
        else:
            visibility_status = "Clear"
    else:
        visibility_status = "Unknown"

    forecast = hourly_forecast(weather, air)

    # BQE traffic
    current_hour = local_now().hour
    bqe = predict_bqe_traffic(current_hour, wind_direction)

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
        "bqe": {
            "traffic": bqe["traffic"],
            "wind_impact": bqe["wind_impact"],
            "pollution_pressure": bqe["pollution_pressure"],
            "current_hour": current_hour
        },
        "smoke": smoke,
        "pollen": pollen,
        "pollen_tomorrow": pollen_tomorrow,
        "forecast": forecast
    })


BQE_TOWARD = (80, 200)   # wind from these directions carries BQE exhaust toward home


def predict_bqe_traffic(hour, wind_direction):
    """Predict BQE pollution impact based on time of day and wind direction.

    BQE peaks: 7-10 AM and 4-8 PM.
    Where the BQE is: within 2 km of home it lies east through south (bearings ~83-194°, nearest
    ~0.95 km south-east, along Meeker Ave and the Kosciuszko Bridge approach; from OpenStreetMap routing).
    So wind FROM about 80-200° (E, SE, S) carries its exhaust toward home; wind from about 260-20°
    (W, NW, N) carries it away; anything else is a crosswind.
    """
    hour_int = int(hour)

    # Traffic intensity by hour
    if 7 <= hour_int <= 9:
        traffic_intensity = "PEAK (morning rush)"
        multiplier = 1.5
    elif 16 <= hour_int <= 19:
        traffic_intensity = "PEAK (evening rush)"
        multiplier = 1.4
    elif 6 <= hour_int <= 10 or 15 <= hour_int <= 20:
        traffic_intensity = "HIGH (rush shoulders)"
        multiplier = 1.2
    else:
        traffic_intensity = "LOW"
        multiplier = 0.7

    # Wind direction impact (wind_direction is where the wind comes FROM, in degrees)
    if wind_direction is None:
        wind_impact = "Unknown"
        wind_multiplier = 1.0
    elif BQE_TOWARD[0] <= wind_direction <= BQE_TOWARD[1]:
        wind_impact = "Blowing toward Greenpoint"
        wind_multiplier = 1.3
    elif wind_direction >= 260 or wind_direction <= 20:
        wind_impact = "Blowing away"
        wind_multiplier = 0.5
    else:
        wind_impact = "Crosswind"
        wind_multiplier = 1.0

    pollution_pressure = multiplier * wind_multiplier

    return {
        "traffic": traffic_intensity,
        "wind_impact": wind_impact,
        "pollution_pressure": round(pollution_pressure, 1)
    }


def calculate_composite_scores(indoor_pm25, outdoor_pm25, indoor_co2, humidity, dew_point, uv_index, visibility, wind_speed):
    """Calculate health-focused composite scores (1-10 scale)."""

    # ALLERGY RISK (1-10): pollen sensitivity + humidity mold risk + dew point sinus risk
    # Lower is better
    mold_risk = 0
    if humidity > 60:
        mold_risk += 3  # High mold growth risk
    elif humidity < 30:
        mold_risk += 2  # Sinus dryness risk

    sinus_dryness = 0
    if dew_point is not None and dew_point < 5:  # Very dry air
        sinus_dryness = 3
    elif dew_point is not None and dew_point < 10:
        sinus_dryness = 1

    visibility_allergen = 0
    if visibility is not None:
        if visibility < 2000:  # Very low visibility = high particulate/allergen
            visibility_allergen = 4
        elif visibility < 5000:
            visibility_allergen = 2

    allergy_risk = min(10, 2 + mold_risk + sinus_dryness + visibility_allergen)

    # RESPIRATORY LOAD (1-10): PM2.5 + CO2 + visibility + UV
    # Lower is better (1=excellent, 10=hazardous)
    pm_score = min(10, (indoor_pm25 / 15))  # 12 µg/m³ is EPA standard
    co2_score = min(10, (indoor_co2 / 1000))  # 1000 ppm is concerning
    visibility_resp = 0
    if visibility is not None and visibility < 3000:
        visibility_resp = 3

    respiratory_load = round((pm_score + co2_score + visibility_resp) / 3, 1)

    # ACTIVITY SAFETY: composite of all factors + time of day (determined in LLM context)
    # Will be determined by LLM based on hour and all signals

    return {
        "allergy_risk": round(allergy_risk, 1),
        "respiratory_load": round(respiratory_load, 1),
        "mold_risk": "High" if humidity > 60 else "Low" if humidity < 30 else "Ideal",
        "sinus_dryness_risk": "High" if dew_point is not None and dew_point < 5 else "None"
    }


def determine_health_status(indoor_pm25, indoor_co2, indoor_humidity, dew_point, uv_index,
                            visibility, smoke_detected, pollen_data, bqe_prediction, scores):
    """Extensible health status from ALL data sources.

    Each signal returns a severity: 0=GOOD, 1=FAIR, 2=POOR.
    Overall status = worst signal. Add new signals by appending to the list.
    """
    signals = []

    # ── AirGradient sensors ──
    if indoor_pm25 <= 12:
        signals.append(0)
    elif indoor_pm25 <= 35:
        signals.append(1)
    else:
        signals.append(2)

    # The prompt already treats CO2 as fine until 800 ppm.
    if indoor_co2 <= 800:
        signals.append(0)
    elif indoor_co2 <= 1200:
        signals.append(1)
    else:
        signals.append(2)

    # ── Humidity ──
    if 30 <= indoor_humidity <= 50:
        signals.append(0)
    elif 25 <= indoor_humidity <= 60:
        signals.append(1)
    else:
        signals.append(2)

    # ── Dew point (sinus dryness) ──
    # Outdoor dew point matters less when indoor humidity is ideal (30-50%)
    if dew_point is not None:
        if dew_point >= 10:
            signals.append(0)
        elif dew_point >= 5:
            signals.append(1)
        elif 30 <= indoor_humidity <= 50:
            # Indoor air is well-humidified — cap at FAIR, not POOR
            signals.append(1)
        else:
            signals.append(2)

    # ── UV index ──
    if uv_index is not None:
        if uv_index <= 5:
            signals.append(0)
        elif uv_index <= 7:
            signals.append(1)
        else:
            signals.append(2)

    # ── Visibility (particulate proxy) ──
    if visibility is not None:
        if visibility >= 10000:
            signals.append(0)
        elif visibility >= 5000:
            signals.append(1)
        else:
            signals.append(2)

    # ── Wildfire smoke ──
    if smoke_detected:
        signals.append(2)  # Smoke = always POOR

    # ── Pollen (worst allergen drives status) ──
    if pollen_data:
        max_pollen = max((p.get("index", 0) for p in pollen_data), default=0)
        if max_pollen <= 1:
            signals.append(0)
        elif max_pollen <= 3:
            signals.append(1)
        else:
            signals.append(2)

    # Rush hour changes when to go out. It should not mark the air itself poor.
    pressure = bqe_prediction.get("pollution_pressure", 0)
    if pressure <= 0.9:
        signals.append(0)
    else:
        signals.append(1)

    # ── Composite health scores ──
    if scores.get("allergy_risk", 0) <= 3:
        signals.append(0)
    elif scores.get("allergy_risk", 0) <= 6:
        signals.append(1)
    else:
        signals.append(2)

    if scores.get("respiratory_load", 0) <= 3:
        signals.append(0)
    elif scores.get("respiratory_load", 0) <= 6:
        signals.append(1)
    else:
        signals.append(2)

    # Overall = worst signal
    worst = max(signals) if signals else 0
    return ["GOOD", "FAIR", "POOR"][worst]


# ── Air summary (the new page) ──────────────────────────────────────────
# Rules decide each verdict. The model only writes the sentences around them,
# and falls back to the rule sentences when it is missing or breaks a rule.

# Haiku 5.5 thinks by default, and thinking counts toward max_tokens: keep effort low and leave room.
READ_MODEL = "claude-haiku-5-5"
READ_EFFORT = "low"
READ_MODEL_NAME = "Claude Haiku 5.5"
READ_CACHE_SECONDS = 20 * 60

# Peak hours as predict_bqe_traffic() counts them: [start, end).
RUSH_WINDOWS = [(7, 10, "morning"), (16, 20, "evening")]
PM_FINE = 12
PM_HIGH = 35
CO2_OPEN = 800
RH_LOW, RH_HIGH, RH_DAMP = 30, 50, 60
MACHINE_WORDS = re.compile(r"\b(de)?humidifier|purifier|hepa|air conditioner|\bac\b|\bfan\b", re.I)


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


def rush_state(hour):
    for start, end, name in RUSH_WINDOWS:
        if start <= hour < end:
            return {"in_rush": True, "name": name, "start": start, "end": end}
    later = [w for w in RUSH_WINDOWS if w[0] > hour]
    start, end, name = later[0] if later else RUSH_WINDOWS[0]
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
        why = f"Outdoor PM2.5 is {pm} µg/m³, over {PM_FINE}" if outdoor_pm > PM_FINE else "NOAA reports wildfire smoke in the Northeast"
        return verdict("Keep it short", "warn", f"{why}. Keep a run short and easy.")
    base = f"Outdoor PM2.5 is {pm} µg/m³, under {PM_FINE}."
    if rush["in_rush"] and wind_toward:
        return verdict(f"After {fmt_hour(rush['end'])}", "warn",
                       f"{base} The BQE {rush['name']} rush runs until {fmt_hour(rush['end'])} with the wind toward Greenpoint, so run after that.")
    if hour >= 21 or hour < 5:
        return verdict("Fine", "good", f"{base} Tonight is fine, and so is the morning before the {fmt_hour(RUSH_WINDOWS[0][0])} rush.")
    if not rush["in_rush"] and not rush.get("tomorrow") and wind_toward:
        return verdict(f"Fine until {fmt_hour(rush['start'])}", "good",
                       f"{base} Fine for a run, and for the toddler outside, until {fmt_hour(rush['start'])}. Then the BQE rush starts, with the wind toward Greenpoint.")
    return verdict("Fine", "good", f"{base} Fine for a run, and for the toddler outside.")


def forecast_facts(fc, t_in, rh, pm_out, wind_toward):
    """What Coming up will show later, as plain lines for the model's DATA, so its why line can't contradict them.
    Same rules as weatherAgenda() and forecastAgenda() in static/app.js; change both together.
    Returns (lines, best_air_hour)."""
    lines, best = [], None
    if len(fc) < 3:
        return lines, best
    hr = lambda h: int(h["time"][11:13])
    # Best time to air: a damp room, and an hour (not now) when the outdoor dew point is 5 °C or more under the
    # indoor one, skipping BQE rush hours whose wind blows toward Greenpoint (that hour's wind, else the wind now).
    d_in = dew_point_c(t_in, rh)
    if rh is not None and rh > RH_DAMP and d_in is not None:
        dry = lambda h: h["dew"] is not None and d_in - h["dew"] >= 5
        def in_rush(h):
            toward = h["bqe_toward"] if isinstance(h.get("bqe_toward"), bool) else wind_toward
            return toward and any(a <= hr(h) < e for a, e, _ in RUSH_WINDOWS)
        if not dry(fc[0]):
            k = next((n for n in range(1, len(fc)) if dry(fc[n]) and not in_rush(fc[n])), None)
            if k is not None:
                best = hr(fc[k])
                lines.append(f"Later: from {fmt_hour(best)} the outside air gets much drier (best time to air).")
    # Rain or snow starting, or stopping when it's already falling
    wet = lambda h: (h["precip"] or 0) >= 0.2 or (h["pop"] or 0) >= 60
    k = next((n for n in range(1, len(fc)) if wet(fc[n]) != wet(fc[0])), None)
    if k is not None:
        lines.append(f"Later: rain or snow {'stops' if wet(fc[0]) else 'starts'} around {fmt_hour(hr(fc[k]))}.")
    # Outdoor PM2.5 from the air-quality model, read as a change against its own value now (it can be biased)
    p0 = fc[0].get("pm25")
    now_pm = pm_out if pm_out is not None else p0
    if p0 is not None and now_pm is not None:
        if now_pm <= PM_FINE:
            k = next((n for n in range(1, len(fc)) if (fc[n].get("pm25") is not None and fc[n]["pm25"] > PM_FINE
                                                         and fc[n]["pm25"] - p0 >= 5)), None)
            if k is not None:
                lines.append(f"Later: haze from {fmt_hour(hr(fc[k]))}; the outside air gets dirtier.")
        elif p0 > PM_FINE:
            k = next((n for n in range(1, len(fc)) if fc[n].get("pm25") is not None and fc[n]["pm25"] <= PM_FINE), None)
            if k is not None:
                lines.append(f"Later: the outside air clears from {fmt_hour(hr(fc[k]))}.")
    return lines, best


READ_SYSTEM = """You explain an air summary for one household in Greenpoint, Brooklyn: a toddler, sinus and allergy sensitivity, and a runner.
Rules have already decided every action and every verdict. You only write short explanations.

For every sentence:
- Use only numbers that appear in DATA.
- Never give a clock time that has already passed.
- Do not name an appliance (no dehumidifier, humidifier, purifier, fan, HEPA, AC).
- Say why, not what to do; the action is already written.
- Simple everyday English: short sentences and common words a ten-year-old knows. No jargon (no "particulates", "respiratory", "ventilation", "airway", "pathogens").
- No exclamation marks, no emoji. Never mention rules or instructions.
- Do not contradict the LATER facts in DATA; you may mention them.

Output one JSON object and nothing else:
- "why": one sentence, at most 16 words, under the HEADLINE: how the NEEDS fit together today (for example, stale and damp inside, clean but damper outside). No numbers; the cards show them.
- "means": {"co2": string, "humidity": string, "pm": string}, each at most 12 words: what that reading does to people in this home, in simple words. Teach; do not restate the reading."""


def _numbers(text):
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))]


def _allowed(text, data_numbers):
    """True when every number in text appears in DATA (within rounding) or is a small count or hour."""
    for n in _numbers(text):
        if n <= 24 and n == int(n):
            continue
        if not any(abs(n - d) <= 0.51 for d in data_numbers):
            return False
    return True


def _parse_model_json(text):
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    return json.loads(match.group(0)) if match else None


def call_read_model(api_key, data_text):
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={
            "model": READ_MODEL,
            "max_tokens": 4000,
            "output_config": {"effort": READ_EFFORT},
            "system": READ_SYSTEM,
            "messages": [{"role": "user", "content": data_text}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("stop_reason") not in ("end_turn", "stop_sequence"):
        raise ValueError(f"stop_reason {body.get('stop_reason')}")
    text = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
    usage = body.get("usage") or {}
    return _parse_model_json(text), {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}


BANNED = re.compile(r"\b(rules?|instructions?|do not call|never call)\b", re.I)


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


def series_of(points, key, now_local, buckets=48, hours=24):
    start = now_local - timedelta(hours=hours)
    sums, counts = [0.0] * buckets, [0] * buckets
    for ts, row in points:
        v = key(row)
        if v is None:
            continue
        i = int((ts - start).total_seconds() / (hours * 3600) * buckets)
        if 0 <= i < buckets:
            sums[i] += v
            counts[i] += 1
    return [round(t / c, 1) if c else None for t, c in zip(sums, counts)]


def clock_label(ts, now_local):
    label = ts.strftime("%-I:%M %p")
    return label if ts.date() == now_local.date() else label + " yesterday"


def stretch(points, key, is_off, now_local, buckets=48, hours=24):
    """The unbroken stretch where is_off holds, running up to the latest reading."""
    vals = [(t, key(r)) for t, r in points]
    vals = [(t, v) for t, v in vals if v is not None]
    if not vals or not is_off(vals[-1][1]):
        return None
    i = len(vals) - 1
    while i > 0 and is_off(vals[i - 1][1]):
        i -= 1
    start = vals[i][0]
    whole = i == 0 and (start - (now_local - timedelta(hours=hours))).total_seconds() < 3600
    idx = int((start - (now_local - timedelta(hours=hours))).total_seconds() / (hours * 3600) * buckets)
    return {"label": "all day" if whole else "since " + clock_label(start, now_local),
            "cross": None if whole else {"i": max(0, min(buckets - 1, idx)), "t": start.strftime("%-I:%M %p")}}


def co2_of(r):
    return fnum(r.get("rco2_corrected", r.get("rco2")))


def rh_in_of(r):
    return fnum(r.get("rhum", r.get("rhum_corrected")))


def pm_of(r):
    return fnum(r.get("pm02_corrected", r.get("pm02")))


# Pollen seasons in New York, roughly; used only for the "relief" line.
POLLEN_ENDS = {"tree": "early June", "grass": "late July", "weed": "mid-October"}


def relief_line(pollen, now):
    """One factual line about the pollen season, or "" when there is nothing useful to say."""
    if not pollen:
        return ""
    top = max(pollen, key=lambda q: q.get("index") or 0)
    if (top.get("index") or 0) >= 3:
        end = POLLEN_ENDS.get(str(top.get("name", "")).lower())
        return f"{top['name']} pollen usually eases by {end}." if end else ""
    if all((q.get("index") or 0) == 0 and not q.get("in_season") for q in pollen) and now.month in (11, 12, 1, 2):
        return "Pollen is off for the winter. Tree pollen usually starts in March."
    return ""


def headline_needs(key, needs):
    """The needs the headline action serves, so the page can show their icons next to it."""
    serves = {"window": ["toddler", "sinus"], "humidity": ["sinus"], "run": ["runner"], "pollen": ["sinus"]}.get(key)
    if serves is None:
        return []
    # airing the room helps sinuses only when humidity is part of the story
    return [n["id"] for n in needs if n["id"] in serves and (n["id"] != "sinus" or key != "window" or n["tone"] != "good")]


def relief_short(pollen, now):
    """A few words for the pollen row, e.g. "off until March"."""
    line = relief_line(pollen, now)
    if not line:
        return ""
    if "off for the winter" in line:
        return "off until March"
    m = re.search(r"usually eases by (.+)\.$", line)
    return f"eases by {m.group(1)}" if m else ""


def build_needs(co2, rh, pm_out, adds_moisture, pollen, top_pollen, actions, run_item, co2_run, now):
    """One line per need, in the header pill's order: Toddler, Sinus & allergy, Runner.
    Each need is paired with the card that holds its evidence (metric)."""
    keyed = {a["key"]: a for a in actions}
    evening = now.hour >= 17 or now.hour < 7

    # Toddler: the indoor air (CO2), unless the outside air keeps them in.
    if pm_out is not None and pm_out > PM_HIGH:
        tod = ("bad", "Keep the toddler inside", f"Outdoor PM2.5 is {fmt_num(pm_out)}, over {PM_HIGH}.")
    elif co2 is not None and co2 > CO2_OPEN:
        since = co2_run["label"] if co2_run else ""
        tod = ("bad" if co2 > 1500 else "warn", "Air the bedroom before sleep" if evening else "Air the room",
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


def build_air_read(payload, force=False):
    now = local_now()
    co2 = fnum(payload.get("indoor_co2"))
    rh = fnum(payload.get("indoor_humidity"))
    t_in = fnum(payload.get("indoor_temp_c"))
    pm_out = fnum(payload.get("outdoor_pm25"))
    rh_out = fnum(payload.get("outdoor_humidity"))
    t_out = fnum(payload.get("outdoor_temp_c"))

    weather = get_open_meteo_data(HOME_LAT, HOME_LON).get("current", {})
    wind_direction = weather.get("wind_direction_10m")
    bqe = predict_bqe_traffic(now.hour, wind_direction)
    wind_toward = bqe["wind_impact"] == "Blowing toward Greenpoint"
    smoke = get_smoke_data()
    pollen = get_pollen_data(HOME_LAT, HOME_LON)
    rush = rush_state(now.hour)

    in_dp, out_dp = dew_point_c(t_in, rh), dew_point_c(t_out, rh_out)
    if out_dp is None:
        out_dp = fnum(weather.get("dew_point_2m"))
    adds_moisture = in_dp is not None and out_dp is not None and out_dp - in_dp > 1
    # what Coming up will say later (rain, haze, best time to air), so the model's line agrees with it
    later, best_air = forecast_facts(hourly_forecast(get_open_meteo_data(HOME_LAT, HOME_LON), get_air_forecast()),
                                     t_in, rh, pm_out, wind_toward)

    pts_in = history_points(payload.get("indoor_location_id"), now)
    pts_out = history_points(payload.get("outdoor_location_id"), now)

    # ── Cards: the evidence, all from rules ──
    co2_run = stretch(pts_in, co2_of, lambda v: v > CO2_OPEN, now)
    rh_run = stretch(pts_in, rh_in_of, lambda v: v > RH_DAMP or v < RH_LOW, now)
    pm_run = stretch(pts_out, pm_of, lambda v: v > PM_FINE, now)
    pm_series = series_of(pts_out, pm_of, now)

    def card(cid, name, src, value, unit, digits, limit_label, limit, state, tone, fact, series, cross, means):
        return {"id": cid, "name": name, "src": src, "num": None if value is None else (round(value) if digits == 0 else round(value, digits)),
                "unit": unit, "limit_label": limit_label, "limit": limit, "state": state, "tone": tone,
                "fact": fact, "series": series, "cross": cross, "means": means}

    if co2 is None:
        c_state, c_tone, c_fact, c_means = "No reading", "muted", "", ""
    elif co2 > 1500:
        c_state, c_tone, c_fact, c_means = "Very high", "bad", co2_run["label"] if co2_run else "", "Very stale air. It causes headaches and poor sleep."
    elif co2 > CO2_OPEN:
        c_state, c_tone, c_fact, c_means = "High", "warn", co2_run["label"] if co2_run else "", "Stale air makes people tired and sleep worse."
    else:
        c_state, c_tone, c_fact, c_means = "Fresh", "good", f"{CO2_OPEN - co2:.0f} under the limit", "Fresh air. Good for focus and sleep."
    if rh is None:
        h_state, h_tone, h_fact, h_means = "No reading", "muted", "", ""
    elif rh > RH_DAMP:
        h_state, h_tone, h_fact, h_means = "Too damp", "warn", rh_run["label"] if rh_run else "", "Damp air helps mold and dust mites grow."
    elif rh < RH_LOW:
        h_state, h_tone, h_fact, h_means = "Too dry", "warn", rh_run["label"] if rh_run else "", "Dry air makes noses and throats sore."
    elif rh > RH_HIGH:
        h_state, h_tone, h_fact, h_means = "A little damp", "good", f"under the {RH_DAMP} line", "Fine. Most comfortable between 30 and 50%."
    else:
        h_state, h_tone, h_fact, h_means = "Good", "good", "in the 30–50 range", "Good for noses and sleep."
    if pm_out is None:
        p_state, p_tone, p_fact, p_means = "No reading", "muted", "", ""
    elif pm_out > PM_HIGH:
        p_state, p_tone, p_fact, p_means = "Unhealthy", "bad", pm_run["label"] if pm_run else "", "Dirty air. Stay inside."
    elif pm_out > PM_FINE:
        p_state, p_tone, p_fact, p_means = "Moderate", "warn", pm_run["label"] if pm_run else "", "Some people will feel it. Keep runs short."
    else:
        peak = max([v for v in pm_series if v is not None], default=None)
        p_state, p_tone = "Clean", "good"
        p_fact = "under the limit all day" if peak is None or peak <= PM_FINE else "back under the limit"
        p_means = "Clean air. Fine for running and playing outside."
    cards = [
        card("co2", "Room air (CO₂)", "ONE", co2, "ppm", 0, "limit", CO2_OPEN, c_state, c_tone, c_fact,
             series_of(pts_in, co2_of, now), co2_run["cross"] if co2_run and co2 and co2 > CO2_OPEN else None, c_means),
        card("humidity", "Humidity", "ONE", rh, "%", 0, "limit", RH_DAMP, h_state, h_tone, h_fact,
             series_of(pts_in, rh_in_of, now), rh_run["cross"] if rh_run else None, h_means),
        card("pm", "Outside air (PM2.5)", "Open Air", pm_out, "µg/m³", 1, "aim under", PM_FINE, p_state, p_tone, p_fact,
             pm_series, pm_run["cross"] if pm_run else None, p_means),
    ]

    # ── Actions, ranked by the rules ──
    actions = []  # each: {"key", "text", "why", "tone"}
    if co2 is not None and co2 > CO2_OPEN:
        since = co2_run["label"] if co2_run else ""
        if pm_out is not None and pm_out > PM_HIGH:
            actions.append({"key": "window", "tone": "warn", "text": "Keep windows shut for now",
                            "why": f"CO₂ is {co2:.0f}, but the air outside is not clean ({fmt_num(pm_out)})."})
        else:
            short = adds_moisture and rh is not None and rh > RH_DAMP
            actions.append({"key": "window", "tone": "bad" if co2 > 1500 else "warn",
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
        actions.append({"key": "run", "tone": "warn", "text": "Run " + w.lower(), "why": f"The BQE rush runs until {w[6:]}, with the wind toward Greenpoint."})
    elif w.startswith("Fine until"):
        run_item = {"key": "run", "tone": "good", "text": "Run before " + w[11:], "why": f"The air outside is clean; the {w[11:]} rush blows this way."}
    elif w == "Fine":
        night = now.hour >= 21 or now.hour < 5
        run_item = {"key": "run", "tone": "good", "text": f"Run tonight or before {fmt_hour(RUSH_WINDOWS[0][0])}" if night else "Fine to run",
                    "why": "The air outside is clean" + (f"; the {fmt_hour(RUSH_WINDOWS[0][0])} rush blows this way." if night and wind_toward else ".")}
    top_pollen = max(pollen, key=lambda q: q.get("index") or 0) if pollen else None
    if top_pollen and (top_pollen.get("index") or 0) >= 3:
        actions.append({"key": "pollen", "tone": "warn", "text": "Limit time outside", "why": f"{top_pollen['name']} pollen is {top_pollen['index']} of 5."})
    needs = build_needs(co2, rh, pm_out, adds_moisture, pollen, top_pollen, actions, run_item, co2_run, now)
    order = {"window": 0, "humidity": 1, "run": 2, "pollen": 3}
    actions.sort(key=lambda a: ({"bad": 0, "warn": 1}.get(a["tone"], 2), order[a["key"]]))

    if actions:
        head, also = actions[0], actions[1:] + ([run_item] if run_item else [])
        headline, tone, why = head["text"] + ".", head["tone"], head["why"]
    else:
        also = []
        if run_item and run_item["text"].startswith("Run before"):
            headline = f"All good. {run_item['text']}."
            why = f"The air outside is clean, and the BQE {rush['name']} rush starts at {fmt_hour(rush['start'])}."
        elif run_item:
            headline, why = f"All good. {run_item['text']}.", run_item["why"]
        else:
            headline, why = "All good.", "Every reading is inside its limit."
        tone = "good"

    checked = []
    if pollen and all((q.get("index") or 0) == 0 for q in pollen):
        checked.append("No pollen today")
    elif pollen and (top_pollen.get("index") or 0) <= 2:
        checked.append("Pollen is low")
    fresh = [r for r in (pts_in[-1:] + pts_out[-1:]) if (now - r[0]).total_seconds() < 15 * 60]
    if len(fresh) == 2:
        checked.append("Both monitors reporting")
    if co2 is not None and co2 <= CO2_OPEN:
        checked.append("Room is well aired")
    if pm_out is not None and pm_out <= PM_FINE and not any(a["key"] == "run" for a in actions) and not run_item:
        checked.append("Outdoor air is clean")
    ahead = ""
    if not actions and run_item and wind_toward and not rush["in_rush"]:
        st, en = fmt_hour(rush["start"]), fmt_hour(rush["end"])
        ahead = f"{st.split()[0] if st.split()[1] == en.split()[1] else st}–{en}: the BQE rush blows this way."

    result = {
        "generated_at": now.isoformat(), "clock": now.strftime("%-I:%M %p"), "status": tone,
        "headline": {"text": headline, "tone": tone, "key": actions[0]["key"] if actions else "ok", "needs": headline_needs(actions[0]["key"] if actions else None, needs)}, "why": why,
        "also": [{"text": a["text"], "why": a["why"], "tone": a["tone"]} for a in also],
        "checked": checked, "ahead": ahead, "cards": cards,
        "needs": needs, "relief": relief_line(pollen, now), "relief_short": relief_short(pollen, now),
        "source": "rules", "model": None, "model_name": None, "note": None, "replaced": [],
    }

    signature = json.dumps([headline, [n["action"] for n in needs], [c["state"] for c in cards],
                            None if co2 is None else round(co2 / 50), None if rh is None else round(rh / 3), now.hour, best_air])
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        result["note"] = "No API key, so these lines come from the rules."
        return result

    ip = client_ip()
    if force and not force_allowed(ip):
        force = False   # too many Refresh presses: serve the cached advice

    def write_with_model():
        """The model writes the why and means lines; raises with a note when it can't (nothing bad gets cached)."""
        over = ai_allowed(ip)
        if over:
            raise RuntimeError("AI writing is paused for a moment (usage limit), so these lines come from the rules."
                               if over != "day" else "Today's AI limit is reached, so these lines come from the rules.")

        data = [
            f"Clock: {now.strftime('%-I:%M %p')}.",
            f"Indoor CO2: {fmt_num(co2, 0)} ppm (limit {CO2_OPEN}; 1000 feels stuffy; 1500 is above building codes). {c_fact}.",
            f"Indoor humidity: {fmt_num(rh, 0)}% (comfortable 30–50; mold and mites above 60). {h_fact}.",
            f"Outdoor humidity: {fmt_num(rh_out, 0)}%. Airing {'adds' if adds_moisture else 'does not add'} moisture.",
            *([f"Airing now: the outside air holds " + ("more water than" if out_dp - in_dp > 1 else "less water than" if in_dp - out_dp > 1 else "about the same water as")
               + f" inside (dew point {fmt_num(out_dp)} vs {fmt_num(in_dp)} °C)."] if in_dp is not None and out_dp is not None else []),
            f"Outdoor PM2.5: {fmt_num(pm_out)} µg/m³ (aim under {PM_FINE}; {PM_HIGH} is unhealthy). {p_fact}.",
            f"BQE rush hours: 7 to 10 AM and 4 to 8 PM; wind {'toward' if wind_toward else 'not toward'} Greenpoint.",
            *later,
            "",
            f"HEADLINE: {headline} Fact: {why}",
            "NEEDS:",
        ] + [f"- {n['name']}: {n['action']}. Fact: {n['why']}" for n in needs]
        data_text = "DATA\n" + "\n".join(data)
        try:
            out = call_read_model(api_key, data_text)
            if isinstance(out, tuple):
                out, usage = out
            else:
                usage = None
        except Exception as e:  # network, HTTP, JSON: keep the rule lines
            app.logger.warning("read model call failed: %s: %s", type(e).__name__, e)   # the error type goes to the log, not the page
            raise RuntimeError("Claude didn't answer, so these lines come from the rules.") from e
        if not isinstance(out, dict):
            app.logger.warning("read model answer was not JSON")
            raise RuntimeError("Claude didn't answer, so these lines come from the rules.")

        nums = _numbers(data_text)
        def ok(text, max_words):
            return (isinstance(text, str) and text.strip() and len(text.split()) <= max_words + 4 and _allowed(text, nums)
                    and not MACHINE_WORDS.search(text) and not BANNED.search(text))
        replaced = []
        if ok(out.get("why"), 16):
            result["why"] = out["why"].strip()
        else:
            replaced.append("why")
        means = out.get("means") if isinstance(out.get("means"), dict) else {}
        for c in cards:
            if c["num"] is not None and ok(means.get(c["id"]), 10):
                c["means"] = means[c["id"]].strip()
            elif c["num"] is not None:
                replaced.append(c["id"])
        result.update(source="model", model=READ_MODEL, model_name=READ_MODEL_NAME, usage=usage, replaced=replaced)
        return result

    key = "read:" + hashlib.sha1(signature.encode()).hexdigest()
    try:
        value, info = cached(key, write_with_model, ttl=READ_CACHE_SECONDS, force=force, force_floor=10, wait=40)
    except Exception as e:
        result["note"] = str(e) if isinstance(e, RuntimeError) else "Claude didn't answer, so these lines come from the rules."
        return result
    return {**value, "cached": True} if info["state"] != "miss" else value


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Stream LLM analysis of current air quality data with weather context.

    With "format": "read" in the body, returns the new page's air summary as one JSON object instead.
    """
    data = request.json or {}
    if data.get("format") == "read":
        return jsonify(build_air_read(data, force=bool(data.get("force"))))

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 500
    over = ai_allowed(client_ip())
    if over:
        return jsonify({"error": "AI analysis is paused for a moment (usage limit). Try again later."}), 429

    indoor_pm25 = float(data.get('indoor_pm25', 0))
    outdoor_pm25 = float(data.get('outdoor_pm25', 0))
    indoor_co2 = float(data.get('indoor_co2', 0))
    indoor_humidity = float(data.get('indoor_humidity', 50))
    neighbor_rank = int(data.get('neighbor_rank', 1))
    neighbor_count = int(data.get('neighbor_count', 1))

    # Fetch weather context from Open-Meteo (free API, no key needed)
    weather = get_open_meteo_data(HOME_LAT, HOME_LON)
    current = weather.get("current", {})
    wind_speed = current.get("wind_speed_10m")
    wind_direction = current.get("wind_direction_10m")
    visibility = current.get("visibility")
    uv_index = current.get("uv_index")
    dew_point = current.get("dew_point_2m")

    wind_dir = get_wind_cardinal(wind_direction)

    # BQE traffic prediction based on time and wind
    current_hour = local_now().hour
    bqe_prediction = predict_bqe_traffic(current_hour, wind_direction)

    # Check for wildfire smoke (NOAA)
    smoke_detected = get_smoke_data()
    smoke_note = " ⚠️ Wildfire smoke in Northeast region — extra PM2.5 risk" if smoke_detected else ""

    # Fetch pollen data (Google Pollen API)
    pollen_data = get_pollen_data(HOME_LAT, HOME_LON)
    pollen_summary = ""
    if pollen_data:
        pollen_str = ", ".join([f"{p['name']} ({p['level']})" for p in pollen_data])
        pollen_summary = f"POLLEN TODAY: {pollen_str}"
    else:
        pollen_summary = "POLLEN: Data unavailable"

    # Calculate composite health scores
    scores = calculate_composite_scores(indoor_pm25, outdoor_pm25, indoor_co2, indoor_humidity, dew_point, uv_index, visibility, wind_speed)

    # Seasonal allergen triggers (Greenpoint, New York)
    month = local_now().month
    if month in [4, 5]:
        allergen_season = "TREE (birch, maple) pollen peak"
    elif month in [6, 7, 8]:
        allergen_season = "GRASS + MOLD SPORE season"
    elif month in [8, 9, 10]:
        allergen_season = "RAGWEED + MOLD SPORE peak"
    else:
        allergen_season = "Low pollen, mold dormancy period"

    # Determine overall health status from ALL data sources
    status = determine_health_status(
        indoor_pm25, indoor_co2, indoor_humidity, dew_point, uv_index,
        visibility, smoke_detected, pollen_data, bqe_prediction, scores
    )

    # Health context
    humidity_status = "ideal" if 30 <= indoor_humidity <= 50 else "dry" if indoor_humidity < 30 else "humid"
    humidity_risk = "Sinus dryness risk" if indoor_humidity < 30 else "Mold growth risk" if indoor_humidity > 60 else "Clear nasal passages"

    # Dew point sinus impact
    dew_point_status = ""
    if dew_point is not None:
        if dew_point < 5 and not (30 <= indoor_humidity <= 50):
            dew_point_status = "Very dry — sinus dryness risk (indoor humidity not ideal)"
        elif dew_point < 5:
            dew_point_status = "Outdoor air dry, but indoor humidity ideal — sinuses protected"
        elif dew_point < 10:
            dew_point_status = "Mildly dry — monitor if you go outside"
        else:
            dew_point_status = "Comfortable for sinuses"

    # Activity timing recommendation based on BQE rush
    if current_hour >= 7 and current_hour <= 9:
        activity_warning = "AVOID outdoor activity 7-9am (BQE morning rush peak)"
        best_window = "10am-3pm is safest for outdoor activity"
    elif current_hour >= 16 and current_hour <= 19:
        activity_warning = "CAUTION: BQE evening rush (4-7pm) — outdoor exposure risky"
        best_window = "Best outdoor window was 10am-3pm, next safe time is 8pm+"
    else:
        activity_warning = f"BQE traffic moderate at {current_hour}:00"
        best_window = "10am-3pm is still the safest window today"

    prompt = f"""You are a CONSUMER-GRADE health coach helping someone and their spouse manage allergies/sinus sensitivity in Greenpoint, Brooklyn using real-time data.

═══ COMPREHENSIVE DATA INPUT ═══
INDOOR CONDITIONS:
  • PM2.5: {indoor_pm25} µg/m³ (EPA safe: ≤12)
  • CO2: {indoor_co2} ppm (Alert: >800)
  • Humidity: {indoor_humidity}% (Ideal: 30-50%)
  • Dew Point: {dew_point}°C ({dew_point_status if dew_point_status else 'calculating...'})

OUTDOOR CONDITIONS:
  • PM2.5: {outdoor_pm25} µg/m³
  • Wind: {wind_speed} km/h from {wind_dir} ({bqe_prediction['wind_impact']})
  • Visibility: {visibility}m (Low=high particulate)
  • UV Index: {uv_index}
  {smoke_note}

POLLEN DATA (Real-time from Google):
  • {pollen_summary}

LOCAL CONTEXT:
  • Clock: {local_now().strftime("%-I:%M %p")} local. Windows already past this clock are not available.
  • Greenpoint Rank: {neighbor_rank}/{neighbor_count} cleanest (lower is better)
  • Seasonal: {allergen_season}
  • BQE Traffic: {bqe_prediction['traffic']} (Pollution Pressure: {bqe_prediction['pollution_pressure']}x)
  • Activity: {activity_warning}

HEALTH SCORES:
  • Allergy Risk: {scores['allergy_risk']}/10 ({scores['mold_risk']} mold risk)
  • Respiratory Load: {scores['respiratory_load']}/10
  • Sinus Risk: {scores['sinus_dryness_risk']} sinus dryness

═══ STRICT BREVITY RULES ═══
• status_line: one or two sentences, MAX 4 words each. Sentence 1 is the day. Sentence 2 only when one thing needs attention, and it names that thing. No numbers.
• metric benefit: MAX 8 words. What to do or how it feels, not a restatement of the value.
• working items: MAX 12 words each. Exactly 3 facts that are already comfortable or clean. Never an instruction, never a warning, never an invented ratio.
• next_steps: MAX 16 words each. Exactly 3 instructions. The first is the single action still available after the Clock above, and it starts with when. Never name a clock time that has already passed. The other two are backups.
• insight: MAX 16 words. One sentence about the Seasonal line above, including when it changes. Do not mention a month the Seasonal line does not support.
• Every string below is a shape sample. Rewrite it from the data. Do not copy a sample.
• NEVER add text outside the JSON object. Output ONLY the JSON.
• Write like a fitness app notification, not a medical report.

═══ TONE RULES ═══
• Use the status value "{status}" exactly — do NOT override it.
• GOOD = reassuring, positive ("Sinuses clear, great day to be outside")
• FAIR = balanced, watchful ("Conditions decent, keep an eye on X")
• POOR = urgent, actionable ("Take action now: X is affecting your health")
• If indoor humidity is 30-50% (ideal), do NOT call dew point "critically dry" — indoor air is compensating.

═══ CONTENT PRIORITIES ═══
1. Symptom-first language ("Clear sinuses" not "PM2.5 is 10")
2. Activity timing for runner + toddler outdoor time
3. Dryness/humidity warnings (sinus-critical)
4. BQE traffic + wind pollution timing
5. Pollen alerts if any type is Moderate+
6. Seasonal context (relief date)

═══ JSON OUTPUT (ONLY JSON, NO MARKDOWN, NO EXTRA TEXT) ═══
{{
  "status": "{status}",
  "status_line": "Clear today. Watch the evening rush.",
  "rank": "{neighbor_rank}/{neighbor_count}",
  "metrics": [
    {{"icon": "🫁", "category": "Air Quality (Indoor)", "status": "Excellent", "value": "{indoor_pm25} µg/m³ indoor · {outdoor_pm25} outdoor", "benefit": "Filtering 70% of street dust"}},
    {{"icon": "💧", "category": "Humidity (Indoor)", "status": "{humidity_status.upper()}", "value": "{indoor_humidity}%", "benefit": "Nasal passages clear, no dryness"}},
    {{"icon": "🌬️", "category": "Ventilation (Indoor)", "status": "Healthy", "value": "{indoor_co2} ppm CO2", "benefit": "Sharp focus, no brain fog"}}
  ],
  "working": [
    "Indoor air is cleaner than the street",
    "Humidity is holding sinuses comfortable",
    "No wildfire smoke in the region"
  ],
  "next_steps": [
    "After the rush, open one window for ten minutes",
    "Skip the outdoor run until the traffic eases",
    "Check humidity again before bed"
  ],
  "insight": "Follow the Seasonal line, and say when that season turns"
}}"""

    def stream():
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": READ_MODEL,
                "max_tokens": 4000,
                "output_config": {"effort": READ_EFFORT},
                "stream": True,
                "messages": [{"role": "user", "content": prompt}],
            },
            stream=True,
            timeout=30,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                    if event.get("type") == "content_block_delta":
                        text = event["delta"].get("text", "")
                        if text:
                            yield f"data: {json.dumps({'text': text})}\n\n"
                    elif event.get("type") == "message_stop":
                        break
                except json.JSONDecodeError:
                    pass
        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠  ANTHROPIC_API_KEY not set — LLM analysis disabled")
        print("   Run: ANTHROPIC_API_KEY=sk-... python server.py")
    port = int(os.environ.get("PORT", 5555))
    print(f"AirGradient Dashboard → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
