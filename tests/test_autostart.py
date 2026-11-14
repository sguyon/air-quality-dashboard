"""Start at login (where-it-runs spec): a LaunchAgent on a Mac, a user service on Linux, no Docker.
The system commands, the health check and the platform are faked; the files are written under a temp home."""
import os
import plistlib
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import autostart  # noqa: E402


class Calls:
    """Records the system commands; every command succeeds unless its first words are in `fail` (`times` failures each)."""
    def __init__(self, fail=(), times=99):
        self.cmds, self.fail, self.left = [], fail, times

    def __call__(self, cmd):
        self.cmds.append(cmd)
        if any(cmd[:len(f)] == list(f) for f in self.fail) and self.left > 0:
            self.left -= 1
            return 1
        return 0


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def which(name):
    return f"/usr/bin/{name}"


def on(tmp_path, platform="darwin", run=None, check=lambda: 0, env=None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    run = run or Calls()
    code = autostart.turn_on(tmp_path / "repo", home, env or {"PORT": str(free_port())}, run, which, platform, check)
    return code, run, home


@pytest.fixture(autouse=True)
def repo(tmp_path, monkeypatch):
    (tmp_path / "repo").mkdir()
    monkeypatch.setattr(autostart, "RETRY_WAIT", 0)
    monkeypatch.setattr(autostart, "STOP_WAIT", 0.5)   # the test's own child stays a zombie until reaped, so the real wait would run in full (10 s)


def test_plist_starts_the_app_from_the_folder():
    plist = plistlib.loads(autostart.launchd_plist(Path("/x/a b"), Path("/h"), 5555).encode())
    assert plist["Label"] == autostart.LABEL
    assert plist["ProgramArguments"] == ["/bin/sh", "/x/a b/scripts/run.sh", "server.py"]
    assert plist["WorkingDirectory"] == "/x/a b"
    assert plist["RunAtLoad"] is True and plist["KeepAlive"] is True
    assert plist["EnvironmentVariables"]["PORT"] == "5555"
    assert plist["EnvironmentVariables"]["PATH"].startswith("/h/.local/bin:")
    assert plist["StandardOutPath"] == plist["StandardErrorPath"] == "/x/a b/app.log"


def test_unit_quotes_the_path():
    unit = autostart.systemd_unit(Path("/x/a b"), 5600)
    assert 'ExecStart=/bin/sh "/x/a b/scripts/run.sh" server.py' in unit
    assert "Environment=PORT=5600" in unit
    assert 'WorkingDirectory="/x/a b"' in unit
    assert "Restart=on-failure" in unit and "WantedBy=default.target" in unit


def test_on_mac_writes_and_loads_then_checks(tmp_path, capsys):
    checked = []
    code, run, home = on(tmp_path, check=lambda: checked.append(1) or 0)
    path = home / "Library" / "LaunchAgents" / f"{autostart.LABEL}.plist"
    assert code == 0 and path.exists()
    assert run.cmds[-1] == ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)]
    assert checked == [1]
    assert "It now starts by itself when you log in." in capsys.readouterr().out


def test_on_linux_enables_the_user_service(tmp_path):
    code, run, home = on(tmp_path, platform="linux")
    assert code == 0 and (home / ".config" / "systemd" / "user" / autostart.UNIT).exists()
    assert ["systemctl", "--user", "enable", autostart.UNIT] in run.cmds
    assert run.cmds[-1] == ["systemctl", "--user", "restart", autostart.UNIT]


def test_on_stops_setups_copy_first(tmp_path):
    copy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "server.py"])
    (tmp_path / "repo" / autostart.PID_FILE).write_text(str(copy.pid))
    try:
        code, run, _ = on(tmp_path)
        assert code == 0
        assert copy.wait(timeout=5) == -signal.SIGTERM
        assert not (tmp_path / "repo" / autostart.PID_FILE).exists()
    finally:
        if copy.poll() is None:
            copy.kill()


def test_on_twice_ends_the_same(tmp_path):
    assert on(tmp_path)[0] == 0
    code, _, home = on(tmp_path)
    assert code == 0
    assert len(list((home / "Library" / "LaunchAgents").iterdir())) == 1


def test_unknown_system_writes_nothing(tmp_path, capsys):
    code, run, home = on(tmp_path, platform="win32")
    assert code == 1 and run.cmds == []
    assert not any(home.rglob("*"))
    assert "Start at login isn't available here" in capsys.readouterr().out


def test_linux_without_user_services_writes_nothing(tmp_path, capsys):
    code, _, home = on(tmp_path, platform="linux", run=Calls(fail=[("systemctl", "--user", "show-environment")]))
    assert code == 1 and not any(home.rglob("*"))
    assert "Start at login isn't available here" in capsys.readouterr().out


def test_a_failed_check_says_so(tmp_path, capsys):
    code, _, _ = on(tmp_path, check=lambda: 1)
    assert code == 1
    assert "It now starts by itself" not in capsys.readouterr().out


def test_off_when_not_on(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    assert autostart.turn_off(tmp_path / "repo", home, Calls(), which, "darwin") == 0
    assert "Start at login is off." in capsys.readouterr().out


def test_off_removes_it_and_notices_a_moved_folder(tmp_path, capsys):
    _, _, home = on(tmp_path)
    (tmp_path / "repo").rename(tmp_path / "moved")
    run = Calls()
    assert autostart.turn_off(tmp_path / "moved", home, run, which, "darwin") == 0
    assert not any((home / "Library" / "LaunchAgents").iterdir())
    assert run.cmds[0] == ["launchctl", "bootout", f"gui/{os.getuid()}/{autostart.LABEL}"]
    out = capsys.readouterr().out
    assert "Start at login is off." in out and "no longer exists" in out


@pytest.mark.xdist_group("app-pid")   # shares the repo's app.pid with test_startup's run of server.py; one worker runs both
def test_server_writes_and_removes_its_pid():
    pid_file = ROOT / autostart.PID_FILE
    if pid_file.exists():
        pytest.skip("an app is running from this folder")
    env = {**os.environ, "DEMO": "1", "PORT": str(free_port())}
    app = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if pid_file.exists():
                break
            time.sleep(0.1)
        assert pid_file.read_text().strip() == str(app.pid)
        app.terminate()
        app.wait(timeout=10)
        assert not pid_file.exists()
    finally:
        if app.poll() is None:
            app.kill()


def test_setup_command_dispatches(monkeypatch, tmp_path):
    import setup
    seen = []
    monkeypatch.setattr(autostart, "turn_on", lambda root, home, env, run, which, platform, check: seen.append(("on", root)) or 0)
    monkeypatch.setattr(autostart, "turn_off", lambda root, home, run, which, platform: seen.append(("off", root)) or 0)
    assert setup.main(["--start-at-login", "on"], {}, tmp_path) == 0
    assert setup.main(["--start-at-login", "off"], {}, tmp_path) == 0
    assert seen == [("on", tmp_path), ("off", tmp_path)]


def test_a_busy_port_stops_before_writing(tmp_path, capsys):
    # review, Important 1: no app.pid but the port taken (setup's copy, or another program): say so, change nothing
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        code, run, home = on(tmp_path, env={"PORT": str(port)})
    assert code == 1 and not any(home.rglob("*")) and not any(c[:2] == ["launchctl", "bootstrap"] for c in run.cmds)
    assert f"Port {port} is busy" in capsys.readouterr().out


def test_a_stale_pid_of_another_program_is_left_alone(tmp_path):
    # review, Important 2: app.pid outlived the app and its number now belongs to something else
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    (tmp_path / "repo" / autostart.PID_FILE).write_text(str(other.pid))
    try:
        assert on(tmp_path)[0] == 0
        assert other.poll() is None
    finally:
        other.kill()


def test_a_pid_owned_by_the_system_is_left_alone(tmp_path):
    (tmp_path / "repo" / autostart.PID_FILE).write_text("1")
    assert on(tmp_path)[0] == 0


def test_host_carries_over(tmp_path):
    # review, Important 3: started with HOST=0.0.0.0 for the phone, it stays open to it after the system takes over
    plist = plistlib.loads(autostart.launchd_plist(Path("/x"), Path("/h"), 5555, "0.0.0.0").encode())
    assert plist["EnvironmentVariables"]["HOST"] == "0.0.0.0"
    assert "Environment=HOST=0.0.0.0" in autostart.systemd_unit(Path("/x"), 5555, "0.0.0.0")
    assert "HOST" not in plistlib.loads(autostart.launchd_plist(Path("/x"), Path("/h"), 5555).encode())["EnvironmentVariables"]
    code, _, home = on(tmp_path, env={"PORT": str(free_port()), "HOST": "0.0.0.0"})
    assert plistlib.loads(autostart.plist_path(home).read_bytes())["EnvironmentVariables"]["HOST"] == "0.0.0.0"


def test_a_slow_bootout_is_retried(tmp_path):
    # review, Minor 2 graded up (the plan's "on twice" case): launchd can refuse a bootstrap right after a bootout
    run = Calls(fail=[("launchctl", "bootstrap")], times=1)
    code, run, _ = on(tmp_path, run=run)
    assert code == 0
    assert sum(c[:2] == ["launchctl", "bootstrap"] for c in run.cmds) == 2


@pytest.mark.parametrize("platform, unload", [("darwin", ["launchctl", "bootout"]), ("linux", ["systemctl", "--user", "stop"])])
def test_on_again_unloads_the_running_one_before_the_port_check(tmp_path, platform, unload):
    # on twice for real: the system's own copy holds the port and would restart if only killed; unloading it frees it
    held = socket.socket()
    held.bind(("127.0.0.1", 0))
    held.listen()
    port = held.getsockname()[1]

    class Freeing(Calls):
        def __call__(self, cmd):
            if cmd[:len(unload)] == unload:
                held.close()
            return super().__call__(cmd)
    try:
        code, _, _ = on(tmp_path, platform=platform, run=Freeing(), env={"PORT": str(port)})
        assert code == 0
    finally:
        held.close()
