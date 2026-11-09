# Deployment

How to put your copy online, so the page works on your phone away from home. Set it up locally first ([`SETUP.md`](SETUP.md)): you need a `config.toml` that passes `uv run --with-requirements requirements.txt scripts/check_config.py` (or `python scripts/check_config.py` in a virtualenv) and a token in `.env`.

Each method says when it was last tested from a fresh copy.

## Railway

Railway is the method the maintainer uses, and the most tested one. Docker is below.

[Railway](https://railway.com) builds the app from this folder's `Dockerfile` (gunicorn, on the port Railway gives it). Your agent can run every step except the ones marked "you".

**Size:** measured on the maintainer's home (Nov 2026): about 100 MB of memory and almost no CPU, so one household fits easily in Railway's Hobby plan. Railway's free trial is enough to try it; its ongoing free allowance may not cover a service that runs all month. Railway's [plans page](https://docs.railway.com/reference/pricing/plans) has the current terms.

**Where the settings go:** `railway up` skips the files in `.gitignore`, so neither `config.toml` nor `.env` is uploaded. The settings go into Railway variables instead: `CONFIG_TOML` holds the whole `config.toml`, and each key is its own variable.

1. **You:** install the [Railway CLI](https://docs.railway.com/guides/cli) and sign in with `railway login` (it opens a browser).
2. Create a project and a service, from the repo folder:

   ```bash
   railway init --name home-air
   railway add --service home-air
   ```

3. Send the config:

   ```bash
   railway variable set CONFIG_TOML --stdin --service home-air --skip-deploys < config.toml
   ```

   Railway variables can hold several lines, and `--stdin` keeps them all (checked 2026-11-09; only the final newline is dropped, which doesn't matter). If the page doesn't answer after a deploy, run `railway logs` and look for the config message.

4. **You:** send the token, in your own terminal, from the repo folder. It reads the value from `.env` and never shows it:

   ```bash
   grep '^AIRGRADIENT_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d '\r\n' \
     | railway variable set AIRGRADIENT_TOKEN --stdin --service home-air --skip-deploys
   ```

   The same for `GOOGLE_POLLEN_API_KEY` if you set one up. Or type the values in the Railway dashboard: your service → Variables.

5. Deploy:

   ```bash
   railway up --service home-air --detach
   ```

   Set a healthcheck path, so a deploy that fails to start never replaces a working one:

   ```bash
   railway environment edit --service-config home-air deploy.healthcheckPath /health
   ```

   Untested: in a 2026-11-09 test, `railway environment edit` answered "No changes to apply" to every value. If it does, set it in the dashboard instead: the service's Settings → Deploy → Healthcheck Path.

6. Give it an address:

   ```bash
   railway domain --service home-air
   ```

   This creates a public `*.up.railway.app` address. Anyone who has it can open the page and see your readings and your home's rounded location (about 1 km). The page tells search engines not to index it, but keep the address to yourself.

**Updating:**

- After changing `config.toml`: run step 3 again without `--skip-deploys`; Railway redeploys with the new config.
- After pulling new code: `railway up --service home-air --detach`.
- To check on it: `railway logs --service home-air`.

**A second, test copy (optional):** a second service with `APP_ENV=preview` marks its tab, icon and title "PREVIEW" so you can't mix it up with your real page. Without `APP_ENV` a deployment is treated as the real one.

**Tip: one token for several services.** If you run more than one service (say a test and a live one), set `AIRGRADIENT_TOKEN` once under Railway's Project Settings → Shared Variables, and use it from each service. Change it there when you renew the token.

## Docker

Docker: tested on 2026-11-09 with Colima on macOS (arm64, Docker 29.5, Compose 5.7), from a fresh copy. The published image, amd64 and a Linux host aren't tested yet.

For a home server or NAS that already runs Docker. The page runs on your network only; it is not online. Your agent can run every step except the ones marked "you".

**Size:** the image is about 230 MB. The demo used about 50 MB of memory.

**Where the settings go:** `docker-compose.yml` reads two files from its own folder. Neither goes into the image.

- `config.toml`, next to `docker-compose.yml`. Required: Compose mounts it read-only at `/config/config.toml`, and stops with "bind source path does not exist: …/config.toml" if it's missing. The container runs as its own user (uid 10001), so on Linux the file must be readable by others (`chmod 644 config.toml`).
- `.env`, next to `docker-compose.yml`, with `AIRGRADIENT_TOKEN` (and `GOOGLE_POLLEN_API_KEY` if you set one up). Optional for Compose, but without a token there are no readings.

**Try the demo first (optional):** the image with nothing mounted opens the demo, no files needed.
```bash
 docker run --rm -p 127.0.0.1:8000:8000 ghcr.io/sguyon/home-air-quality
```

Then open http://localhost:8000; Ctrl-C stops it. From a copy of this repo, `docker build -t home-air-quality .` and run `home-air-quality` instead.

### From this repo (builds the image on your machine)

1. **You:** install Docker with Compose 2.24 or newer (Docker Desktop, or Colima on a Mac: `brew install colima docker docker-compose`, then `colima start`). With Colima, keep the repo inside your home folder: Colima only shares that folder with its containers by default.
2. Set it up as in [`SETUP.md`](SETUP.md), so `config.toml` and `.env` sit in the repo folder.
3. Check the config inside the container (must end with "Config OK"):
   ```bash
    docker compose run --rm home-air-quality python scripts/check_config.py
   ```
4. Start it:
   ```bash
    docker compose up -d
   ```

    Then open http://localhost:8000. `docker compose ps` shows "healthy" once `/health` answers.

### From the published image (no build, amd64 and arm64)

The image `ghcr.io/sguyon/home-air-quality:latest` is built from `main`, for amd64 and arm64 (a Raspberry Pi with a 64-bit system). You don't need the repo, only three files in one folder on the server:

1. [`docker-compose.yml`](docker-compose.yml) from this repo. Delete its `build: .` line and uncomment `image: ghcr.io/sguyon/home-air-quality:latest`.
2. Your `config.toml` (made with [`SETUP.md`](SETUP.md) on any computer).
3. `.env` with your token.

Then `docker compose up -d` in that folder, and open http://localhost:8000 on that machine.

### Open it to your network

By default only the machine running it can open the page (`127.0.0.1:8000:8000`). To open it from a phone on the same network, change the port line in `docker-compose.yml` to `"8000:8000"`, run `docker compose up -d`, and open `http://<the server's address>:8000`.

Anyone on your network can then see your readings and your home's rounded location. There is no password and no HTTPS. Don't forward the port on your router: to reach it from outside, use a method in this file instead, or a VPN to your home.

### Updating

- After changing `config.toml` or `.env`: `docker compose up -d --force-recreate`.
- After pulling new code (built here): `git pull`, then `docker compose up -d --build`.
- With the published image: `docker compose pull`, then `docker compose up -d`.
- To check on it: `docker compose logs`. If the config has a problem, the server prints it there and stops; Docker restarts it with growing delays (`restart: unless-stopped`) until you fix the file and run `docker compose up -d --force-recreate`.

### Without Compose

```bash
 docker build -t home-air-quality .
 docker run -d --name home-air-quality --restart unless-stopped -p 127.0.0.1:8000:8000 \
   -v "$PWD/config.toml":/config/config.toml:ro --env-file .env home-air-quality
```

`--env-file .env` fails if `.env` is missing: drop that flag when there is no `.env`. Run it from the folder that holds `config.toml`; if that file is missing, `-v` creates an empty folder in its place, so check it's there first.

## Where the config lives

`config.toml` is never in this repo (it holds your home's location). The server looks for it in this order:

| Variable | Use it when |
|---|---|
| `CONFIG_TOML` | The host has no files of yours, like Railway building from this public repo: the variable holds the file's contents. Set it from your local file (`railway variable set CONFIG_TOML --stdin < config.toml`); edit the file, not the variable. |
| `CONFIG_FILE` | The file sits somewhere else on the machine: a path to it. A file that can't be read stops the server. |
| *(none)* | `config.toml` at the repo root: running locally, with Docker (compose mounts it), or deploying from your own private copy of the repo where you committed it with `git add -f config.toml`. |

Keys never go in the config file; they stay in `.env` or your host's variables.

## The demo on Vercel

The public demo runs on Vercel (`vercel.json`), with no keys. `DEMO=1` is set in the Vercel project's environment variables, not in `vercel.json`: a new Vercel project needs it added there. Live data isn't tested there: the server refreshes your monitors' readings in the background, and that hasn't been tried on Vercel's functions.

## Add your method

Deployed it another way (Docker, a Raspberry Pi, Fly.io, Render…)? Keep the steps in your own copy, or send a pull request that adds a section here. Head it with when it was last tested from a fresh copy, and keep keys out of every command and screenshot.
