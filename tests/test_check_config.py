import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_config  # noqa: E402

EXAMPLE = (REPO / "config.example.toml").read_text(encoding="utf-8")


def run(tmp_path, text=EXAMPLE, env=None, dotenv=None, argv=None, capsys=None):
    f = tmp_path / "config.toml"
    if text is not None:
        f.write_text(text, encoding="utf-8")
    if dotenv is not None:
        (tmp_path / ".env").write_text(dotenv, encoding="utf-8")
    code = check_config.main(argv if argv is not None else [], env or {}, tmp_path)
    out = capsys.readouterr()
    return code, out.out + out.err


def test_example_ok(tmp_path, capsys):
    code, out = run(tmp_path, capsys=capsys)
    assert code == 0
    assert "Config OK" in out
    assert "Checked config.toml" in out


def test_example_placeholders_count_as_missing(tmp_path, capsys):
    """.env.example's values are placeholders, not keys: copied as they are, they are still missing."""
    dotenv = "AIRGRADIENT_TOKEN=your_token_here\nGOOGLE_POLLEN_API_KEY=your_key_here\n"
    code, out = run(tmp_path, dotenv=dotenv, env={"GOOGLE_POLLEN_API_KEY": "your_pollen_key"}, capsys=capsys)
    assert "AIRGRADIENT_TOKEN missing" in out
    assert "GOOGLE_POLLEN_API_KEY missing" in out
    assert "your_token_here" not in out and "your_key_here" not in out


def test_keys_set_and_missing(tmp_path, capsys):
    code, out = run(tmp_path, dotenv="AIRGRADIENT_TOKEN=abc\n# GOOGLE_POLLEN_API_KEY=zzz\n", capsys=capsys)
    assert "AIRGRADIENT_TOKEN set" in out
    assert "GOOGLE_POLLEN_API_KEY missing" in out


def test_env_vars_count(tmp_path, capsys):
    code, out = run(tmp_path, env={"GOOGLE_POLLEN_API_KEY": "k"}, capsys=capsys)
    assert "GOOGLE_POLLEN_API_KEY set" in out
    assert "AIRGRADIENT_TOKEN missing" in out


def test_never_prints_values(tmp_path, capsys):
    code, out = run(tmp_path, env={"AIRGRADIENT_TOKEN": "secret123"},
                    dotenv='export GOOGLE_POLLEN_API_KEY="secret456"\n', capsys=capsys)
    assert "secret123" not in out and "secret456" not in out
    assert "AIRGRADIENT_TOKEN set" in out and "GOOGLE_POLLEN_API_KEY set" in out


def test_decimals(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("lat = 39.95", "lat = 39.9526"), capsys=capsys)
    assert code == 1
    assert "latitude has 4 decimals: round to 2, about 1 km, since the page shows it" in out
    code, out = run(tmp_path, EXAMPLE.replace("lon = -75.16", "lon = -75.1652"), capsys=capsys)
    assert "longitude has 4 decimals" in out


def test_unknown_timezone(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("America/New_York", "Mars/Base"), capsys=capsys)
    assert code == 1 and "timezone" in out and "Mars/Base" in out


def test_route_missing(tmp_path, capsys):
    road = '\n[road]\nname = "X"\nroute = "static/nope.json"\nrush = [[7, 10, "morning"]]\ntoward = [80, 200]\n'
    code, out = run(tmp_path, EXAMPLE + road, capsys=capsys)
    assert code == 1 and "static/nope.json" in out and "not found" in out


def test_unknown_need(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("toddler = true", "toddler = true\ndog = true"), capsys=capsys)
    assert code == 1 and "needs.dog" in out and "toddler, sinus, runner" in out


def test_limits_order(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("rh_stop = 55", "rh_stop = 65"), capsys=capsys)
    assert code == 1 and "rh_dry < rh_stop < rh_damp" in out
    code, out = run(tmp_path, EXAMPLE.replace("pm_high = 35", "pm_high = 10"), capsys=capsys)
    assert code == 1 and "pm must be below limits.pm_high" in out


def test_toml_error_is_plain(tmp_path, capsys):
    code, out = run(tmp_path, "[place\n", capsys=capsys)
    assert code == 1 and "config.toml" in out and "Traceback" not in out


def test_missing_file(tmp_path, capsys):
    code, out = run(tmp_path, text=None, capsys=capsys)
    assert code == 1 and "No config.toml" in out


def test_file_flag(tmp_path, capsys):
    other = tmp_path / "other.toml"
    other.write_text(EXAMPLE, encoding="utf-8")
    code, out = run(tmp_path, text=None, argv=["--file", str(other)], capsys=capsys)
    assert code == 0 and "Checked " + str(other) in out


def test_falls_back_to_config_toml_env(tmp_path, capsys):
    code, out = run(tmp_path, text=None, env={"CONFIG_TOML": EXAMPLE}, capsys=capsys)
    assert code == 0 and "CONFIG_TOML" in out


def test_checks_the_file_config_file_points_at(tmp_path, capsys):
    mounted = tmp_path / "mounted" / "config.toml"
    mounted.parent.mkdir()
    mounted.write_text(EXAMPLE)
    code, out = run(tmp_path, text="not toml [", env={"CONFIG_FILE": str(mounted)}, capsys=capsys)
    assert code == 0 and "Checked config.toml" in out and "Config OK" in out
