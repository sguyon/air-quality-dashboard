"""AirGradient's public monitors, for any home or the demo: which monitors of the world list are outdoor, the nearest
ones, a monitor's place name, its reading row, and its history from AirGradient's public map backend.

Pure functions over the world list (GET /world/locations/measures/current, no token), plus the two map requests
(map_id, history). The documented API shares a public monitor's history only with its owner's token; the map's backend
shares it without one. No import of demo/ or server.py.
"""
import math
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

from summary import corrected_pm   # AirGradient's EPA correction: one home for the demo and every home's neighbors

OUTDOOR_PREFIX = "O-"   # AirGradient model names: "O-..." outdoor (Open Air), "I-..." indoor
PICKER_COUNT = 20   # monitors in the picker's list, nearest first
# lat min, lat max, lon min, lon max: North America, what NOAA HMS smoke maps cover; outside it there is no smoke check
# and no NWS forecast link (NWS covers the US only, so a monitor in Canada or Mexico still gets a link that won't help)
NORTH_AMERICA = (15, 75, -170, -50)
EARTH_RADIUS_KM = 6371   # km: mean Earth radius, for distances between monitors

# AirGradient's public map backend (map.airgradient.com, open source: airgradienthq/airgradient-map). Not the documented
# API: it gives a public monitor's history without a token, under its own location ids.
MAP_API = "https://map-data.airgradient.com/map/api/v1"
MAP_SOURCE = "AirGradient"   # the map's entries from AirGradient monitors (it lists other networks' sensors too)
MATCH_BOX = 0.003   # degrees around the monitor searched for its map entry (about 300 m)
MATCH_KM = 0.1   # km: the farthest a map entry may be and still be this monitor
MAP_ID_TTL = 24 * 3600   # s: how long a monitor's map id stays cached (a monitor's ids don't change)
HISTORY_TTL = 300   # s: how long a monitor's history stays fresh in the cache (5 min, like its weather)
MAP_WAIT = 5   # s: how long a request waits on the map (its id, then its history) before drawing the model's past instead
# the map's measure → /api/history's field; the map's pm25 is EPA-corrected (getEpaCorrectedPM.ts), like a home's pm02_corrected
MAP_MEASURES = {"pm25": "pm02_corrected", "rhum": "rhum", "atmp": "atmp", "rco2": "rco2"}
FINE_HOURS = 24   # h: ranges up to this get the map's 15-minute buckets (FINE_BUCKET), longer ones hourly (COARSE_BUCKET)
FINE_BUCKET, COARSE_BUCKET = "15m", "1h"
PM_ONLY = {"pm25": "pm02_corrected"}   # history's measures when only PM2.5 is read (the area estimate): one request, not four

WORLD_URL = "https://api.airgradient.com/public/api/v1/world/locations/measures/current"   # every public monitor, no token

# An indoor-only home's outdoor PM2.5 ([sources] outdoor_from, chosen once at setup: internal spec "one monitor", Decided)
NEARBY_SOURCE_KM = 3   # km: a public outdoor monitor this close counts as nearby; setup suggests the nearest one as the source
AREA_KM = 15   # km: the public outdoor monitors within this radius tune the model for the "area" estimate
# area monitors with history needed for the area estimate: one alone would let a single sensor (by a grill, a dead fan)
# set the whole area's level; two is the least that isn't one sensor's word, and keeps the estimate where monitors are sparse
AREA_MIN_MONITORS = 2
PINNED_OFFLINE_DAYS = 7   # days: a chosen public monitor silent this long gets a note from check_config.py, with the next best
STALE_READING = timedelta(hours=2)   # a reading older than this counts as no reading now (a monitor gone quiet)


def fetch_world():
    """The world list: every public AirGradient monitor, as the API lists them (it drops one that stops reporting).
    Raises when AirGradient doesn't answer."""
    r = requests.get(WORLD_URL, timeout=15)
    r.raise_for_status()
    return r.json()


def outdoor(world):
    """The outdoor monitors of the world list that have a place."""
    return [m for m in world or [] if isinstance(m, dict) and str(m.get("model") or "").startswith(OUTDOOR_PREFIX)
            and m.get("latitude") is not None and m.get("longitude") is not None]


def find(world, location_id):
    """The outdoor monitor with this id, or None (unknown, removed, or indoor)."""
    return next((m for m in outdoor(world) if m.get("locationId") == location_id), None)


def plain_text(text):
    """An owner's text (a monitor's name) on one line: control and formatting characters (line breaks, bidi overrides)
    become spaces, so a name can't fake a line in check_config's output or reorder the text around it."""
    return " ".join("".join(" " if unicodedata.category(c) in ("Cc", "Cf") else c for c in str(text)).split())


def name_of(monitor):
    return plain_text(monitor.get("publicLocationName") or monitor.get("locationName") or "") or f"Monitor {monitor.get('locationId')}"


def km_between(lat1, lon1, lat2, lon2):
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
                     "distance_km": round(km_between(lat, lon, m["latitude"], m["longitude"]), 1),
                     "pm02": _picker_pm(m), "offline": m.get("offline"), "timestamp": m.get("timestamp")})
    rows.sort(key=lambda r: r["distance_km"])
    return rows[:n]


def reporting(monitor, now=None):
    """Whether a monitor's reading counts as a reading now: not marked offline, and its timestamp (aware) under
    STALE_READING old. The server's rule for an outdoor reading, and check_config.py's."""
    if monitor.get("offline"):
        return False
    try:
        ts = datetime.fromisoformat(str(monitor.get("timestamp")).replace("Z", "+00:00"))
    except ValueError:
        return False
    return ts.tzinfo is not None and (now or datetime.now(timezone.utc)) - ts <= STALE_READING


def within(world, lat, lon, km, now=None):
    """The outdoor monitors within `km` of a point that are reporting now (reporting()), nearest first, as
    (distance km, monitor)."""
    rows = [(km_between(lat, lon, m["latitude"], m["longitude"]), m) for m in outdoor(world) if reporting(m, now)]
    return sorted(((d, m) for d, m in rows if d <= km), key=lambda r: r[0])


def suggest(world, lat, lon, now=None):
    """The outdoor source setup recommends for an indoor-only home at a point: (choice, nearest, count). choice is the
    nearest reporting monitor's locationId when it is within NEARBY_SOURCE_KM, else "area" when at least
    AREA_MIN_MONITORS report within AREA_KM, else "model". nearest is (distance km, monitor) of the nearest within
    AREA_KM, or None; count is how many report within AREA_KM."""
    near = within(world, lat, lon, AREA_KM, now)
    first = near[0] if near else None
    if first and first[0] <= NEARBY_SOURCE_KM:
        return first[1].get("locationId"), first, len(near)
    return ("area" if len(near) >= AREA_MIN_MONITORS else "model"), first, len(near)


def in_north_america(monitor):
    lat_lo, lat_hi, lon_lo, lon_hi = NORTH_AMERICA
    return lat_lo <= monitor["latitude"] <= lat_hi and lon_lo <= monitor["longitude"] <= lon_hi


def reading_row(monitor):
    """A public monitor's one outdoor reading, as the world list gives it, with pm02_corrected (the basis the page and
    the summary read first) when it has the humidity to correct with."""
    pm = corrected_pm(monitor.get("pm02"), monitor.get("rhum"))
    return {**monitor, "locationName": name_of(monitor), "locationType": "outdoor",
            **({"pm02_corrected": pm} if pm is not None else {})}


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
            km = km_between(lat, lon, float(e["latitude"]), float(e["longitude"]))
        except (KeyError, TypeError, ValueError):
            continue
        if km <= MATCH_KM:
            close.append((str(e.get("locationName") or "").strip().casefold() not in names, km, lid))
    return min(close)[2] if close else None


def history(map_id, hours, now=None, measures=MAP_MEASURES):
    """The last `hours` of a monitor's readings on the map, as /api/history rows ("timestamp" in UTC with a Z, then
    pm02_corrected, rhum, atmp, rco2 when the map has them, as numbers), oldest first. One request per measure
    (`measures`: the map's measure → the row's field, every one by default); 15-minute buckets up to FINE_HOURS,
    hourly beyond. Raises when the map doesn't answer."""
    now = now or datetime.now(timezone.utc)
    base = {"start": _utc(now - timedelta(hours=hours)), "end": _utc(now),
            "bucketSize": FINE_BUCKET if hours <= FINE_HOURS else COARSE_BUCKET}
    rows = {}
    for measure, field in measures.items():
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
