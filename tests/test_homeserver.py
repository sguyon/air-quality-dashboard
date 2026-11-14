"""setup.py --home-server (where-it-runs spec, "A home server"): a folder with the Compose file, the settings and the
token, and the two steps to run on the server. Setup itself stays on the person's computer."""
import shutil
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import homeserver  # noqa: E402
from config import ENV_FILE_MODE  # noqa: E402

CONFIG = ('[place]\nname = "Test home"\nlat = 40.72\nlon = -73.95\ntimezone = "America/New_York"\n'
          'indoor = "Bedroom"\noutdoor = "Balcony"\n')
TOKEN = "tok_secret_123"
STEPS = ["1. Copy the home-server folder to your server, keeping .env private, for example: scp -rp home-server you@your-server:",
         "2. On the server, in the home-server folder: docker compose up -d",
         "Then open http://your-server:8000 from any device at home."]


@pytest.fixture
def root(tmp_path):
    (tmp_path / "config.toml").write_text(CONFIG)
    env = tmp_path / ".env"
    env.write_text(f"AIRGRADIENT_TOKEN={TOKEN}\n")
    env.chmod(ENV_FILE_MODE)
    return tmp_path


def test_writes_three_files(root):
    assert homeserver.prepare(root) == 0
    folder = root / homeserver.FOLDER
    assert sorted(p.name for p in folder.iterdir()) == [".env", "config.toml", "docker-compose.yml"]
    compose = (folder / "docker-compose.yml").read_text()
    assert "image: ghcr.io/sguyon/home-air-quality:latest" in compose
    assert '- "8000:8000"' in compose
    assert "restart: unless-stopped" in compose
    assert "target: /config/config.toml" in compose and "read_only: true" in compose
    assert (folder / "config.toml").read_text() == CONFIG


def test_env_copy_is_private(root, capsys):
    homeserver.prepare(root)
    env = root / homeserver.FOLDER / ".env"
    assert stat.S_IMODE(env.stat().st_mode) == ENV_FILE_MODE
    assert TOKEN in env.read_text()
    assert TOKEN not in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["config.toml", ".env"])
def test_stops_without_token_or_config(root, missing, capsys):
    (root / missing).unlink()
    assert homeserver.prepare(root) == 1
    assert not (root / homeserver.FOLDER).exists()
    assert capsys.readouterr().out.strip()


def test_second_run_replaces_the_folder(root):
    homeserver.prepare(root)
    (root / homeserver.FOLDER / "stray.txt").write_text("old")
    assert homeserver.prepare(root) == 0
    assert not (root / homeserver.FOLDER / "stray.txt").exists()
    assert stat.S_IMODE((root / homeserver.FOLDER / ".env").stat().st_mode) == ENV_FILE_MODE


def test_prints_the_two_steps(root, capsys):
    homeserver.prepare(root)
    out = capsys.readouterr().out.splitlines()
    positions = [out.index(line) for line in STEPS]
    assert positions == sorted(positions)


def test_setup_command_dispatches(root, monkeypatch):
    import setup
    seen = []
    monkeypatch.setattr(homeserver, "prepare", lambda r: seen.append(r) or 0)
    assert setup.main(["--home-server"], {}, root) == 0
    assert seen == [root]


def test_compose_works_with_older_compose():
    # review, Minor 7 graded up: the long env_file syntax needs Compose 2.24, which some NAS boxes may not have
    text = homeserver.compose_text()
    assert "env_file: .env" in text and "required:" not in text
