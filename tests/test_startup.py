"""Starting up: the demo with nothing set up, a plain state with a config but no token, a clear stop otherwise.
The server reads its config at import, so the tests that need a fresh import reload it and restore the reference config after."""
import importlib
import os
import shutil

import pytest

import server as server_module
import sources

REFERENCE = os.environ["CONFIG_TOML"]


@pytest.fixture
def reloaded(monkeypatch):
    """reload(server) with the given env (None removes a key); the reference config and token back afterwards."""
    def run(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v) if v is not None else monkeypatch.delenv(k, raising=False)
        return importlib.reload(server_module)
    yield run
    monkeypatch.undo()
    importlib.reload(server_module)


def test_no_token_no_config_is_demo(tmp_path):
    root = server_module.Path(__file__).parent.parent
    (tmp_path / "demo").mkdir()
    shutil.copy(root / "demo" / "config.toml", tmp_path / "demo" / "config.toml")
    shutil.copytree(root / "static", tmp_path / "static")   # the route the demo's road reads
    cfg = server_module.startup_config({}, root=tmp_path)
    assert cfg.demo and server_module.server_mode(cfg, "") == "demo"


def test_config_no_token_state(reloaded):
    srv = reloaded(AIRGRADIENT_TOKEN="", CONFIG_TOML=REFERENCE)
    assert srv.MODE == "no_token"
    srv.app.config["TESTING"] = True
    with srv.app.test_client() as c:
        r = c.get("/api/current")
        assert r.status_code == 200 and r.get_json() == {"state": "no_token"}
        page = c.get("/").get_data(as_text=True)
    assert '"state": "no_token"' in page


def test_live_page_has_no_state(reloaded):
    srv = reloaded(AIRGRADIENT_TOKEN="x", CONFIG_TOML=REFERENCE)
    with srv.app.test_client() as c:
        assert '"state"' not in c.get("/").get_data(as_text=True)


# Exit code 4 is gunicorn's APP_LOAD_ERROR: the master stops instead of respawning the worker forever.
def test_token_no_config_exits_with_message(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        server_module.boot_config({"AIRGRADIENT_TOKEN": "secret-token"}, root=tmp_path)
    assert e.value.code == 4
    out = capsys.readouterr()
    assert out.err.strip() == "No config: copy config.example.toml to config.toml (or set CONFIG_TOML)"
    assert "secret-token" not in out.err + out.out


def test_invalid_config_exits_with_message(reloaded, capsys):
    with pytest.raises(SystemExit) as e:
        reloaded(AIRGRADIENT_TOKEN="secret-token", CONFIG_TOML="[place]\nlat = 40.7\n")
    assert e.value.code == 4
    out = capsys.readouterr()
    assert out.err.startswith("CONFIG_TOML:")
    assert "secret-token" not in out.err + out.out


def test_placeholder_token_with_config_is_no_token(reloaded):
    srv = reloaded(AIRGRADIENT_TOKEN="your_token_here", CONFIG_TOML=REFERENCE)
    assert srv.MODE == "no_token" and srv.TOKEN == ""


def test_placeholder_token_without_config_is_demo(tmp_path):
    root = server_module.Path(__file__).parent.parent
    (tmp_path / "demo").mkdir()
    shutil.copy(root / "demo" / "config.toml", tmp_path / "demo" / "config.toml")
    shutil.copytree(root / "static", tmp_path / "static")
    cfg = server_module.startup_config({"AIRGRADIENT_TOKEN": "your_token_here"}, root=tmp_path)
    assert cfg.demo and server_module.server_mode(cfg, "your_token_here") == "demo"
    assert server_module.server_mode(server_module.CFG, "your_token_here") == "no_token"


def test_placeholder_pollen_key_is_not_set_up(monkeypatch):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "your_key_here")
    assert sources.pollen_state() == "not_set_up"
    assert sources._fetch_pollen() == {"today": [], "tomorrow": []}   # never calls Google with the placeholder


def test_dotenv_skips_lines_without_a_key():
    assert server_module.parse_dotenv("=x\nexport =y\n  = z\nA=1\n") == {"A": "1"}


@pytest.mark.xdist_group("app-pid")   # runs server.py, which writes the repo's app.pid: same worker as test_autostart's pid test
def test_main_binds_localhost_unless_host_is_set(monkeypatch, capsys):
    import runpy
    import flask
    calls = []
    monkeypatch.setattr(flask.Flask, "run", lambda self, **kw: calls.append(kw))
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("PORT", "5599")
    path = str(server_module.Path(server_module.__file__))
    runpy.run_path(path, run_name="__main__")
    monkeypatch.setenv("HOST", "0.0.0.0")
    runpy.run_path(path, run_name="__main__")
    assert [c["host"] for c in calls] == ["127.0.0.1", "0.0.0.0"] and calls[0]["port"] == 5599
    assert "Home Air Quality → http://localhost:5599" in capsys.readouterr().out


def test_expired_token_is_not_no_token(reloaded, monkeypatch):
    srv = reloaded(AIRGRADIENT_TOKEN="expired", CONFIG_TOML=REFERENCE)
    monkeypatch.setattr(sources, "api_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("401")))
    srv.app.config["TESTING"] = True
    with srv.app.test_client() as c:
        r = c.get("/api/current?force=1")
    assert r.status_code == 502 and "error" in r.get_json() and "state" not in r.get_json()


def test_dotenv_drops_one_pair_of_matching_quotes():
    env = server_module.parse_dotenv(
        'AIRGRADIENT_TOKEN="abc"\n'
        "GOOGLE_POLLEN_API_KEY='k1'\n"
        'A="x\'\n'          # not a matching pair: kept as written
        'export B=plain\n'
        '# C=commented\n'
        'B=second\n')       # the first line for a key wins
    assert env == {"AIRGRADIENT_TOKEN": "abc", "GOOGLE_POLLEN_API_KEY": "k1", "A": "\"x'", "B": "plain"}


def test_airgradient_api_base_is_airgradients_unless_a_test_server_is_named(monkeypatch):
    """Production talks to AirGradient; AIRGRADIENT_API_BASE (simulated setups only) points the monitors' calls elsewhere."""
    import importlib, sys
    monkeypatch.delenv("AIRGRADIENT_API_BASE", raising=False)
    import server
    assert sources.API_BASE == "https://api.airgradient.com/public/api/v1"
    monkeypatch.setenv("AIRGRADIENT_API_BASE", "http://127.0.0.1:5696/public/api/v1/")
    sys.modules.pop("server", None)
    try:
        assert importlib.import_module("server").sources.API_BASE == "http://127.0.0.1:5696/public/api/v1"
    finally:
        monkeypatch.delenv("AIRGRADIENT_API_BASE")
        sys.modules.pop("server", None)
        importlib.import_module("server")
