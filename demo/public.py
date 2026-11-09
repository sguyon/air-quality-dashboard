"""Public AirGradient monitors in the demo (?monitor=<id>): any outdoor monitor on AirGradient's public map, shown with
its live reading and its place's forecast instead of made-up data.

Pure functions over the world list (GET /world/locations/measures/current, no token): which monitors are outdoor, the
nearest ones for the picker, a monitor's place, its page view and its /api/current row. demo/data.py wires them in.
A public monitor has no indoor monitor. Its history comes from AirGradient's public map backend (map_id, history): the
documented API shares it only with the owner's token, so when the map has no entry for it or doesn't answer, the page
falls back to the model's past.
"""
import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from config import Here, place_links
from summary import corrected_pm   # AirGradient's EPA correction: one home for the demo and every home's neighbors

OUTDOOR_PREFIX = "O-"   # AirGradient model names: "O-..." outdoor (Open Air), "I-..." indoor
MONITOR_TTL = 300   # s: how long a monitor's weather and model stay fresh in the cache (5 min)
# cache keys one for every monitor (and a home), kept in the real cache with their own ttl: NOAA's smoke polygons,
# one file for all of North America that NOAA posts a few times a day
SHARED_KEYS = ("smoke",)
PICKER_COUNT = 20   # monitors in the picker's list, nearest first
# lat min, lat max, lon min, lon max: North America, what NOAA HMS smoke maps cover; outside it there is no smoke check
# and no NWS forecast link (NWS covers the US only, so a monitor in Canada or Mexico still gets a link that won't help)
NORTH_AMERICA = (15, 75, -170, -50)
DEFAULT_LIST = ("New York", 40.71, -73.95)   # the picker's list before anyone gives a location: around the demo's home
EARTH_RADIUS_KM = 6371   # km: mean Earth radius, for distances between monitors
# km: how far from the demo's home its pollen seasons still hold (the same climate); a monitor farther away gets none,
# so its pollen card shows no calendar rather than New York's
DEMO_REGION_KM = 300

UNKNOWN = "Monitor {id} isn't on AirGradient's public map"   # the id isn't an outdoor monitor of the world list
WORLD_DOWN = "AirGradient's public map didn't answer"   # the world list failed or timed out

NEEDS = {"toddler": False, "sinus": False, "runner": True}   # a public monitor is outdoor only: the runner's need
ROW_KEYS = ("locationId", "name", "street", "contributor", "distance_km", "pm02", "offline", "timestamp")   # a picker row

# AirGradient's public map backend (map.airgradient.com, open source: airgradienthq/airgradient-map). Not the documented
# API: it gives a public monitor's history without a token, under its own location ids.
MAP_API = "https://map-data.airgradient.com/map/api/v1"
MAP_SOURCE = "AirGradient"   # the map's entries from AirGradient monitors (it lists other networks' sensors too)
MATCH_BOX = 0.003   # degrees around the monitor searched for its map entry (about 300 m)
MATCH_KM = 0.1   # km: the farthest a map entry may be and still be this monitor
MAP_ID_TTL = 24 * 3600   # s: how long a monitor's map id stays cached (a monitor's ids don't change)
HISTORY_TTL = 300   # s: how long a monitor's history stays fresh in the cache (5 min, like its weather)
MAP_WAIT = 5   # s: how long a request waits on the map (its id, then its history) before drawing the model's past instead
# s: how long a request waits on a monitor's weather, PM2.5 model or NOAA smoke before answering without it (a late
# fetch still lands in the cache for the next request); Open-Meteo answers in about a second
MONITOR_WAIT = 6
# s: the most one request waits on upstreams in all (the world list, the map, weather, model, smoke, in series in the
# demo): Vercel stops a request at 30 s (vercel.json maxDuration), and start-up and the rest need the remainder
REQUEST_BUDGET = 20
# the map's measure → /api/history's field; the map's pm25 is EPA-corrected (getEpaCorrectedPM.ts), like a home's pm02_corrected
MAP_MEASURES = {"pm25": "pm02_corrected", "rhum": "rhum", "atmp": "atmp", "rco2": "rco2"}
FINE_HOURS = 24   # h: ranges up to this get the map's 15-minute buckets (FINE_BUCKET), longer ones hourly (COARSE_BUCKET)
FINE_BUCKET, COARSE_BUCKET = "15m", "1h"


def outdoor(world):
    """The outdoor monitors of the world list that have a place."""
    return [m for m in world or [] if isinstance(m, dict) and str(m.get("model") or "").startswith(OUTDOOR_PREFIX)
            and m.get("latitude") is not None and m.get("longitude") is not None]


def find(world, location_id):
    """The outdoor monitor with this id, or None (unknown, removed, or indoor)."""
    return next((m for m in outdoor(world) if m.get("locationId") == location_id), None)


def name_of(monitor):
    return (monitor.get("publicLocationName") or monitor.get("locationName") or "").strip() or f"Monitor {monitor.get('locationId')}"


def _km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def nearest(world, lat, lon, n=PICKER_COUNT):
    """The n outdoor monitors nearest a point, nearest first, trimmed to what the picker shows."""
    rows = []
    for m in outdoor(world):
        rows.append({"locationId": m.get("locationId"), "name": name_of(m), "street": m.get("publicPlaceName"),
                     "contributor": m.get("publicContributorName"),
                     "distance_km": round(_km(lat, lon, m["latitude"], m["longitude"]), 1),
                     "pm02": _picker_pm(m), "offline": m.get("offline"), "timestamp": m.get("timestamp")})
    rows.sort(key=lambda r: r["distance_km"])
    return rows[:n]


def _tz_of(monitor):
    """The monitor's timezone as the world list gives it, when it names a real one; else UTC (none, or junk)."""
    name = monitor.get("timezone")
    try:
        ZoneInfo(name)
        return name
    except (ZoneInfoNotFoundError, ValueError, TypeError):   # missing, unknown ("Mars/Base"), or not a name ("../x", 5)
        return "UTC"


def here_of(monitor):
    """The monitor's place, for the fetchers: its own cache key, coordinates and timezone (UTC when it has none or
    names no real one)."""
    return Here(f"m{monitor['locationId']}", monitor["latitude"], monitor["longitude"], _tz_of(monitor))


def in_north_america(monitor):
    lat_lo, lat_hi, lon_lo, lon_hi = NORTH_AMERICA
    return lat_lo <= monitor["latitude"] <= lat_hi and lon_lo <= monitor["longitude"] <= lon_hi


def view_of(monitor, base_view):
    """window.APP for a public monitor: the demo's view, at the monitor's place, outdoor only, no road, no pollen. The
    demo home's pollen seasons only within DEMO_REGION_KM of it."""
    name, here, na = name_of(monitor), here_of(monitor), in_north_america(monitor)
    home = base_view.get("place", {})
    near_home = home.get("lat") is not None and _km(home["lat"], home["lon"], here.lat, here.lon) <= DEMO_REGION_KM
    lat, lon = round(here.lat, 2), round(here.lon, 2)
    links = place_links(SimpleNamespace(lat=lat, lon=lon, pollen_zip=None))
    if not na:
        links["forecast"] = None   # NWS forecasts only the US
    place = {**base_view.get("place", {}), "name": name, "lat": lat, "lon": lon, "timezone": here.tz,
             "indoor": None, "outdoor": name, "pollen_zip": None, "region": None}
    return {**base_view, "place": place, "links": links, "road": None, "needs": dict(NEEDS),
            "pollen_seasons": list(base_view.get("pollen_seasons") or []) if near_home else [],
            "sources": {**base_view.get("sources", {}), "pollen": False, "road": False, "smoke": na, "nearby": True},
            "public": {"id": monitor["locationId"], "name": name, "street": monitor.get("publicPlaceName"),
                       "contributor": monitor.get("publicContributorName"),
                       "url": monitor.get("publicPlaceUrl")}}


def current_rows(monitor):
    """/api/current for a public monitor: its one outdoor reading, as the world list gives it, with pm02_corrected
    (the basis the page and the summary read first) when it has the humidity to correct with."""
    pm = corrected_pm(monitor.get("pm02"), monitor.get("rhum"))
    return [{**monitor, "locationName": name_of(monitor), "locationType": "outdoor",
             **({"pm02_corrected": pm} if pm is not None else {})}]


def _picker_pm(monitor):
    """A picker row's PM2.5: corrected, or the raw pm02 when there's no humidity to correct with (as the map does)."""
    pm = corrected_pm(monitor.get("pm02"), monitor.get("rhum"))
    return pm if pm is not None else monitor.get("pm02")


def _map_rows(payload):
    """The map's answer rows: {"data": [...]} (a bare list is read too)."""
    rows = payload.get("data") if isinstance(payload, dict) else payload
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _utc(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def map_id(monitor):
    """The monitor's id on AirGradient's public map, or None: the AirGradient entry within MATCH_KM that has its name
    (stripped, any case), else the nearest one within MATCH_KM. Raises when the map doesn't answer."""
    lat, lon = monitor["latitude"], monitor["longitude"]
    r = requests.get(f"{MAP_API}/measurements/current/area", timeout=15, params={
        "measure": "pm25", "xmin": round(lon - MATCH_BOX, 6), "ymin": round(lat - MATCH_BOX, 6),
        "xmax": round(lon + MATCH_BOX, 6), "ymax": round(lat + MATCH_BOX, 6)})
    r.raise_for_status()
    names = {str(monitor.get(k) or "").strip().casefold() for k in ("locationName", "publicLocationName")} - {""}
    close = []   # (not named alike, km, map id): the named ones first, then the nearest
    for e in _map_rows(r.json()):
        lid = e.get("locationId")
        if e.get("dataSource") != MAP_SOURCE or not isinstance(lid, int) or isinstance(lid, bool):
            continue
        try:
            km = _km(lat, lon, float(e["latitude"]), float(e["longitude"]))
        except (KeyError, TypeError, ValueError):
            continue
        if km <= MATCH_KM:
            close.append((str(e.get("locationName") or "").strip().casefold() not in names, km, lid))
    return min(close)[2] if close else None


def history(map_id, hours, now=None):
    """The last `hours` of a monitor's readings on the map, as /api/history rows ("timestamp" in UTC with a Z, then
    pm02, rhum, atmp, rco2 when the map has them, as numbers), oldest first. One request per measure; 15-minute
    buckets up to FINE_HOURS, hourly beyond. Raises when the map doesn't answer."""
    now = now or datetime.now(timezone.utc)
    base = {"start": _utc(now - timedelta(hours=hours)), "end": _utc(now),
            "bucketSize": FINE_BUCKET if hours <= FINE_HOURS else COARSE_BUCKET}
    rows = {}
    for measure, field in MAP_MEASURES.items():
        r = requests.get(f"{MAP_API}/locations/{int(map_id)}/measures/history", params={**base, "measure": measure},
                         timeout=15)
        r.raise_for_status()
        for p in _map_rows(r.json()):
            try:   # values come as numbers or strings ("37.13"); a missing one is skipped
                at = datetime.fromisoformat(str(p["timebucket"]).replace("Z", "+00:00"))
                value = float(p["value"])
            except (KeyError, TypeError, ValueError):
                continue
            if at.tzinfo is not None and math.isfinite(value):
                rows.setdefault(at.astimezone(timezone.utc), {})[field] = value
    return [{"timestamp": at.strftime("%Y-%m-%dT%H:%M:%S.000Z"), **fields} for at, fields in sorted(rows.items())]
