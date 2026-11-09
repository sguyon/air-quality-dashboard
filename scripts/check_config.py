"""Checks a config file before the app starts. Prints plain problems; reports keys as set or missing, never their values.

Usage: python scripts/check_config.py [--file PATH]
"""
import argparse
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import DEFAULT_LIMITS, NEEDS, ConfigError, _clean, load_config, real_value, route_path  # noqa: E402

KEYS = ("AIRGRADIENT_TOKEN", "GOOGLE_POLLEN_API_KEY")


def keys_present(env, root: Path) -> dict[str, bool]:
    """True per key if it is in .env or the environment, with a real value. Values are never kept."""
    found = {k: real_value(env.get(k, "")) for k in KEYS}
    try:
        lines = (root / ".env").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip().removeprefix("export ").strip()
        if name in found and real_value(value):
            found[name] = True
    return found


def decimals(x: float) -> int:
    s = repr(x)
    return len(s.split(".")[1]) if "." in s and "e" not in s else 0


def extra_problems(raw: dict, root: Path) -> list[str]:
    out = []
    place = raw.get("place") if isinstance(raw.get("place"), dict) else {}
    for key, label in (("lat", "latitude"), ("lon", "longitude")):
        v = place.get(key)
        if isinstance(v, float) and decimals(v) > 2:
            out.append(f"{label} has {decimals(v)} decimals: round to 2, about 1 km, since the page shows it")
    needs = raw.get("needs") if isinstance(raw.get("needs"), dict) else {}
    for k in needs:
        if k not in NEEDS:
            out.append(f"needs.{k} is not a need the page knows. Use only: {', '.join(NEEDS)}")
    limits = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}

    def lim(k):
        v = limits.get(k, DEFAULT_LIMITS[k])
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    dry, stop, damp, pm, high = (lim(k) for k in ("rh_dry", "rh_stop", "rh_damp", "pm", "pm_high"))
    if None not in (dry, stop, damp) and not dry < stop < damp:
        out.append("limits must follow rh_dry < rh_stop < rh_damp (dry, then the dehumidifier's target, then damp)")
    if None not in (pm, high) and not pm < high:
        out.append("limits.pm must be below limits.pm_high")
    road = raw.get("road")
    if isinstance(road, dict) and isinstance(road.get("route"), str):
        if not route_path(road["route"], root).is_file():
            out.append(f"road.route file not found: {road['route']}")
    return out


def main(argv, env, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="Check config.toml before starting the app.")
    ap.add_argument("--file", help="config file to check (default: CONFIG_FILE, else config.toml, else CONFIG_TOML)")
    args = ap.parse_args(argv)

    if args.file:
        path = Path(args.file)
        label = path.name
    elif env.get("CONFIG_FILE", "").strip():
        path = Path(env["CONFIG_FILE"].strip())
        label = path.name
    elif (root / "config.toml").is_file():
        path = root / "config.toml"
        label = "config.toml"
    else:
        path, label = None, "CONFIG_TOML"
    if path is not None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"Problem: cannot read {path}: {e}")
            return 1
    elif env.get("CONFIG_TOML", "").strip():
        text = env["CONFIG_TOML"]
    else:
        print("Problem: No config.toml found. Copy config.example.toml to config.toml and edit it.")
        return 1
    print(f"Checked {args.file if args.file else label}")

    problems = []
    try:
        raw = tomllib.loads(_clean(text))
    except tomllib.TOMLDecodeError as e:
        print(f"Problem: {label}: {e}")
        return 1
    problems += extra_problems(raw, root)
    try:
        load_config({"CONFIG_TOML": text}, root)
    except ConfigError as e:
        msg = str(e).replace("CONFIG_TOML", label, 1)
        if "cannot read road.route" not in msg or not any("road.route file not found" in p for p in problems):
            problems.append(msg)

    for k, ok in keys_present(env, root).items():
        print(f"{k} {'set' if ok else 'missing'}")
    for p in problems:
        print(f"Problem: {p}")
    if problems:
        return 1
    print("Config OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
