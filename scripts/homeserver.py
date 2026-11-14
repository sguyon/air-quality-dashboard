"""`setup.py --home-server` (where-it-runs spec, "A home server"): setup stays on this computer, where the token page
works; this prepares a folder with what a home server needs to run the app with Docker (the Compose file using the
published image, the settings and the token) and says the two steps to run there. The agent doesn't copy it over SSH."""
import os
import shutil
from pathlib import Path

IMAGE = "ghcr.io/sguyon/home-air-quality:latest"   # published from main by .github/workflows/image.yml
FOLDER = "home-server"                             # prepared in the repo folder; gitignored (it holds a copy of .env)
SERVER_PORT = 8000                                 # the image's port (Dockerfile), opened to the home network

COMPOSE = f"""# Home Air Quality on a home server. In this folder: docker compose up -d
# Then open http://<this server>:{SERVER_PORT} from any device at home. Anyone on the home network can see the page.
# Prepared by scripts/setup.py --home-server: config.toml and .env sit next to this file; keep them private.
services:
  home-air-quality:
    image: {IMAGE}
    ports:
      - "{SERVER_PORT}:{SERVER_PORT}"
    volumes:
      - type: bind
        source: ./config.toml
        target: /config/config.toml
        read_only: true
        bind:
          create_host_path: false
    env_file: .env
    restart: unless-stopped
"""


def compose_text():
    return COMPOSE


def prepare(root):
    from config import ENV_FILE_MODE, ConfigError, env_key, load_config
    from setup import HOME_CMD, START_CMD, saved_keys
    try:
        cfg = load_config({}, root)
    except ConfigError as e:
        print(f"config.toml has a problem ({e}). Fix it first: {HOME_CMD}")
        return 1
    if cfg is None:
        print(f"There's no config.toml yet. Set up the home first: {HOME_CMD}")
        return 1
    if not env_key("AIRGRADIENT_TOKEN", saved_keys(root)):
        print(f"There's no AirGradient token in .env yet. Start the app and save it on its page first: {START_CMD}")
        return 1
    folder = root / FOLDER
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    (folder / "docker-compose.yml").write_text(compose_text())
    shutil.copyfile(root / "config.toml", folder / "config.toml")
    env = folder / ".env"
    fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, ENV_FILE_MODE)
    with os.fdopen(fd, "wb") as out:
        out.write((root / ".env").read_bytes())
    env.chmod(ENV_FILE_MODE)
    print(f"Prepared {folder} for a home server with Docker.")
    print(f"1. Copy the {FOLDER} folder to your server, keeping .env private, for example: scp -rp {FOLDER} you@your-server:")
    print(f"2. On the server, in the {FOLDER} folder: docker compose up -d")
    print(f"Then open http://your-server:{SERVER_PORT} from any device at home.")
    return 0
