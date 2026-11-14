"""Start at login, without Docker (where-it-runs spec): `setup.py --start-at-login on|off`.

On a Mac, a LaunchAgent starts the app when the person logs in and restarts it if it stops; on Linux, a systemd
user service does the same while they're logged in. Elsewhere it says so and changes nothing. The system commands
(`run`), `which`, the platform and the final check are passed in, so tests fake them."""
import os
import plistlib
import signal
import socket
import subprocess
import time
from pathlib import Path

LABEL = "io.github.sguyon.home-air-quality"   # the LaunchAgent's name, reverse-DNS as launchd expects
UNIT = "home-air-quality.service"              # the systemd user service's file name
PID_FILE = "app.pid"                           # server.py writes its pid here, in the repo folder
LOG_FILE = "app.log"                           # where the started app writes, in the repo folder
STOP_WAIT = 10                                 # seconds for setup's own copy to stop before the system starts it
STOP_POLL = 0.2                                # seconds between checks that it has stopped
RETRY_WAIT = 2                                 # seconds before launchd gets a second bootstrap, right after a bootout
PATH_TAIL = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"   # where uv or Python may live, after ~/.local/bin


def system(platform, which, run):
    """"launchd", "systemd" or "" (not available), with the reason when it's ""."""
    if platform == "darwin":
        return "launchd", ""
    if platform.startswith("linux"):
        if not which("systemctl"):
            return "", "this Linux has no systemd"
        if run(["systemctl", "--user", "show-environment"]) != 0:
            return "", "systemd's user services aren't running"
        return "systemd", ""
    return "", "it works on a Mac or on Linux with systemd"


def launchd_plist(root, home, port, host=None):
    env = {"PORT": str(port), "PATH": f"{home}/.local/bin:{PATH_TAIL}"}
    if host:
        env["HOST"] = host   # started with HOST=0.0.0.0 for a phone at home: it stays open to it
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": ["/bin/sh", str(root / "scripts" / "run.sh"), "server.py"],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(root / LOG_FILE),
        "StandardErrorPath": str(root / LOG_FILE),
        "EnvironmentVariables": env,
    }).decode()


def systemd_unit(root, port, host=None):
    return (
        "[Unit]\nDescription=Home Air Quality\n\n"
        "[Service]\n"
        f'WorkingDirectory="{root}"\n'
        f'ExecStart=/bin/sh "{root / "scripts" / "run.sh"}" server.py\n'
        f"Environment=PORT={port}\n"
        + (f"Environment=HOST={host}\n" if host else "") +
        "Restart=on-failure\n"
        f"StandardOutput=append:{root / LOG_FILE}\n"
        f"StandardError=append:{root / LOG_FILE}\n\n"
        "[Install]\nWantedBy=default.target\n"
    )


def plist_path(home):
    return home / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def unit_path(home):
    return home / ".config" / "systemd" / "user" / UNIT


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _is_ours(pid):
    """The pid is this app (a stale app.pid can name another program after a crash or a restart)."""
    out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    return "server.py" in out


def port_answers(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def stop_setup_copy(root):
    """Stop the copy setup started (its pid in app.pid), so two copies never fight over the port."""
    pid_file = root / PID_FILE
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return
    if _alive(pid) and _is_ours(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except PermissionError:
            return
        end = time.monotonic() + STOP_WAIT
        while _alive(pid) and time.monotonic() < end:
            time.sleep(STOP_POLL)
    pid_file.unlink(missing_ok=True)


def turn_on(root, home, env, run, which, platform, check):
    from setup import SETUP_CMD, START_CMD, port_from
    kind, reason = system(platform, which, run)
    if not kind:
        print(f"Start at login isn't available here ({reason}): keep the app running with {START_CMD} instead.")
        return 1
    port, host = port_from(env), env.get("HOST")
    uid = os.getuid()
    if kind == "launchd":   # already on: unload it first, or launchd restarts the copy the port check would see
        run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    else:
        run(["systemctl", "--user", "stop", UNIT])
    stop_setup_copy(root)
    if port_answers(port):
        print(f"Port {port} is busy (another copy of the app, or another program). Stop it, then run this again.")
        return 1
    if kind == "launchd":
        path = plist_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(launchd_plist(root, home, port, host))
        bootstrap = ["launchctl", "bootstrap", f"gui/{uid}", str(path)]
        loaded = run(bootstrap) == 0
        if not loaded:   # launchd may still be removing the previous one
            time.sleep(RETRY_WAIT)
            loaded = run(bootstrap) == 0
    else:
        path = unit_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(systemd_unit(root, port, host))
        loaded = all(run(cmd) == 0 for cmd in (["systemctl", "--user", "daemon-reload"],
                                               ["systemctl", "--user", "enable", UNIT],
                                               ["systemctl", "--user", "restart", UNIT]))
    if not loaded:
        print(f"The system didn't start it ({path}). Its log: {root / LOG_FILE}")
        return 1
    if check() != 0:
        print(f"It's set to start at login, but the page didn't answer. Its log: {root / LOG_FILE}")
        return 1
    print(f"It now starts by itself when you log in. To turn it off: {SETUP_CMD} --start-at-login off")
    return 0


def _folder_in(path):
    """The folder the start file points to, read back from it."""
    try:
        if path.suffix == ".plist":
            return Path(plistlib.loads(path.read_bytes())["WorkingDirectory"])
        for line in path.read_text().splitlines():
            if line.startswith("WorkingDirectory="):
                return Path(line.split("=", 1)[1].strip('"'))
    except (OSError, KeyError, ValueError, plistlib.InvalidFileException):
        pass
    return None


def turn_off(root, home, run, which, platform):
    kind, _ = system(platform, which, run)
    path = plist_path(home) if kind == "launchd" else unit_path(home) if kind == "systemd" else None
    moved = ""
    if path is not None and path.exists():
        folder = _folder_in(path)
        if folder is not None and not folder.exists():
            moved = f" (it pointed to {folder}, which no longer exists)"
        if kind == "launchd":
            run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
        else:
            run(["systemctl", "--user", "disable", "--now", UNIT])
        path.unlink()
        if kind == "systemd":
            run(["systemctl", "--user", "daemon-reload"])
    print(f"Start at login is off.{moved}")
    return 0
