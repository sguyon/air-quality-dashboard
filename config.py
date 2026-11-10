"""Reads the one config file that holds everything specific to a home."""
import json
import math
import os
import re
import tempfile
import tomllib
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent   # the app's folder: config.toml, demo/ and relative road routes live here

# Owner-only file mode: every saved dotenv contains credentials, including an existing file.
ENV_FILE_MODE = 0o600

# the profiles the page knows ([profiles]); a new one is code (SETUP.md, "Adding a profile")
PROFILES = ("toddler", "sinus", "runner")
# [profiles]' old name (v0.1 configs): still read when [profiles] is absent; [profiles] wins when both are there
OLD_PROFILES_TABLE = "needs"
# the keys [limits] may set
LIMITS = ("co2", "pm", "pm_high", "rh_dry", "rh_good", "rh_damp", "rh_stop", "pollen")
# the household's thresholds, [limits] in config.toml; config.example.toml says what each one means
DEFAULT_LIMITS = {"co2": 800, "pm": 15, "pm_high": 35, "rh_dry": 30, "rh_good": 50, "rh_damp": 60, "rh_stop": 55, "pollen": 3}
SOURCES = ("smoke", "pollen", "nearby")   # outside sources [sources] can turn off
# what [home] appliances may list: the damp-room action runs the first one the home has.
APPLIANCES = ("dehumidifier", "ac_dry")
DEFAULT_APPLIANCES = ()  # no equipment assumed: a home opts in to the appliances it has.
# the named ways to get outdoor PM2.5 without an outdoor monitor of your own ([sources] outdoor_from); the other way is a public monitor's id
OUTDOOR_FROM_KINDS = ("area", "model")


def real_value(value) -> bool:
    """A key someone filled in: not empty, and not .env.example's placeholder ("your_token_here", "your_…")."""
    v = str(value or "").strip().strip("'\"").strip()
    return bool(v) and not v.lower().startswith("your_")


def env_key(name: str, env: Mapping[str, str] = os.environ) -> str:
    """The key's value, or "" when it is missing, empty or still the placeholder."""
    value = env.get(name, "")
    return value if real_value(value) else ""


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


def defines(line, key):
    """Whether a dotenv line sets key, using parse_dotenv's name rules."""
    s = line.strip()
    return bool(s) and not s.startswith("#") and "=" in s and s.split("=", 1)[0].strip().removeprefix("export ").strip() == key


def write_env_key(path, key, value):
    """Replace one key atomically, preserving other lines. Unique temporary files and the result are owner-only."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or any(c in value for c in "\r\n\0"):
        raise ValueError("Invalid environment entry")
    target = path.resolve() if path.is_symlink() else path
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    out, placed = [], False
    for line in text.splitlines():
        if defines(line, key):
            if not placed:
                out.append(f"{key}={value}")
                placed = True
            continue
        out.append(line)
    if not placed:
        out.append(f"{key}={value}")
    fd, name = tempfile.mkstemp(prefix=".env-", dir=target.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), ENV_FILE_MODE)
            stream.write("\n".join(out) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


class ConfigError(Exception):
    """The message names the source and the problem."""


PLACE_DECIMALS = 2   # decimals kept on the home's coordinates: about 1 km, enough for weather, pollen and smoke
Here = namedtuple("Here", "key lat lon tz")   # a place the fetchers can look at: a cache key, coordinates, a timezone name


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float
    timezone: str
    indoor: str | None    # None: no indoor monitor
    outdoor: str | None   # None: no outdoor monitor; Config.outdoor_from says where outdoor PM2.5 comes from
    pollen_zip: str | None
    region: str | None = None   # city or region for a few sentences ("the usual New York season"); None: neutral wording
    indoor_id: int | None = None  # account monitor chosen at setup; older configs select by type.
    outdoor_id: int | None = None


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
    profiles: dict[str, bool]
    limits: dict[str, float]
    pollen_seasons: tuple[dict, ...]
    sources: dict[str, bool]
    appliances: tuple[str, ...] = DEFAULT_APPLIANCES
    outdoor_from: int | str | None = None   # without an outdoor monitor: a public monitor's locationId, "area" or "model"


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


def _monitor_id(place, kind, source):
    value = place.get(kind + "_id")
    if value is None:
        return None
    value = _int(value, f"place.{kind}_id", source)
    if value <= 0:
        raise ConfigError(f"{source}: place.{kind}_id must be positive")
    return value


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
    v = home.get("appliances", list(DEFAULT_APPLIANCES))
    if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
        raise ConfigError(f"{source}: home.appliances must be a list, like [\"dehumidifier\", \"ac_dry\"]")
    unknown = [x for x in v if x not in APPLIANCES]
    if unknown:
        raise ConfigError(f"{source}: home.appliances has {', '.join(unknown)}. Use only: {', '.join(APPLIANCES)}")
    return tuple(x for x in APPLIANCES if x in v)


def _outdoor_from(sources_t: dict, place: Place, source: str) -> int | str | None:
    """sources.outdoor_from: needed without an outdoor monitor, ignored with one."""
    if place.outdoor is not None:
        return None
    if "outdoor_from" not in sources_t:
        raise ConfigError(f"{source}: no outdoor monitor, so sources.outdoor_from is needed: a public monitor's id, \"area\" or \"model\"")
    v = sources_t["outdoor_from"]
    if (isinstance(v, int) and not isinstance(v, bool) and v > 0) or v in OUTDOOR_FROM_KINDS:
        return v
    raise ConfigError(f"{source}: sources.outdoor_from must be a public monitor's id, \"area\" or \"model\"")


def _monitor_name(p: dict, key: str) -> str | None:
    """A monitor's name from [place], or None when the line is missing or blank (blanking it is deleting it)."""
    name = str(p.get(key, ""))
    return name if name.strip() else None


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
        # rounded to about 1 km whatever the file says: the place leaves the server (weather, pollen) and shows on the page
        lat=round(_num(_need(p, "lat", "place", source), "place.lat", source), PLACE_DECIMALS),
        lon=round(_num(_need(p, "lon", "place", source), "place.lon", source), PLACE_DECIMALS),
        timezone=str(_need(p, "timezone", "place", source)),
        indoor=_monitor_name(p, "indoor"),
        outdoor=_monitor_name(p, "outdoor"),
        pollen_zip=str(p["pollen_zip"]) if p.get("pollen_zip") else None,
        region=_region(p.get("region"), source),
        indoor_id=_monitor_id(p, "indoor", source),
        outdoor_id=_monitor_id(p, "outdoor", source),
    )
    if place.indoor is None and place.outdoor is None:
        raise ConfigError(f"{source}: [place] needs indoor, outdoor or both (the names of your monitors)")
    try:
        ZoneInfo(place.timezone)
    except (ValueError, ZoneInfoNotFoundError) as e:
        raise ConfigError(f"{source}: place.timezone {place.timezone!r} is not a timezone name, like America/Chicago") from e
    table = "profiles" if "profiles" in raw or OLD_PROFILES_TABLE not in raw else OLD_PROFILES_TABLE
    profiles_t, limits_t, sources_t, home_t = (_table(raw, n, source) for n in (table, "limits", "sources", "home"))
    profiles = {k: _flag(profiles_t.get(k, True), f"{table}.{k}", source) for k in PROFILES}
    limits = {k: _num(limits_t.get(k, DEFAULT_LIMITS[k]), f"limits.{k}", source) for k in LIMITS}
    order = limit_order_problems(limits)
    if order:
        raise ConfigError(f"{source}: " + "; ".join(order))
    sources = {k: _flag(sources_t.get(k, True), f"sources.{k}", source) for k in SOURCES}
    outdoor_from = _outdoor_from(sources_t, place, source)
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
    return Config(source, demo, place, road, profiles, limits, tuple(seasons), sources, _appliances(home_t, source), outdoor_from)


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


def airgradient_map(lat, lon, zoom=15) -> str:
    """AirGradient's public map centered on a place: the home's monitor in the Home menu, each neighbor's row."""
    return (f"https://www.airgradient.com/map?zoom={zoom}&long={lon}&lat={lat}&meas=ug_m3&wind_layer=false"
            "&fires_layer=false&map_theme=light&org=ag&embedded=false&sidebar=1")


def place_links(p: Place) -> dict:
    """Outside pages about a place (anything with lat, lon and pollen_zip), the home's by default. NWS and pollen.com are US only."""
    lat, lon = round(p.lat, 2), round(p.lon, 2)
    links = {
        "forecast": f"https://forecast.weather.gov/MapClick.php?lat={lat}&lon={lon}",
        "traffic": f"https://www.google.com/maps/@{lat},{lon},14z/data=!5m1!1e1",
        "map_home": airgradient_map(lat, lon),
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
        "links": place_links(p),
        "road": None,
        "profiles": dict(cfg.profiles),
        "limits": dict(cfg.limits),
        "pollen_seasons": list(cfg.pollen_seasons),
        "sources": dict(cfg.sources),
    }
    if cfg.outdoor_from is not None:
        of = cfg.outdoor_from
        view["outdoor_from"] = {"kind": of if isinstance(of, str) else "monitor", "id": None if isinstance(of, str) else of}
    if cfg.road:
        view["road"] = {"name": cfg.road.name, "kind": cfg.road.kind, "toward": list(cfg.road.toward), "rush": [list(r) for r in cfg.road.rush],
                        "distance_km": road_distance_km(p.lat, p.lon, cfg.road, root)}
    return view
