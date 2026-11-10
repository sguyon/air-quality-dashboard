import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_config  # noqa: E402
import pytest  # noqa: E402

EXAMPLE = (REPO / "config.example.toml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test reaches AirGradient: an indoor-only config's source check sees no network (tests/test_outdoor_source.py
    gives it a made-up world list)."""
    def down():
        raise check_config.publicmap.requests.ConnectionError("offline in tests")
    monkeypatch.setattr(check_config.publicmap, "fetch_world", down)


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


def test_unknown_profile(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("toddler = true", "toddler = true\ndog = true"), capsys=capsys)
    assert code == 1 and "profiles.dog is not a profile the page knows" in out and "toddler, sinus, runner" in out


def test_old_needs_table_is_a_note_not_a_problem(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("[profiles]", "[needs]"), capsys=capsys)
    assert code == 0 and "Config OK" in out
    assert "Note: [needs] is the old name of [profiles]. It still works; rename it to [profiles]." in out


def test_old_needs_table_unknown_key(tmp_path, capsys):
    old = EXAMPLE.replace("[profiles]", "[needs]").replace("toddler = true", "toddler = true\ndog = true")
    code, out = run(tmp_path, old, capsys=capsys)
    assert code == 1 and "needs.dog is not a profile the page knows" in out


def test_both_tables_profiles_wins(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE + "\n[needs]\ntoddler = false\n", capsys=capsys)
    assert code == 0 and "Config OK" in out
    assert "Both are here, so [needs] is ignored" in out


def test_example_has_no_note(tmp_path, capsys):
    assert "Note:" not in run(tmp_path, capsys=capsys)[1]


def test_limits_order(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("rh_stop = 55", "rh_stop = 65"), capsys=capsys)
    assert code == 1 and "rh_dry < rh_stop < rh_damp" in out
    code, out = run(tmp_path, EXAMPLE.replace("pm_high = 35", "pm_high = 10"), capsys=capsys)
    assert code == 1 and "pm must be below limits.pm_high" in out
    for bad in ("rh_good = 25", "rh_good = 65"):   # under rh_dry, over rh_damp
        code, out = run(tmp_path, EXAMPLE.replace("rh_good = 50", bad), capsys=capsys)
        assert code == 1 and "rh_dry < rh_good <= rh_damp" in out, bad
    code, out = run(tmp_path, EXAMPLE.replace("rh_good = 50", "rh_good = 60"), capsys=capsys)
    assert code == 0, out   # the comfortable band may run up to the damp line


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


def _without(*keys):
    return "\n".join(l for l in EXAMPLE.splitlines() if not any(l.startswith(k + " =") for k in keys)) + "\n"


def test_says_which_monitors(tmp_path, capsys):
    assert "Monitors: indoor and outdoor" in run(tmp_path, capsys=capsys)[1]
    assert "Monitors: outdoor only" in run(tmp_path, _without("indoor"), capsys=capsys)[1]
    text = _without("outdoor").replace("[sources]\n", "[sources]\noutdoor_from = 900002\n", 1)
    code, out = run(tmp_path, text, capsys=capsys)
    assert code == 0 and "Monitors: indoor only; outdoor PM2.5 from public monitor 900002" in out
    text = _without("outdoor").replace("[sources]\n", '[sources]\noutdoor_from = "area"\n', 1)
    assert "outdoor PM2.5 from the area estimate" in run(tmp_path, text, capsys=capsys)[1]


def test_indoor_only_without_outdoor_from_is_a_problem(tmp_path, capsys):
    code, out = run(tmp_path, _without("outdoor"), capsys=capsys)
    assert code == 1 and "sources.outdoor_from" in out


def test_outdoor_from_next_to_an_outdoor_monitor_is_ignored(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace("[sources]\n", "[sources]\noutdoor_from = 900002\n", 1), capsys=capsys)
    assert code == 0 and "outdoor_from is ignored" in out


def test_a_blank_outdoor_name_reads_as_indoor_only(tmp_path, capsys):
    """Blanking the line is deleting it: check_config and the server agree, and never print 'the None estimate'."""
    code, out = run(tmp_path, EXAMPLE.replace('outdoor = "porch"', 'outdoor = ""'), capsys=capsys)
    assert code == 1 and "sources.outdoor_from" in out and "None" not in out and "Config OK" not in out
    text = EXAMPLE.replace('outdoor = "porch"', 'outdoor = "  "').replace("[sources]\n", '[sources]\noutdoor_from = "model"\n', 1)
    code, out = run(tmp_path, text, capsys=capsys)
    assert code == 0 and "Monitors: indoor only; outdoor PM2.5 from the model estimate" in out
    assert "outdoor_from is ignored" not in out


def test_a_blank_indoor_name_reads_as_outdoor_only(tmp_path, capsys):
    code, out = run(tmp_path, EXAMPLE.replace('indoor = "living room"', 'indoor = ""'), capsys=capsys)
    assert code == 0 and "Monitors: outdoor only" in out


def test_outdoor_source_line_tests_for_none():
    from types import SimpleNamespace as NS
    line = check_config.outdoor_source_line
    assert line(NS(place=NS(indoor="living room", outdoor="porch"), outdoor_from=None)) == "Monitors: indoor and outdoor"
    assert line(NS(place=NS(indoor=None, outdoor="porch"), outdoor_from=None)) == "Monitors: outdoor only"
    assert line(NS(place=NS(indoor="living room", outdoor=None), outdoor_from="area")) == \
        "Monitors: indoor only; outdoor PM2.5 from the area estimate"


def test_keys_present_reads_keys_the_way_the_server_does(tmp_path):
    """The first .env line for a key wins (a placeholder above a real token means no token), and the environment beats
    the file: check_config must say what the server will do."""
    (tmp_path / ".env").write_text("AIRGRADIENT_TOKEN=your_token_here\nAIRGRADIENT_TOKEN=real-looking-value-123\n")
    assert check_config.keys_present({}, tmp_path)["AIRGRADIENT_TOKEN"] is False
    (tmp_path / ".env").write_text("AIRGRADIENT_TOKEN=real-looking-value-123\n")
    assert check_config.keys_present({"AIRGRADIENT_TOKEN": ""}, tmp_path)["AIRGRADIENT_TOKEN"] is False
    assert check_config.keys_present({}, tmp_path)["AIRGRADIENT_TOKEN"] is True


def test_config_ok_without_a_token_says_it_is_not_live_yet(tmp_path, capsys):
    """Config OK means the file is valid; without the token the page can't read a monitor: say so (setup lab)."""
    code, out = run(tmp_path, capsys=capsys)
    assert code == 0 and "Config OK" in out and "Not live yet: add your AirGradient token" in out
    code, out = run(tmp_path, dotenv="AIRGRADIENT_TOKEN=real-looking-value-123\n", capsys=capsys)
    assert "Not live yet" not in out
