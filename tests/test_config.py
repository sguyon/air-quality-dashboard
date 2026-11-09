import json
from pathlib import Path

import pytest

from config import Config, ConfigError, bearing_in, load_config, public_view, toward_range

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = (REPO / "config.example.toml").read_text(encoding="utf-8")


def root_with(tmp_path, text=EXAMPLE, name="config.toml"):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="")
    return tmp_path


def test_example_loads(tmp_path):
    cfg = load_config({}, root_with(tmp_path))
    assert isinstance(cfg, Config)
    assert cfg.needs == {"toddler": True, "sinus": True, "runner": True}
    assert cfg.road is None
    assert cfg.demo is False


def test_env_wins_over_file(tmp_path):
    root = root_with(tmp_path, EXAMPLE.replace('"Maplewood"', '"File"'))
    cfg = load_config({"CONFIG_TOML": EXAMPLE.replace('"Maplewood"', '"Env"')}, root)
    assert cfg.place.name == "Env"
    assert cfg.source == "CONFIG_TOML"


def test_demo_flag_reads_demo_file(tmp_path):
    root_with(tmp_path, EXAMPLE, "demo/config.toml")
    cfg = load_config({"DEMO": "1"}, tmp_path)
    assert cfg.demo is True
    assert cfg.source == "demo"


def test_nothing_returns_none(tmp_path):
    assert load_config({}, tmp_path) is None


def test_crlf_bom_and_quotes_parse(tmp_path):
    crlf = "﻿" + EXAMPLE.replace("\n", "\r\n")
    assert load_config({"CONFIG_TOML": crlf}, tmp_path).place.name == "Maplewood"
    assert load_config({"CONFIG_TOML": "'" + crlf + "'"}, tmp_path).place.name == "Maplewood"


def test_bad_toml_names_source_and_line(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_config({"CONFIG_TOML": "[place\n"}, tmp_path)
    assert "CONFIG_TOML" in str(e.value) and "line 1" in str(e.value)


def test_missing_required_key(tmp_path):
    text = EXAMPLE.replace("lat = 39.95\n", "")
    with pytest.raises(ConfigError) as e:
        load_config({"CONFIG_TOML": text}, tmp_path)
    assert "place.lat" in str(e.value)


def test_toward_range_matches_spec():
    route = json.loads((REPO / "static" / "bqe.json").read_text())
    lo, hi = toward_range(40.73, -73.95, route)
    # Research said (83, 194); the specified algorithm computes (89, 192). Pinned to the computed value.
    assert (lo, hi) == (89, 192)
    lo, hi = toward_range(40.7192, -73.9500, route)
    assert abs(lo - 63) <= 3 and abs(hi - 210) <= 3


def test_override_wins(tmp_path):
    text = EXAMPLE.replace("# [road]", "[road]").replace("# name = \"BQE\"", "name = \"BQE\"") \
        .replace("# route =", "route =").replace("# rush =", "rush =").replace("# toward =", "toward =")
    cfg = load_config({"CONFIG_TOML": text}, REPO)
    assert cfg.road.toward == (80, 200)
    assert cfg.road.rush[0] == (7, 10, "morning")


def test_road_without_toward_is_computed(tmp_path):
    text = EXAMPLE.replace("lat = 39.95", "lat = 40.73").replace("lon = -75.16", "lon = -73.95")
    text += '\n[road]\nname = "BQE"\nroute = "static/bqe.json"\nrush = [[7, 10, "morning"]]\n'
    cfg = load_config({"CONFIG_TOML": text}, REPO)
    assert cfg.road.toward == toward_range(40.73, -73.95, json.loads((REPO / "static/bqe.json").read_text()))


def test_public_view_has_no_secrets(tmp_path):
    cfg = load_config({"AIRGRADIENT_TOKEN": "x"}, root_with(tmp_path))
    assert cfg is not None
    assert '"x"' not in json.dumps(public_view(cfg))
    cfg = load_config({"AIRGRADIENT_TOKEN": "sekret-token", "CONFIG_TOML": EXAMPLE}, tmp_path)
    assert "sekret-token" not in json.dumps(public_view(cfg))
    assert public_view(cfg)["place"]["lat"] == 39.95


def test_toward_range_wraps_north():
    # points due north of home, spread slightly east and west
    route = [[-75.16 + dx, 39.95 + 0.01] for dx in (-0.002, 0.0, 0.002)]
    lo, hi = toward_range(39.95, -75.16, route)
    assert lo > hi and (360 - lo) + hi < 30
    assert bearing_in(0, (lo, hi)) and not bearing_in(180, (lo, hi))


def test_bearing_in_plain_arc():
    assert bearing_in(100, (80, 200)) and not bearing_in(10, (80, 200)) and not bearing_in(250, (80, 200))


def _bad(tmp_path, text):
    with pytest.raises(ConfigError) as e:
        load_config({"CONFIG_TOML": text}, REPO)
    return str(e.value)


def test_limits_not_a_table():
    msg = _bad(None, "limits = 5\n" + EXAMPLE.replace("[limits]", "[limits_gone]"))
    assert "CONFIG_TOML" in msg and "limits" in msg


def test_road_not_a_table():
    msg = _bad(None, "road = 3\n" + EXAMPLE)
    assert "CONFIG_TOML" in msg and "road" in msg


def test_limit_not_a_number():
    msg = _bad(None, EXAMPLE.replace("co2 = 800", 'co2 = "high"'))
    assert "CONFIG_TOML: limits.co2 must be a number" in msg


def test_bad_rush_entry():
    text = EXAMPLE + '\n[road]\nname = "R"\nroute = "static/bqe.json"\nrush = [[7, 10]]\ntoward = [80, 200]\n'
    assert "road.rush" in _bad(None, text)


def test_bad_toward():
    text = EXAMPLE + '\n[road]\nname = "R"\nroute = "static/bqe.json"\ntoward = [80]\n'
    assert "road.toward" in _bad(None, text)


def test_no_route_point_near_home_names_source():
    text = EXAMPLE + '\n[road]\nname = "R"\nroute = "static/bqe.json"\n'
    assert _bad(None, text).startswith("CONFIG_TOML: road:")


def test_unreadable_config_file(tmp_path):
    (tmp_path / "config.toml").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ConfigError) as e:
        load_config({}, tmp_path)
    assert "config.toml" in str(e.value)


def test_unknown_timezone_is_a_config_error(tmp_path):
    root = root_with(tmp_path, EXAMPLE.replace('timezone = "America/New_York"', 'timezone = "Nowhere/Town"'))
    with pytest.raises(ConfigError, match="place.timezone 'Nowhere/Town'"):
        load_config({}, root)


def test_road_kind_defaults_to_highway():
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent
    text = (ROOT / "tests/fixtures/config_sacha.toml").read_text()
    cfg = load_config({"CONFIG_TOML": text}, ROOT)
    assert cfg.road.kind == "expressway" and public_view(cfg)["road"]["kind"] == "expressway"
    plain = load_config({"CONFIG_TOML": text.replace('kind = "expressway"\n', "", 1)}, ROOT)
    assert plain.road.kind == "highway"



def test_config_file_points_at_another_path(tmp_path):
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    f = tmp_path / "mounted.toml"
    f.write_text((root / "tests/fixtures/config_sacha.toml").read_text().replace('name = "Greenpoint"', 'name = "Mounted"', 1))
    assert load_config({"CONFIG_FILE": str(f)}, root).place.name == "Mounted"
    env_text = (root / "tests/fixtures/config_sacha.toml").read_text().replace('name = "Greenpoint"', 'name = "Env"', 1)
    assert load_config({"CONFIG_FILE": str(f), "CONFIG_TOML": env_text}, root).place.name == "Env"


def test_config_file_missing_is_an_error_not_a_fallback(tmp_path):
    (tmp_path / "config.toml").write_text('[place]\nname = "Root"\nlat = 1.0\nlon = 1.0\ntimezone = "UTC"\n')
    with pytest.raises(ConfigError, match="CONFIG_FILE"):
        load_config({"CONFIG_FILE": str(tmp_path / "nope.toml")}, tmp_path)
