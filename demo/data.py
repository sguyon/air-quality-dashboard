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

from config import route_path

from .moments import MOMENTS, TZ, moment_for

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

_HOME = {}   # the demo config's place and road, set by install()


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
    the current request asked for (?moment=, or the default)."""
    cfg = server.CFG
    _HOME.update(lat=cfg.place.lat, lon=cfg.place.lon, indoor=cfg.place.indoor, outdoor=cfg.place.outdoor,
                 route=cfg.road.route if cfg.road else None)
    _route.cache_clear()
    nearby.cache_clear()
    key = lambda: moment_for_request().key

    def api_get(path, params=None):
        if path == "/locations/measures/current":
            return current(key())
        hit = re.fullmatch(r"/locations/(\d+)/measures/past", path)
        if hit:
            return past(key(), hit.group(1), params)
        raise RuntimeError(f"AirGradient API returned 404: no demo data for {path}")

    server.api_get = api_get
    server.get_open_meteo_data = lambda *a, **k: weather(key())
    server.get_air_forecast = lambda *a, **k: dict(air_forecast(key()))
    server.smoke_status = lambda *a, **k: smoke(key())
    server.get_smoke_data = lambda *a, **k: smoke(key())["detected"]
    server.get_pollen_days = lambda *a, **k: pollen_days(key())
    server.get_pollen_data = lambda *a, **k: pollen_days(key())["today"]
    server.pollen_state = lambda: "ok" if server.source_on("pollen") else "off"   # made up, so no key to miss
    server.history_points = lambda location_id, now_local, hours=24: history_points(key(), location_id, now_local, hours)
    server._fetch_nearby = lambda: [dict(n) for n in nearby(key())]
    server.local_now = lambda: moment_for_request().at
    # every moment's answer is computed per request: no shared cache (its keys don't know the moment), no pool threads
    server.cached = lambda cache_key, fetch, **kw: (fetch(), {"state": "hit", "age": 0})
    server._CONTEXT_POOL = _Inline()
    server.page_clock = lambda: {"at": moment_for_request().at.isoformat(), "moment": moment_for_request().key,
                                 "moments": [{"key": mm.key, "label": mm.label} for mm in MOMENTS.values()]}
