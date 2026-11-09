"""Reads the one config file that holds everything specific to a home."""
import json
import math
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent   # the app's folder: config.toml, demo/ and relative road routes live here

# the needs the page knows ([needs]); a new one is code (SETUP.md, "Adding a need")
NEEDS = ("toddler", "sinus", "runner")
# the keys [limits] may set
LIMITS = ("co2", "pm", "pm_high", "rh_dry", "rh_good", "rh_damp", "rh_stop", "pollen")
# the household's thresholds, [limits] in config.toml; config.example.toml says what each one means
DEFAULT_LIMITS = {"co2": 800, "pm": 15, "pm_high": 35, "rh_dry": 30, "rh_good": 50, "rh_damp": 60, "rh_stop": 55, "pollen": 3}
SOURCES = ("smoke", "pollen", "nearby")   # outside sources [sources] can turn off
# what [home] appliances may list: the damp-room action runs the first one the home has. Default: both.
APPLIANCES = ("dehumidifier", "ac_dry")


def real_value(value) -> bool:
    """A key someone filled in: not empty, and not .env.example's placeholder ("your_token_here", "your_…")."""
    v = str(value or "").strip().strip("'\"").strip()
    return bool(v) and not v.lower().startswith("your_")


def env_key(name: str, env: Mapping[str, str] = os.environ) -> str:
    """The key's value, or "" when it is missing, empty or still the placeholder."""
    value = env.get(name, "")
    return value if real_value(value) else ""


class ConfigError(Exception):
    """The message names the source and the problem."""


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float
    timezone: str
    indoor: str
    outdoor: str
    pollen_zip: str | None
    region: str | None = None   # city or region for a few sentences ("the usual New York season"); None: neutral wording


@dataclass(frozen=True)
class Road:
    name: str
    route: str
    rush: tuple[tuple[int, int, str], ...]
    toward: tuple[int, int]
    kind: str = "highway"   # shown after the name ("BQE expressway"), so readers elsewhere know what it is


@dataclass(frozen=True)
class Config:
    source: str
    demo: bool
    place: Place
    road: Road | None
    needs: dict[str, bool]
    limits: dict[str, float]
    pollen_seasons: tuple[dict, ...]
    sources: dict[str, bool]
    appliances: tuple[str, ...] = APPLIANCES


def _clean(text: str) -> str:
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"" and "\n" in text:
        text = text[1:-1]
    return text.lstrip("﻿").strip() + "\n"


def bearing_in(deg: float, toward: tuple[int, int]) -> bool:
    """True if a compass bearing lies in the arc (lo, hi); lo > hi means the arc crosses north."""
    lo, hi = toward
    deg = deg % 360
    return lo <= deg <= hi if lo <= hi else deg >= lo or deg <= hi


def toward_range(lat: float, lon: float, route: list[list[float]], within_km: float = 2.0) -> tuple[int, int]:
    """Smallest arc of compass bearings (lo, hi) containing every route point within within_km.
    When the arc crosses north, lo > hi (for example (350, 10))."""
    bearings = []
    for plon, plat in route:
        dy = (plat - lat) * 111.32
        dx = (plon - lon) * 111.32 * math.cos(math.radians(lat))
        if math.hypot(dx, dy) <= within_km:
            bearings.append(math.degrees(math.atan2(dx, dy)) % 360)
    if not bearings:
        raise ConfigError(f"road: no route point within {within_km} km of home; set road.toward by hand")
    bearings.sort()
    n = len(bearings)
    # the arc starts just after the largest gap between neighbours (the wrap-around gap included)
    gaps = [((bearings[(i + 1) % n] - bearings[i]) % 360, i) for i in range(n)]
    _, i = max(gaps)
    return round(bearings[(i + 1) % n]) % 360, round(bearings[i]) % 360


def _need(table: dict, key: str, section: str, source: str):
    if key not in table:
        raise ConfigError(f"{source}: missing {section}.{key}")
    return table[key]


def _table(raw: dict, name: str, source: str) -> dict:
    t = raw.get(name, {})
    if not isinstance(t, dict):
        raise ConfigError(f"{source}: [{name}] must be a table")
    return t


def _num(v, where: str, source: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ConfigError(f"{source}: {where} must be a number")
    return float(v)


def _int(v, where: str, source: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ConfigError(f"{source}: {where} must be a whole number")
    return v


def _flag(v, where: str, source: str) -> bool:
    if not isinstance(v, bool):
        raise ConfigError(f"{source}: {where} must be true or false")
    return v


def _region(v, source: str) -> str | None:
    if v is None:
        return None
    if not isinstance(v, str):
        raise ConfigError(f"{source}: place.region must be text, like \"New York\"")
    return v.strip() or None


def limit_order_problems(limits: Mapping[str, float]) -> list[str]:
    """The limits that are out of order, in words. config.py refuses them; scripts/check_config.py lists them."""
    lim = lambda k: limits.get(k, DEFAULT_LIMITS[k])
    out = []
    if not lim("rh_dry") < lim("rh_stop") < lim("rh_damp"):
        out.append("limits must follow rh_dry < rh_stop < rh_damp (dry, then the damp-room action's target, then damp)")
    if not lim("rh_dry") < lim("rh_good") <= lim("rh_damp"):
        out.append("limits must follow rh_dry < rh_good <= rh_damp (dry, then the top of the comfortable band, then damp)")
    if not lim("pm") < lim("pm_high"):
        out.append("limits.pm must be below limits.pm_high")
    return out


def _appliances(home: dict, source: str) -> tuple[str, ...]:
    v = home.get("appliances", list(APPLIANCES))
    if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
        raise ConfigError(f"{source}: home.appliances must be a list, like [\"dehumidifier\", \"ac_dry\"]")
    unknown = [x for x in v if x not in APPLIANCES]
    if unknown:
        raise ConfigError(f"{source}: home.appliances has {', '.join(unknown)}. Use only: {', '.join(APPLIANCES)}")
    return tuple(x for x in APPLIANCES if x in v)


def _parse(text: str, source: str, root: Path, demo: bool) -> Config:
    try:
        raw = tomllib.loads(_clean(text))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{source}: {e}") from e
    p = raw.get("place")
    if not isinstance(p, dict):
        raise ConfigError(f"{source}: missing [place]")
    place = Place(
        name=str(_need(p, "name", "place", source)),
        lat=_num(_need(p, "lat", "place", source), "place.lat", source),
        lon=_num(_need(p, "lon", "place", source), "place.lon", source),
        timezone=str(_need(p, "timezone", "place", source)),
        indoor=str(_need(p, "indoor", "place", source)),
        outdoor=str(_need(p, "outdoor", "place", source)),
        pollen_zip=str(p["pollen_zip"]) if p.get("pollen_zip") else None,
        region=_region(p.get("region"), source),
    )
    try:
        ZoneInfo(place.timezone)
    except (ValueError, ZoneInfoNotFoundError) as e:
        raise ConfigError(f"{source}: place.timezone {place.timezone!r} is not a timezone name, like America/Chicago") from e
    needs_t, limits_t, sources_t, home_t = (_table(raw, n, source) for n in ("needs", "limits", "sources", "home"))
    needs = {k: _flag(needs_t.get(k, True), f"needs.{k}", source) for k in NEEDS}
    limits = {k: _num(limits_t.get(k, DEFAULT_LIMITS[k]), f"limits.{k}", source) for k in LIMITS}
    order = limit_order_problems(limits)
    if order:
        raise ConfigError(f"{source}: " + "; ".join(order))
    sources = {k: _flag(sources_t.get(k, True), f"sources.{k}", source) for k in SOURCES}
    road = None
    if "road" in raw:
        r = _table(raw, "road", source)
        name = str(_need(r, "name", "road", source))
        route = str(_need(r, "route", "road", source))
        rush_raw = r.get("rush", [])
        rush = []
        if not isinstance(rush_raw, list):
            raise ConfigError(f"{source}: road.rush must be a list of [start, end, label]")
        for item in rush_raw:
            if not (isinstance(item, list) and len(item) == 3 and isinstance(item[2], str)):
                raise ConfigError(f"{source}: road.rush entries must look like [7, 10, \"morning\"]")
            rush.append((_int(item[0], "road.rush hour", source), _int(item[1], "road.rush hour", source), item[2]))
        if "toward" in r:
            t = r["toward"]
            if not (isinstance(t, list) and len(t) == 2):
                raise ConfigError(f"{source}: road.toward must be two numbers, like [80, 200]")
            toward = (_int(t[0], "road.toward", source), _int(t[1], "road.toward", source))
        else:
            path = route_path(route, root)
            try:
                points = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise ConfigError(f"{source}: cannot read road.route {route}: {e}") from e
            try:
                toward = toward_range(place.lat, place.lon, points)
            except ConfigError as e:
                raise ConfigError(f"{source}: {e}") from e
            except (TypeError, ValueError) as e:
                raise ConfigError(f"{source}: road.route {route} is not a list of [lon, lat] points") from e
        kind = str(r.get("kind", "highway")).strip() or "highway"
        road = Road(name, route, tuple(rush), toward, kind)
    seasons = raw.get("pollen_seasons", [])
    if not isinstance(seasons, list):
        raise ConfigError(f"{source}: pollen_seasons must be a list of [[pollen_seasons]] blocks")
    return Config(source, demo, place, road, needs, limits, tuple(seasons), sources, _appliances(home_t, source))


def load_config(env: Mapping[str, str] = os.environ, root: Path = ROOT) -> Config | None:
    """DEMO=1 reads demo/config.toml; else CONFIG_TOML (the file's contents, for hosts without files);
    else CONFIG_FILE (a path, e.g. a mounted volume); else root/config.toml; else None."""
    if env.get("DEMO") == "1":
        path = root / "demo" / "config.toml"
        try:
            return _parse(path.read_text(encoding="utf-8"), "demo", root, True)
        except (OSError, UnicodeDecodeError) as e:
            raise ConfigError(f"demo: cannot read {path}: {e}") from e
    if env.get("CONFIG_TOML", "").strip():
        return _parse(env["CONFIG_TOML"], "CONFIG_TOML", root, False)
    if env.get("CONFIG_FILE", "").strip():
        path = Path(env["CONFIG_FILE"].strip())
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ConfigError(f"CONFIG_FILE: cannot read {path}: {e}") from e
        return _parse(text, "CONFIG_FILE", root, False)
    path = root / "config.toml"
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ConfigError(f"config.toml: cannot read {path}: {e}") from e
        return _parse(text, "config.toml", root, False)
    return None


def route_path(route: str, root: Path = ROOT) -> Path:
    """road.route is relative to the app's folder unless absolute."""
    return Path(route) if Path(route).is_absolute() else root / route


def road_distance_km(lat: float, lon: float, road: Road, root: Path = ROOT) -> float | None:
    """How far the road's nearest route point is from home, to the half km (at least 0.5). None if the route can't be read."""
    try:
        points = json.loads(route_path(road.route, root).read_text(encoding="utf-8"))
        d = min(math.hypot((plon - lon) * 111.32 * math.cos(math.radians(lat)), (plat - lat) * 111.32) for plon, plat in points)
    except (OSError, ValueError, TypeError):
        return None
    return max(0.5, round(d * 2) / 2)


def _links(p: Place) -> dict:
    """Outside pages about the home, built from its place. NWS and pollen.com are US only."""
    lat, lon = round(p.lat, 2), round(p.lon, 2)
    ag = ("https://www.airgradient.com/map?zoom={z}&long={lon}&lat={lat}&meas=ug_m3&wind_layer=false"
          "&fires_layer=false&map_theme=light&org=ag&embedded=false&sidebar=1")
    links = {
        "forecast": f"https://forecast.weather.gov/MapClick.php?lat={lat}&lon={lon}",
        "traffic": f"https://www.google.com/maps/@{lat},{lon},14z/data=!5m1!1e1",
        "map_home": ag.format(z=15, lat=lat, lon=lon),
        "map_area": ag.format(z=12, lat=lat, lon=lon),
    }
    if p.pollen_zip:
        links["pollen"] = f"https://www.pollen.com/forecast/current/pollen/{p.pollen_zip}"
    return links


def public_view(cfg: Config, root: Path = ROOT) -> dict:
    """What the page may see (window.APP). Never env values."""
    p = cfg.place
    view = {
        "place": {
            "name": p.name, "lat": round(p.lat, 2), "lon": round(p.lon, 2), "timezone": p.timezone,
            "indoor": p.indoor, "outdoor": p.outdoor, "pollen_zip": p.pollen_zip, "region": p.region,
        },
        "links": _links(p),
        "road": None,
        "needs": dict(cfg.needs),
        "limits": dict(cfg.limits),
        "pollen_seasons": list(cfg.pollen_seasons),
        "sources": dict(cfg.sources),
    }
    if cfg.road:
        view["road"] = {"name": cfg.road.name, "kind": cfg.road.kind, "toward": list(cfg.road.toward), "rush": [list(r) for r in cfg.road.rush],
                        "distance_km": road_distance_km(p.lat, p.lon, cfg.road, root)}
    return view
