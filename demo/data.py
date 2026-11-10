"""Made-up readings for the demo, in the shapes the real sources answer in: AirGradient (both monitors, their week of
history, the public monitors nearby), Open-Meteo (weather and the PM2.5 model), Google Pollen and NOAA smoke.

Everything is generated from the moment's story numbers (demo/moments.py) and seeded by its key, so every request for a
moment gets the same answer. install() puts the generators in place of server.py's fetchers: the routes and the rules
run unchanged, and nothing leaves the machine.

Each reading is a curve through knots (a usual day's shape, jittered day to day, with the moment's own story laid over
it), plus a little noise that fades to nothing at the moment, so the latest reading is exactly the story's number.
"""
import bisect
import json
import math
import random
import re
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from time import monotonic

import requests

import publicmap
from config import route_path
from summary import corrected_pm

from . import public
from .moments import MOMENTS, SAMPLES, SOURCE_MONITOR_ID, TZ, data_key, moment_for

STEP = timedelta(minutes=5)
WEEK = timedelta(days=7)
INDOOR_ID, OUTDOOR_ID = 4201, 4202
POLLEN_TYPES = ("Tree", "Grass", "Weed")
LEVELS = ("None", "Very Low", "Low", "Moderate", "High", "Very High")

# Public monitors around the home: made up, placed in real neighborhoods so the map reads.
NEARBY = (
    (5101, "Greenpoint", 40.7296, -73.9542), (5102, "North Williamsburg", 40.7206, -73.9585),
    (5103, "South Williamsburg", 40.7088, -73.9602), (5104, "Broadway Triangle", 40.7025, -73.9475),
    (5105, "East Williamsburg", 40.7142, -73.9348), (5106, "Meeker Avenue", 40.7170, -73.9445),
    (5107, "Grand Street", 40.7115, -73.9535), (5108, "Newtown Creek", 40.7290, -73.9330),
    (5109, "Bushwick", 40.6990, -73.9220), (5110, "Long Island City", 40.7440, -73.9480),
    (5111, "Lower East Side", 40.7150, -73.9850), (5112, "Ridgewood", 40.7060, -73.9050),
)

# indoor-near's public monitor (?moment=indoor-near): made up, about 1.1 km northeast of the demo's home; its owner too
SOURCE_PLACE = {"publicLocationName": "Larkspur Yard", "publicPlaceName": "Quill Street",
                "publicContributorName": "Demo Neighbor", "latitude": 40.7275, "longitude": -73.9415}
SOURCE_FIELDS = ("pm02_corrected", "rhum", "atmp", "rco2")   # what AirGradient's map gives in a monitor's history
RAW_PM_MAX = 1000.0   # µg/m³ raw pm02: the bisection's upper bound, far above any story's PM2.5 once corrected
RAW_PM_STEPS = 60   # bisection steps finding the raw pm02 whose EPA correction is the story's PM2.5 (far below 0.01)

_HOME = {}   # the demo config's place and road, set by install()
# how far past a History range a request's start may reach and still get that range: the route builds from = now − h,
# then the range is picked a moment later (a slow request, a page's clock a little off)
RANGE_SLACK = timedelta(minutes=2)


# ── curves ──

def _hour(m, h):
    """Hour h of the moment's day (25 is 1 AM the next day) as an aware datetime."""
    day = datetime(m.at.year, m.at.month, m.at.day, tzinfo=TZ)
    return (day + timedelta(hours=h)).astimezone(TZ)


def _hours_of(m, t):
    return (t - _hour(m, 0)).total_seconds() / 3600


class Curve:
    """Values through (time, value) knots, eased between them (cosine), flat past the ends."""
    def __init__(self, knots):
        knots = sorted(knots)
        self.xs = [t.timestamp() for t, _ in knots]
        self.vs = [v for _, v in knots]

    def __call__(self, t):
        x, xs, vs = t.timestamp(), self.xs, self.vs
        i = bisect.bisect_right(xs, x)
        if i == 0:
            return vs[0]
        if i == len(xs):
            return vs[-1]
        f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
        return vs[i - 1] + (vs[i] - vs[i - 1]) * (1 - math.cos(math.pi * f)) / 2


def _days(m):
    """The days the curves cover: the week of history before the moment, and the forecast's day after."""
    first = (m.at - WEEK).date() - timedelta(days=2)
    return [first + timedelta(days=k) for k in range((m.at.date() - first).days + 3)]


def _usual(m):
    """Each signal's usual day, day by day, jittered; the moment's own day keeps the story's levels exactly."""
    knots = {s: [] for s in ("co2", "rh_in", "t_in", "t_out", "rh_out", "pm_out")}
    days = _days(m)
    rngs = {d: random.Random(f"{m.key}:{d.isoformat()}") for d in days}
    story_day = m.at.date()
    peak = {d: m.co2_night if d == story_day else m.co2_night * rngs[d].uniform(.85, 1.0) for d in days}
    peak[days[-1] + timedelta(days=1)] = m.co2_night * .95
    for d in days:
        r, exact = rngs[d], d == story_day
        jit = (lambda a, b: 0) if exact else r.uniform
        at = lambda h: datetime(d.year, d.month, d.day, tzinfo=TZ) + timedelta(hours=h)
        nxt = peak[d + timedelta(days=1)]
        lo_day, p = m.co2_day * (1 + jit(-.04, .04)), peak[d]
        knots["co2"] += [(at(0), lo_day + (p - lo_day) * .72), (at(3), lo_day + (p - lo_day) * .9), (at(5.5), p),
                         (at(7.2), lo_day + (p - lo_day) * .85), (at(9), lo_day + 90), (at(11), lo_day),
                         (at(16.5), lo_day + 10), (at(19.5), lo_day + (nxt - lo_day) * .12),
                         (at(22), lo_day + (nxt - lo_day) * .38)]
        dd, nn = m.rh_in_day + jit(-1.5, 1.5), m.rh_in_night + jit(-1.5, 1.5)
        knots["rh_in"] += [(at(0), dd + (nn - dd) * .5), (at(6.5), nn), (at(9.5), dd + 1), (at(14), dd),
                           (at(19), dd + .5), (at(22.5), dd + (nn - dd) * .3)]
        ti = m.t_in + jit(-.3, .3)
        knots["t_in"] += [(at(0), ti - .3), (at(6), ti - .8), (at(10), ti), (at(17), ti + .6), (at(21), ti + .2)]
        lo, hi = m.t_range[0] + jit(-1.2, 1.2), m.t_range[1] + jit(-1.2, 1.2)
        knots["t_out"] += [(at(0), lo + (hi - lo) * .3), (at(6), lo), (at(15), hi), (at(20), lo + (hi - lo) * .55)]
        dry, wet = m.rh_out_range[0] + jit(-4, 4), min(99, m.rh_out_range[1] + jit(-4, 4))
        knots["rh_out"] += [(at(0), wet - 4), (at(6), wet), (at(15), dry), (at(20), (dry + wet) / 2)]
        base = m.pm_base * (1 + jit(-.15, .15))
        room = max(0.0, m.pm_rush_max - base)
        weekday = d.weekday() < 5
        am, pm = room * r.uniform(.3, 1) * (1 if weekday else .3), room * r.uniform(.2, .8) * (1 if weekday else .3)
        knots["pm_out"] += [(at(0), base), (at(5), base * .95), (at(8.5), base + am), (at(11), base + 1),
                            (at(15), base), (at(18), base + pm), (at(21), base + .5)]
    return knots


@lru_cache(maxsize=8)
def world(key):
    """Every curve of one moment, its story laid over the usual days, ending exactly on the story's readings."""
    m = MOMENTS[key]
    knots = _usual(m)
    now_h = _hours_of(m, m.at)
    story = {s: list(m.story.get(s, ())) for s in knots}
    finals = {"co2": m.co2, "rh_in": m.rh_in, "t_in": m.t_in, "t_out": m.t_out, "rh_out": m.rh_out, "pm_out": m.pm_out}
    curves = {}
    for s, ks in knots.items():
        pts = [(h, v) for h, v in story[s] if abs(h - now_h) > 1e-6] + [(now_h, finals[s])]
        a, b = _hour(m, min(h for h, _ in pts)), _hour(m, max(h for h, _ in pts))
        curves[s] = Curve([(t, v) for t, v in ks if not a <= t <= b] + [(_hour(m, h), v) for h, v in pts])
    return m, curves


def _noise(key, signal, n, sd, keep=.85):
    """Smooth made-up wiggle (an AR(1) series), the same for every request."""
    r, e, out = random.Random(f"{key}:{signal}:noise"), 0.0, []
    for _ in range(n):
        e = keep * e + r.gauss(0, sd)
        out.append(e)
    return out


def _z(t):
    """AirGradient's timestamps: UTC, with milliseconds and a Z."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


@lru_cache(maxsize=8)
def history(key):
    """A week of 5-minute readings for both monitors, ending at the moment: ([indoor rows], [outdoor rows])."""
    m, c = world(key)
    n = int(WEEK / STEP) + 1
    times = [m.at - STEP * (n - 1 - i) for i in range(n)]
    nz = {s: _noise(key, s, n, sd) for s, sd in
          (("co2", 9), ("rh_in", .25), ("t_in", .04), ("pm_in", .12), ("voc", 3), ("t_out", .08), ("rh_out", .5),
           ("pm_out", .5), ("co2_out", 1.5))}
    indoor, outdoor = [], []
    for i, t in enumerate(times):
        fade = 1 - math.exp(-(m.at - t).total_seconds() / 1800)   # no noise at the moment itself
        w = lambda s: nz[s][i] * fade
        pm_o = max(0.5, c["pm_out"](t) + w("pm_out") * max(1, c["pm_out"](t) / 10))
        h = t.astimezone(TZ).hour + t.astimezone(TZ).minute / 60
        voc = m.voc + 18 * (math.sin(2 * math.pi * (h - 13) / 24) - math.sin(2 * math.pi * (_hours_of(m, m.at) - 13) / 24)) * fade
        indoor.append({"timestamp": _z(t), "pm02": round(max(.3, m.pm_in + .15 * (c["pm_out"](t) - m.pm_out) + w("pm_in")), 1),
                       "rco2": round(c["co2"](t) + w("co2")), "rhum": round(c["rh_in"](t) + w("rh_in"), 1),
                       "atmp": round(c["t_in"](t) + w("t_in"), 1), "tvocIndex": round(voc + w("voc")), "noxIndex": 1})
        t_o, rh_o = c["t_out"](t) + w("t_out"), min(99.0, c["rh_out"](t) + w("rh_out"))
        outdoor.append({"timestamp": _z(t), "pm02": round(pm_o * 1.18, 1), "pm02_corrected": round(pm_o, 1),
                        "rco2": round(421 + 6 * math.sin(2 * math.pi * h / 24) * fade + w("co2_out")),
                        "rhum": round(rh_o - 3, 1), "rhum_corrected": round(rh_o, 1),
                        "atmp": round(t_o + .6, 1), "atmp_corrected": round(t_o, 1)})
    return indoor, outdoor


def current(key):
    """/locations/measures/current: both monitors, their latest reading with everything the page shows."""
    m, _ = world(key)
    ind, out = (dict(rows[-1]) for rows in history(key))
    ind.update(locationId=INDOOR_ID, locationName=_HOME["indoor"], locationType="indoor", serialno="demo-one",
               model="I-9PSL", firmwareVersion="3.3.9", pm01=round(ind["pm02"] * .7, 1), pm10=round(ind["pm02"] * 1.2, 1),
               pm003Count=round(ind["pm02"] * 55 + 120), tvoc=round(ind["tvocIndex"] * 1.6), wifi=-52)
    pm = out["pm02_corrected"]
    out.update(locationId=OUTDOOR_ID, locationName=_HOME["outdoor"], locationType="outdoor", serialno="demo-openair",
               model="O-1PST", firmwareVersion="3.3.9", pm01=round(pm * .66, 1), pm10=round(pm * 1.28, 1),
               pm10_corrected=round(pm * 1.22, 1), pm003Count=round(pm * 62 + 180), tvocIndex=round(96 + pm),
               noxIndex=round(1 + 1.1 * pm), wifi=-67)
    return [ind, out]


def past(key, location_id, params=None):
    """/locations/{id}/measures/past: the readings between from and to (the last day without them)."""
    m, _ = world(key)
    rows = history(key)[0 if int(location_id) == INDOOR_ID else 1] if int(location_id) in (INDOOR_ID, OUTDOOR_ID) else []
    p = params or {}
    iso = lambda s: datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    try:
        frm = iso(p["from"]) if p.get("from") else m.at - timedelta(days=1)
        to = iso(p["to"]) if p.get("to") else m.at
    except ValueError:
        raise RuntimeError("AirGradient API returned 400: bad from/to")
    return [dict(r) for r in rows if frm <= iso(r["timestamp"]) <= to]


def history_points(key, location_id, now_local, hours=24):
    """server.history_points: the last `hours` of one monitor as (local time, row), oldest first."""
    if not location_id:
        return []
    rows = past(key, location_id, {"from": _z(now_local - timedelta(hours=hours)), "to": _z(now_local)})
    return [(datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).astimezone(now_local.tzinfo), r) for r in rows]


# ── indoor-near's public monitor ──

def _raw_pm(pm, rh):
    """The raw pm02 that AirGradient's EPA correction (summary.corrected_pm) turns into `pm` at humidity `rh`."""
    lo, hi = 0.0, RAW_PM_MAX
    for _ in range(RAW_PM_STEPS):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if (corrected_pm(mid, rh) or 0) < pm else (lo, mid)
    return round(hi, 2)


def source_row(key):
    """The public monitor as AirGradient's world list gives it: the balcony monitor's reading now (the story's), with
    the raw pm02 its correction reads back as the story's PM2.5."""
    m, _ = world(key)
    out = history(key)[1][-1]
    return {"locationId": SOURCE_MONITOR_ID, "locationName": SOURCE_PLACE["publicLocationName"], "locationType": "outdoor",
            **SOURCE_PLACE, "publicPlaceUrl": None, "pm02": _raw_pm(m.pm_out, out["rhum"]), "rhum": out["rhum"],
            "atmp": out["atmp"], "rco2": out["rco2"], "timestamp": _z(m.at), "offline": False}


def source_past(key, frm, to):
    """The public monitor's history between frm and to (aware datetimes), as AirGradient's map gives it: the balcony
    monitor's readings, in the map's fields."""
    rows = past(key, OUTDOOR_ID, {"from": _z(frm), "to": _z(to)})
    return [{"timestamp": r["timestamp"], **{k: r[k] for k in SOURCE_FIELDS if k in r}} for r in rows]


# ── weather, the PM2.5 model, pollen, smoke, nearby ──

def _dew(t, rh):
    g = math.log(max(rh, 1) / 100) + 17.62 * t / (243.12 + t)
    return round(243.12 * g / (17.62 - g), 1)


def _sun(m, day_index):
    rise, set_ = m.sun[day_index]
    f = lambda s: int(s[:2]) + int(s[3:]) / 60
    return f(rise), f(set_)


def _raining(m, h):
    return m.rain is not None and m.rain[0] <= h < m.rain[1]


@lru_cache(maxsize=8)
def weather(key):
    """Open-Meteo's forecast answer: current, 4 hours back and 24 ahead by hour, today's and tomorrow's sun."""
    m, c = world(key)
    now = m.at.replace(minute=0)
    hours = [now + timedelta(hours=k) for k in range(-4, 24)]
    hh = [_hours_of(m, t) for t in hours]
    def uv(h):
        rise, set_ = _sun(m, 0 if h < 24 else 1)
        x = h % 24
        if not rise < x < set_:
            return 0.0
        v = m.uv_max * math.sin(math.pi * (x - rise) / (set_ - rise)) ** 1.6
        return round(v * (.3 if _raining(m, h) else 1), 1)
    wind = lambda h: round((m.wind_dir + 9 * math.sin(h / 1.2)) % 360)
    speed = lambda h: round(m.wind_speed * (1 + .25 * math.sin(math.pi * (h - 9) / 12)), 1)
    rain_mm = lambda h: round(.5 + 1.5 * math.sin(math.pi * (h - m.rain[0]) / (m.rain[1] - m.rain[0])), 1) if _raining(m, h) else 0.0
    code = lambda h: (63 if rain_mm(h) >= 1 else 61) if _raining(m, h) else m.weather_code if not m.rain else 3
    temp = lambda t: round(c["t_out"](t), 1)
    rh = lambda t: round(c["rh_out"](t))
    days = [m.at.date(), m.at.date() + timedelta(days=1)]
    return {
        "latitude": _HOME["lat"], "longitude": _HOME["lon"], "timezone": "America/New_York",
        "current": {"time": m.at.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": m.t_out, "relative_humidity_2m": m.rh_out,
                    "dew_point_2m": _dew(m.t_out, m.rh_out), "weather_code": m.weather_code,
                    "wind_speed_10m": m.wind_speed, "wind_direction_10m": m.wind_dir, "visibility": m.visibility,
                    "uv_index": uv(_hours_of(m, m.at)), "cloud_cover": m.cloud},
        "hourly": {
            "time": [t.strftime("%Y-%m-%dT%H:00") for t in hours],
            "temperature_2m": [temp(t) for t in hours],
            "dew_point_2m": [_dew(temp(t), rh(t)) for t in hours],
            "precipitation_probability": [90 if _raining(m, h) else 5 + round(5 * math.sin(h)) for h in hh],
            "precipitation": [rain_mm(h) for h in hh],
            "weather_code": [code(h) for h in hh],
            "uv_index": [uv(h) for h in hh],
            "wind_direction_10m": [wind(h) for h in hh],
            "wind_speed_10m": [speed(h) for h in hh],
        },
        "daily": {"time": [d.isoformat() for d in days],
                  "sunrise": [f"{d.isoformat()}T{m.sun[i][0]}" for i, d in enumerate(days)],
                  "sunset": [f"{d.isoformat()}T{m.sun[i][1]}" for i, d in enumerate(days)]},
    }


@lru_cache(maxsize=8)
def air_forecast(key):
    """Open-Meteo's PM2.5 model by local hour, the past day and the day ahead. The past hours are the balcony monitor's
    own hourly means, so the server's calibration keeps the forecast at the story's level (factor 1)."""
    m, c = world(key)
    now = m.at.replace(minute=0)
    out = {}
    sums = {}
    for r in history(key)[1]:
        t = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).astimezone(TZ)
        if t > now - timedelta(hours=24):
            sums.setdefault(t.replace(minute=0, second=0).strftime("%Y-%m-%dT%H:00"), []).append(r["pm02_corrected"])
    for k in range(-23, 25):
        t = now + timedelta(hours=k)
        key_t = t.strftime("%Y-%m-%dT%H:00")
        out[key_t] = round(sum(sums[key_t]) / len(sums[key_t]), 2) if k <= 0 and key_t in sums else round(c["pm_out"](t), 1)
    return out


def pollen_days(key):
    m = moment_for(key)
    day = lambda idx: [{"name": n, "level": LEVELS[i], "index": i, "in_season": s}
                       for n, i, s in zip(POLLEN_TYPES, idx, m.pollen_in_season)]
    return {"today": day(m.pollen_today), "tomorrow": day(m.pollen_tomorrow)}


def smoke(key):
    m = moment_for(key)
    return {"checked": True, "detected": False, "density": None, "date": m.at.strftime("%Y-%m-%d")}


@lru_cache(maxsize=1)
def _route():
    try:
        return json.loads(route_path(_HOME["route"]).read_text(encoding="utf-8")) if _HOME.get("route") else []
    except (OSError, ValueError):
        return []


def _km(lat1, lon1, lat2, lon2):
    return math.hypot((lon2 - lon1) * 111.32 * math.cos(math.radians(lat1)), (lat2 - lat1) * 111.32)


@lru_cache(maxsize=8)
def nearby(key):
    """The public monitors around home, nearest first, the balcony monitor among them. In the rush the ones beside
    the BQE read highest."""
    m, _ = world(key)
    r = random.Random(f"{key}:nearby")
    lat, lon = _HOME["lat"], _HOME["lon"]
    far = m.pm_base * .95
    out = [{"locationId": OUTDOOR_ID, "locationName": _HOME["outdoor"], "latitude": lat, "longitude": lon,
            "pm02": m.pm_out, "atmp": m.t_out, "rhum": m.rh_out, "timestamp": _z(m.at), "distance_km": 0.0}]
    for lid, name, a, b in NEARBY:
        to_road = min((_km(a, b, y, x) for x, y in _route()), default=5)
        pm = far + m.nearby_road * math.exp(-to_road / .45) + r.uniform(-.7, .7)
        out.append({"locationId": lid, "locationName": f"Demo monitor · {name}", "latitude": a, "longitude": b,
                    "pm02": round(max(.5, pm), 1), "atmp": round(m.t_out + r.uniform(-.6, .6), 1),
                    "rhum": round(min(99, m.rh_out + r.uniform(-3, 3))), "timestamp": _z(m.at - timedelta(minutes=r.randint(1, 9))),
                    "distance_km": round(_km(lat, lon, a, b), 1)})
    return sorted(out, key=lambda n: n["distance_km"])


# ── into the server ──

class _Inline:
    """An executor that runs the work at once, in the request's own thread (so the work can read ?moment=)."""
    def submit(self, fn, *args, **kwargs):
        fut = Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except Exception as e:  # the caller's result() raises it, as with a pool
            fut.set_exception(e)
        return fut


def install(server, moment_for_request):
    """Replace every outside source in server.py with the generators above. moment_for_request() gives the Moment
    the current request asked for (?moment=, or the default).

    With ?monitor=<id> (server.request_monitor()) and that id an outdoor monitor of AirGradient's public map, the
    request is about that monitor instead: the real fetchers at its place, through the real cache under keys that
    carry its id (MONITOR_TTL), its history from AirGradient's public map when the map has it (monitor_history), no
    pollen, no road, the runner's profile only (its view's), and its reading counts only while it's online and recent
    (server.outdoor_row). An id that can't be shown (unknown, or the map didn't answer) gets the default sample's
    made-up answers, which no one caches, and the page says why (window.APP.public.error).

    The monitor wiring reads the request (?monitor=, flask.g), so every replaced function must run in the request's
    thread: the demo's _CONTEXT_POOL runs inline, and the real cache only ever runs the real fetchers in its pool."""
    sources, air_read = server.sources, server.air_read
    cfg = server.CFG
    _HOME.update(lat=cfg.place.lat, lon=cfg.place.lon, indoor=cfg.place.indoor, outdoor=cfg.place.outdoor,
                 route=cfg.road.route if cfg.road else None)
    _route.cache_clear()
    nearby.cache_clear()
    key = lambda: data_key(moment_for_request())   # whose made-up readings: a hidden case shows the rush's
    # the real ones, before they're replaced: a public monitor uses them
    _REAL.clear()
    _REAL.update({name: getattr(sources, name) for name in (
        "cached", "_fetch_world", "_fetch_nearby", "get_open_meteo_data", "get_air_forecast", "smoke_status",
        "local_now", "source_on", "outdoor_source")},
        road_traffic=air_read.road_traffic, page_view=server.page_view, indoor_monitor=air_read.indoor_monitor,
        force=sources._force, world_cache=sources.WORLD_CACHE)
    real = _REAL
    request_monitor = server.request_monitor
    ranges = sorted(sources.HIST_TTL)   # the History card's ranges (h): a monitor's history is fetched and cached by them

    def monitor():
        """The public monitor this request is about, or None (no ?monitor=, or one that can't be shown)."""
        return _resolve(request_monitor())[0]

    def asked():
        """"sample" (no ?monitor=), "monitor" (one to show) or "missing" (asked for, can't be shown)."""
        if request_monitor() is None:
            return "sample"
        return "monitor" if monitor() else "missing"

    def which():
        """Where this request's data comes from: "monitor" (one to show) or "sample". A monitor that can't be shown gets
        the default sample (made-up data), so its page is the sample's, with the reason in the banner."""
        return "monitor" if asked() == "monitor" else "sample"

    def here():
        return public.here_of(monitor())

    def sample():
        """The sample's moment, or None for a public monitor's page. A hidden case's moment says which monitors the
        home has (indoor, outdoor_from), as a config's place and [sources] outdoor_from would."""
        return moment_for_request() if which() == "sample" else None

    def outdoor_from():
        """server.outdoor_from: a hidden indoor-only case's source; None for the samples and a public monitor."""
        m = sample()
        return m.outdoor_from if m else None

    def own_rows(rows):
        """The home's own monitors (server.place_rows for the demo): an indoor-only case has no balcony monitor, an
        outdoor-only one no bedroom monitor."""
        m = sample()
        drop = {"outdoor"} if m and m.outdoor_from is not None else {"indoor"} if m and not m.indoor else set()
        return [r for r in rows if r["locationType"] not in drop]

    def api_get(path, params=None):
        w = which()
        if path == "/locations/measures/current":
            return public.current_rows(monitor()) if w == "monitor" else own_rows(current(key()))
        hit = re.fullmatch(r"/locations/(\d+)/measures/past", path)
        if hit:   # a public monitor's comes from AirGradient's public map (the API shares it only with its owner)
            if w == "sample":
                return past(key(), hit.group(1), params)
            return monitor_past(monitor(), hit.group(1), params, ranges)
        raise RuntimeError(f"AirGradient API returned 404: no demo data for {path}")

    def source_on(name):
        if which() == "monitor":
            return public.view_of(monitor(), server.APP_VIEW)["sources"].get(name) is not False
        return real["source_on"](name)

    def smoke_status(*a, **k):
        w = which()
        if w == "sample":
            return smoke(key())
        return real["smoke_status"](here()) if source_on("smoke") else sources.no_smoke()

    def weather_now(*a, **k):
        w = which()
        return weather(key()) if w == "sample" else real["get_open_meteo_data"](here())

    def air_model(*a, **k):
        w = which()
        return dict(air_forecast(key())) if w == "sample" else real["get_air_forecast"](here())

    def nearby_of(world, *a, **k):
        w = which()
        if w != "sample":
            return real["_fetch_nearby"](world, here())
        rows = [dict(n) for n in nearby(key())]
        if outdoor_from() is None:
            return rows
        # an indoor-only case: no balcony monitor among them; indoor-near's public monitor is, at its place
        rows = [n for n in rows if n["locationId"] != OUTDOOR_ID]
        if isinstance(outdoor_from(), int):
            row = source_row(key())
            pm = corrected_pm(row["pm02"], row["rhum"])
            rows.append({**row, "distance_km": round(_km(_HOME["lat"], _HOME["lon"], row["latitude"], row["longitude"]), 1),
                         **({"pm02_corrected": pm} if pm is not None else {})})
        return sorted(rows, key=lambda n: n["distance_km"])

    def outdoor_source(now=None, with_history=True):
        """server.outdoor_source: indoor-near's public monitor, made up (its reading, and its last day of history),
        through server.py's own shapes; anything else (the model, a sample with the balcony, a public monitor's page)
        is server.py's."""
        of = outdoor_from()
        if not isinstance(of, int):
            return real["outdoor_source"](now, with_history)
        row = source_row(key())
        at = moment_for_request().at
        rows = source_past(key(), at - timedelta(hours=sources.SOURCE_HOURS), at) if with_history else []
        return sources._source("monitor", **sources._monitor_facts(row), row=publicmap.reading_row(row), history=rows)

    def source_history_rows(location_id, frm, to):
        """server.source_history_rows: indoor-near's public monitor's rows between frm and to; [] for another id."""
        return source_past(key(), frm, to) if location_id == SOURCE_MONITOR_ID == outdoor_from() else []

    def indoor_monitor():
        m = sample()
        return m.indoor if m else real["indoor_monitor"]()

    def now(*a, **k):
        w = which()
        return moment_for_request().at if w == "sample" else real["local_now"](here())

    def cached(cache_key, fetch, **kw):
        """A public monitor's own keys (they end in its id) go through the real cache, fresh for MONITOR_TTL; the keys
        every monitor shares (public.SHARED_KEYS: NOAA's smoke polygons) keep their own ttl. Each waits MONITOR_WAIT at
        most, within the request's budget. Every other answer is computed per request (a sample's keys don't know the
        moment)."""
        mon = monitor()
        wait = min(kw.get("wait", public.MONITOR_WAIT), public.MONITOR_WAIT)
        if mon and cache_key in public.SHARED_KEYS:
            return real_cached(cache_key, fetch, **{**kw, "wait": wait})
        if mon and cache_key.endswith(":" + public.here_of(mon).key):
            return real_cached(cache_key, fetch, **{**kw, "ttl": public.MONITOR_TTL, "wait": wait})
        return fetch(), {"state": "hit", "age": 0}

    def page_view():
        mid = request_monitor()
        if mid is None:
            view, m = real["page_view"](), moment_for_request()
            if m.indoor and m.outdoor_from is None:
                return view
            # a hidden one-monitor case: its place without the monitor it lacks, and its source (config.public_view)
            of = m.outdoor_from
            place = {**view["place"], **({"outdoor": None} if of is not None else {}), **({} if m.indoor else {"indoor": None})}
            return {**view, "place": place,
                    **({"outdoor_from": {"kind": of if isinstance(of, str) else "monitor", "id": None if isinstance(of, str) else of}}
                       if of is not None else {})}
        mon, error = _resolve(mid)
        return public.view_of(mon, server.APP_VIEW) if mon else {**server.APP_VIEW, "public": {"id": mid, "error": error}}

    def page_clock():
        if which() == "monitor":
            return None   # a public monitor runs on the real clock, at its place
        return {"at": moment_for_request().at.isoformat(), "moment": moment_for_request().key,
                "moments": [{"key": mm.key, "label": mm.label, "n": SAMPLES.index(mm.key) + 1} for mm in MOMENTS.values()]}

    def points(location_id, now_local, hours=24):
        w = which()
        if w == "sample":
            return history_points(key(), location_id, now_local, hours)
        return monitor_points(monitor(), location_id, now_local, hours)

    no_road = {"toward": False, "traffic": None, "wind_impact": None, "pollution_pressure": None}   # road_traffic without a road

    sources.api_get = api_get
    sources.get_open_meteo_data = weather_now
    sources.get_air_forecast = air_model
    sources.smoke_status = smoke_status
    sources.get_smoke_data = lambda *a, **k: smoke_status()["detected"]
    sources.get_pollen_days = lambda *a, **k: pollen_days(key()) if which() == "sample" else {"today": [], "tomorrow": []}
    sources.get_pollen_data = lambda *a, **k: pollen_days(key())["today"] if which() == "sample" else []
    sources.source_on = source_on
    sources.pollen_state = lambda: "ok" if sources.source_on("pollen") else "off"   # made up, so no key to miss
    sources.history_points = points
    sources._fetch_world = lambda: world_list() if which() == "monitor" else []   # a sample's cached() runs it; nothing leaves the machine
    sources._fetch_nearby = nearby_of
    air_read.active_road = lambda: server.ROAD if which() == "sample" else None
    air_read.road_traffic = lambda hour, wind: real["road_traffic"](hour, wind) if which() == "sample" else dict(no_road)
    sources.local_now = now
    # every sample's answer is computed per request: no shared cache (its keys don't know the moment), no pool threads
    sources.cached = cached
    server._CONTEXT_POOL = _Inline()
    server.page_view = page_view
    server.page_clock = page_clock
    server.monitor_missing = lambda: asked() == "missing"
    air_read.outdoor_row = monitor   # a public monitor's row from the world list: its age and offline flag; None for a sample
    # the hidden one-monitor cases (?moment=indoor-near, indoor-model, outdoor-only): which monitors the home has
    sources.outdoor_from = outdoor_from
    sources.outdoor_source = outdoor_source
    sources.source_history_rows = source_history_rows
    air_read.indoor_monitor = indoor_monitor


# ── public monitors (?monitor=) ──

_REAL = {}   # server.py's own cache and fetchers, saved by install() before it replaces them
# what "AirGradient's public map didn't answer" means: the fetch failed (network, HTTP status, bad JSON) or timed out
WORLD_ERRORS = (requests.RequestException, RuntimeError, TimeoutError)


def real_cached(key, fetch, **kw):
    """server.py's own cache, for a public monitor's data, waiting no longer than what's left of the request's
    REQUEST_BUDGET: in the demo a request's upstreams run one after another, and past the budget each answers at once
    from what's cached (or fails, and the caller falls back as when the upstream is down)."""
    from flask import g
    try:
        deadline = g.setdefault("upstream_deadline", monotonic() + public.REQUEST_BUDGET)
    except RuntimeError:   # outside a request: no budget to keep
        return _REAL["cached"](key, fetch, **kw)
    left = max(0.0, deadline - monotonic())
    return _REAL["cached"](key, fetch, **{**kw, "wait": min(kw.get("wait", public.MONITOR_WAIT), left)})


def world_list():
    """AirGradient's world list through the real cache ("ag:world", one list for every monitor and the picker), fetched
    in the request's thread (never inside a cached fetch). Raises when the map doesn't answer and nothing recent is cached."""
    value, _ = real_cached("ag:world", _REAL["_fetch_world"], force=_REAL["force"](), **_REAL["world_cache"])
    return value


def _resolve(mid):
    """(monitor, None), or (None, the message for the page) when it can't be shown; (None, None) without an id.
    Memoized per request (flask.g), so a request reads the world list once."""
    if mid is None:
        return None, None
    from flask import g
    memo = getattr(g, "public_monitor", None)
    if memo and memo[0] == mid:
        return memo[1]
    try:
        mon = publicmap.find(world_list(), mid)
        out = (mon, None) if mon else (None, public.UNKNOWN.format(id=mid))
    except WORLD_ERRORS:
        out = (None, public.WORLD_DOWN)
    g.public_monitor = (mid, out)
    return out


def monitor_history(mon, hours):
    """A public monitor's last `hours` of readings from AirGradient's public map, as /api/history rows; [] when the
    map has no entry for it or doesn't answer (the page then draws the model's past). Fetched in the request's thread
    through the real cache, under keys that carry the monitor's id: its map id for MAP_ID_TTL, each range for
    HISTORY_TTL. A failed fetch isn't cached, so the next request asks again."""
    here_key = public.here_of(mon).key
    try:
        mid, _ = real_cached(f"ag:mapid:{here_key}", lambda: publicmap.map_id(mon), ttl=publicmap.MAP_ID_TTL,
                                 wait=publicmap.MAP_WAIT)
        if mid is None:
            return []
        rows, _ = real_cached(f"ag:maphist:{here_key}:{hours}h", lambda: publicmap.history(mid, hours),
                                  ttl=publicmap.HISTORY_TTL, wait=publicmap.MAP_WAIT)
    except WORLD_ERRORS:   # the map failed or timed out, like the world list; a bug in our code still raises
        return []
    return [dict(r) for r in rows]


def _utc_of(s):
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _is(mon, location_id):
    """Whether an id the page sent is this monitor's (a string, a number or junk)."""
    return location_id is not None and str(location_id) == str(mon["locationId"])


def monitor_past(mon, location_id, params, ranges):
    """/locations/{id}/measures/past for a public monitor: its rows between from and to (the last day without them),
    from the shortest History range (`ranges`, hours) that reaches back to from (within RANGE_SLACK), the longest at
    most."""
    if not _is(mon, location_id):
        return []
    p, now = params or {}, datetime.now(timezone.utc)
    try:
        frm = _utc_of(p["from"]) if p.get("from") else now - timedelta(days=1)
        to = _utc_of(p["to"]) if p.get("to") else now
    except ValueError:
        raise RuntimeError("AirGradient API returned 400: bad from/to")
    back = (now - frm - RANGE_SLACK).total_seconds() / 3600
    hours = next((h for h in ranges if h >= back), ranges[-1])
    return [r for r in monitor_history(mon, hours) if frm <= _utc_of(r["timestamp"]) <= to]


def monitor_points(mon, location_id, now_local, hours):
    """server.history_points for a public monitor: its last `hours` as (local time, row), oldest first."""
    if not _is(mon, location_id):
        return []
    rows = ((_utc_of(r["timestamp"]).astimezone(now_local.tzinfo), r) for r in monitor_history(mon, hours))
    return sorted(((t, r) for t, r in rows if now_local - timedelta(hours=hours) <= t <= now_local), key=lambda p: p[0])
