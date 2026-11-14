"""scripts/run.sh: the uv ladder (where-it-runs spec). uv already there, else install uv, else Python 3.11+ in .venv,
else a plain stop. Each test runs a copy of the script with fake programs on a minimal PATH."""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = ("Setup needs uv or Python 3.11 or newer, and neither could be found or installed. "
        "Install uv (https://docs.astral.sh/uv/getting-started/installation/), then run this again.")


def fake(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


def stage(tmp_path, name="repo"):
    """A repo copy with the script, the requirements and an empty fake bin; HOME and the call log in tmp_path."""
    repo = tmp_path / name
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "run.sh", repo / "scripts" / "run.sh")
    (repo / "requirements.txt").write_text("flask\n")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for tool in ("sh", "cksum"):   # the only outside programs the script may use, besides the fakes
        os.symlink(shutil.which(tool), bin_ / tool)
    home = tmp_path / "home"
    home.mkdir()
    return repo, bin_, home, tmp_path / "calls.log"


def recorder(log, name):
    return f'echo "{name} $*" >> "{log}"\n'


def run(repo, bin_, home, *args):
    env = {"PATH": str(bin_), "HOME": str(home)}
    return subprocess.run(["/bin/sh", str(repo / "scripts" / "run.sh"), *args], env=env, capture_output=True, text=True, timeout=30)


def calls(log):
    return log.read_text().splitlines() if log.exists() else []


UV_ARGS = "run --python 3.12 --with-requirements requirements.txt python hello.py --x"


def test_uses_uv_on_the_path(tmp_path):
    repo, bin_, home, log = stage(tmp_path)
    fake(bin_ / "uv", recorder(log, "uv"))
    r = run(repo, bin_, home, "hello.py", "--x")
    assert r.returncode == 0, r.stderr
    assert calls(log) == [f"uv {UV_ARGS}"]
    assert "Using uv." in r.stderr


def test_uses_uv_in_local_bin_when_not_on_the_path(tmp_path):
    repo, bin_, home, log = stage(tmp_path)
    fake(home / ".local" / "bin" / "uv", recorder(log, "uv"))
    r = run(repo, bin_, home, "hello.py", "--x")
    assert r.returncode == 0, r.stderr
    assert calls(log) == [f"uv {UV_ARGS}"]


def test_installs_uv_when_missing(tmp_path):
    repo, bin_, home, log = stage(tmp_path)
    uv = home / ".local" / "bin" / "uv"
    # the fake installer, as curl would download it: it writes uv where the real one does
    installer = tmp_path / "install.sh"
    installer.write_text(f"/bin/mkdir -p '{uv.parent}'\n"
                         f"printf '#!/bin/sh\\necho \"uv $*\" >> \"{log}\"\\n' > '{uv}'\n"
                         f"/bin/chmod +x '{uv}'\n")
    fake(bin_ / "curl", recorder(log, "curl") + f"/bin/cat '{installer}'\n")
    r = run(repo, bin_, home, "hello.py", "--x")
    assert r.returncode == 0, r.stderr
    assert calls(log)[0].startswith("curl -LsSf https://astral.sh/uv/install.sh")
    assert calls(log)[-1] == f"uv {UV_ARGS}"
    assert "Installed uv." in r.stderr


def python_fake(bin_, name, log, minor):
    """A python that answers the version check, makes a venv whose python records its calls."""
    venv_py = '#!/bin/sh\\necho "venv-python $*" >> "' + str(log) + '"\\n'
    fake(bin_ / name,
         recorder(log, name)
         + f'if [ "$1" = "-c" ]; then [ {minor} -ge 11 ]; exit $?; fi\n'
         + 'if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then /bin/mkdir -p "$3/bin"; printf \'' + venv_py + '\' > "$3/bin/python"; '
           '/bin/chmod +x "$3/bin/python"; fi\n')


def test_falls_back_to_python_311(tmp_path):
    repo, bin_, home, log = stage(tmp_path)
    fake(bin_ / "curl", "exit 6\n")   # uv's site can't be reached
    python_fake(bin_, "python3.11", log, 11)
    r = run(repo, bin_, home, "hello.py", "--x")
    assert r.returncode == 0, r.stderr
    venv_calls = [c for c in calls(log) if c.startswith("venv-python")]
    assert venv_calls == ["venv-python -m pip install -q -r requirements.txt", "venv-python hello.py --x"]
    assert list((repo / ".venv").glob(".requirements-*"))
    assert "Using python3.11 in .venv." in r.stderr


def test_skips_python_older_than_311(tmp_path):
    repo, bin_, home, log = stage(tmp_path)
    fake(bin_ / "curl", "exit 6\n")
    python_fake(bin_, "python3", log, 9)
    r = run(repo, bin_, home, "hello.py")
    assert r.returncode == 1
    assert r.stderr.strip() == STOP
    assert not (repo / ".venv").exists()


def test_path_with_a_space(tmp_path):
    repo, bin_, home, log = stage(tmp_path, name="a b")
    fake(bin_ / "uv", recorder(log, "uv"))
    r = run(repo, bin_, home, "hello.py", "--x")
    assert r.returncode == 0, r.stderr
    assert calls(log) == [f"uv {UV_ARGS}"]


def test_setup_prints_commands_through_the_launcher():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import setup
    assert setup.SETUP_CMD == "scripts/run.sh scripts/setup.py"
    assert setup.SERVER_CMD == "scripts/run.sh server.py"
    assert not hasattr(setup, "UV")
