"""Public AirGradient monitors in the demo (?monitor=<id>): any outdoor monitor on AirGradient's public map, shown with
its live reading and its place's forecast instead of made-up data.

What is specific to the demo: a monitor's page view, its place for the fetchers and its cache keys, the request's time
budget. The helpers a real home can use too (which monitors are outdoor, the nearest, the map's id and history) live in
publicmap.py. A public monitor has no indoor monitor; when the map has no history for it, the page falls back to the
model's past. demo/data.py wires these in.
"""
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import publicmap
from config import Here, place_links

MONITOR_TTL = 300   # s: how long a monitor's weather and model stay fresh in the cache (5 min)
# cache keys one for every monitor (and a home), kept in the real cache with their own ttl: NOAA's smoke polygons,
# one file for all of North America that NOAA posts a few times a day
SHARED_KEYS = ("smoke",)
DEFAULT_LIST = ("New York", 40.71, -73.95)   # the picker's list before anyone gives a location: around the demo's home
# km: how far from the demo's home its pollen seasons still hold (the same climate); a monitor farther away gets none,
# so its pollen card shows no calendar rather than New York's
DEMO_REGION_KM = 300

UNKNOWN = "Monitor {id} isn't on AirGradient's public map"   # the id isn't an outdoor monitor of the world list
WORLD_DOWN = "AirGradient's public map didn't answer"   # the world list failed or timed out

PROFILES = {"toddler": False, "sinus": False, "runner": True}   # a public monitor is outdoor only: the runner's profile

# s: how long a request waits on a monitor's weather, PM2.5 model or NOAA smoke before answering without it (a late
# fetch still lands in the cache for the next request); Open-Meteo answers in about a second
MONITOR_WAIT = 6
# s: the most one request waits on upstreams in all (the world list, the map, weather, model, smoke, in series in the
# demo): Vercel stops a request at 30 s (vercel.json maxDuration), and start-up and the rest need the remainder
REQUEST_BUDGET = 20


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


def view_of(monitor, base_view):
    """window.APP for a public monitor: the demo's view, at the monitor's place, outdoor only, no road, no pollen. The
    demo home's pollen seasons only within DEMO_REGION_KM of it."""
    name, here, na = publicmap.name_of(monitor), here_of(monitor), publicmap.in_north_america(monitor)
    home = base_view.get("place", {})
    near_home = home.get("lat") is not None and publicmap.km_between(home["lat"], home["lon"], here.lat, here.lon) <= DEMO_REGION_KM
    lat, lon = round(here.lat, 2), round(here.lon, 2)
    links = place_links(SimpleNamespace(lat=lat, lon=lon, pollen_zip=None))
    if not na:
        links["forecast"] = None   # NWS forecasts only the US
    place = {**base_view.get("place", {}), "name": name, "lat": lat, "lon": lon, "timezone": here.tz,
             "indoor": None, "outdoor": name, "pollen_zip": None, "region": None}
    return {**base_view, "place": place, "links": links, "road": None, "profiles": dict(PROFILES),
            "pollen_seasons": list(base_view.get("pollen_seasons") or []) if near_home else [],
            "sources": {**base_view.get("sources", {}), "pollen": False, "road": False, "smoke": na, "nearby": True},
            "public": {"id": monitor["locationId"], "name": name, "street": monitor.get("publicPlaceName"),
                       "contributor": monitor.get("publicContributorName"),
                       "url": monitor.get("publicPlaceUrl")}}


def current_rows(monitor):
    """/api/current for a public monitor: its one outdoor reading."""
    return [publicmap.reading_row(monitor)]
