# Agent rules

Rules for any coding agent working in this repo. `CLAUDE.md` is a link to this file.

If `internal/AGENTS.local.md` exists, read it: it holds the maintainer's private rules.

## Setting it up or deploying

- Setting it up for someone's home: follow [`SETUP.md`](SETUP.md).
- Putting it online: follow [`DEPLOYMENT.md`](DEPLOYMENT.md).
- Do the steps yourself when a command can (the `railway` CLI, `gcloud`, `gh`), and say so before listing any manual click-path: the user may act on a list right away. Each command that changes a live service or account needs the user's OK first, and manual steps are the fallback. Never ask the user to do by hand what a command can do.

## After changing config.toml

The deployed copy doesn't follow the local file by itself. After every edit:

1. Check it: `uv run --with-requirements requirements.txt scripts/check_config.py` (must end with "Config OK").
2. Update every deployed copy, with the user's OK (it changes a live service):
   - Railway (reads `CONFIG_TOML`): `railway variable set CONFIG_TOML --stdin --service <service> < config.toml`, once per service. Add `--skip-deploys` to apply it at the next deploy instead of now.
   - Docker (mounts the file): restart the container (`docker compose restart`).
3. Confirm the deployed copy matches the file without printing it: compare `railway variable list --service <service> --json`'s `CONFIG_TOML` with the local file after stripping the ends (Railway drops the final newline; `--stdin` keeps every other line, checked 2026-11-09).

If the maintainer's private rules (`internal/AGENTS.local.md`) list services, update all of them.

## Keys

- Never read, print or `cat` `.env` or `.env.*`. Repo settings deny it to Claude Code; every other agent follows this line.
- Never ask the user to paste a key into the chat. The user types keys into `.env` themselves, or a command writes them there without showing them (see `SETUP.md`).
- `scripts/check_config.py` says whether each key is set, never its value. Use it instead of looking.
- Never commit `config.toml`, `.env*` or real readings. `config.toml` and `.env*` are gitignored, and CI fails a PR that adds them.

## Layout

- `server.py`: the Flask app. Fetches the monitors and the outside sources, caches them, serves the page and its JSON.
- `summary.py`: the rules that pick the actions, the profiles' states and the day chart's data. No network.
- `phrases.py`: the sentences behind each explanation, filled from the readings and the limits.
- `config.py`: reads `config.toml` (or the `CONFIG_TOML` or `CONFIG_FILE` variable) and checks it. `config.example.toml` is the commented starter.
- `index.html` and `static/`: the page, with no build step. `app.js` (data, readings, charts), `summary.js` (the summary card), `home.js` (the home's profiles and road in words), `sky.js` (the live sky), `map.js` (the neighborhood map), `picker.js` (the demo's banner and its monitor picker).
- `publicmap.py`: AirGradient's public monitors for any home or the demo: the outdoor ones in the world list, the nearest, the outdoor source an indoor-only home is offered at setup, a monitor's reading row, its place on the public map and its history there. No import of `demo/` or `server.py`.
- `demo/`: the demo's home (`config.toml`), its made-up data (`data.py`), its three moments and three hidden one-monitor cases (`moments.py`) and the public monitors' pages at `?monitor=<id>` (`public.py`).
- `scripts/`: `check_config.py`, `screenshot.sh` (the README's images, from the demo), `vercel_build.sh` (the demo's build on Vercel).
- `Dockerfile`, `docker-compose.yml` and `.dockerignore`: the container (DEPLOYMENT.md, "Docker"). `.github/workflows/image.yml` publishes the image to `ghcr.io/sguyon/home-air-quality` from `main`.
- `tests/`: Python tests (pytest) and page tests (`*.test.mjs`, Node's test runner).

## Run

```bash
uv run --with-requirements requirements.txt server.py
```

Then http://localhost:5555 (`PORT` changes the port). Without uv: a virtualenv with `pip install -r requirements.txt`, then `python server.py`. Python 3.11 or newer. `DEMO=1` runs the demo whatever the config.

## Test

```bash
pytest -q && node --test tests/
```

Both must pass before a commit.

## The demo moments are the test fixtures

The demo's three moments (`demo/moments.py`: `rush`, `clear`, `humid`, at `?moment=`) are made-up data tuned so the rules tell each story, and `tests/test_demo.py` pins what each one says. A change to the page or the rules that changes a story updates the moments and their tests in the same commit, so the demo keeps showing what the app does. Three hidden moments (`indoor-near`, `indoor-model`, `outdoor-only`) cover homes with one monitor and are pinned the same way; they're reachable only at `?moment=`, not in the banner. `scripts/screenshot.sh` takes the README's images from the demo.

## Numbers

- A threshold a household would tune lives in `config.toml`: `[limits]`, and `[home] appliances` for what dries a damp room. Its default is in `config.py` (`DEFAULT_LIMITS`, `APPLIANCES`), and `config.example.toml` says what it does.
- Every other tuning number is a named constant at the top of its module, with a one-line comment: what it is, its unit, and why that value.
- Never put an unnamed threshold in the middle of a function. Keyword arguments that name themselves (`ttl=600`, `timeout=15`) are fine.
- The same in `static/*.js`: a number that means one of the config's limits reads `APP.limits` (or a helper in `home.js` that takes it), never a copy. A display scale that isn't a limit (an AQI band edge, a ring's full scale) is a named constant at the top of its file with a comment.

## Copy

- Plain and factual, no marketing.
- What the page tells you to do is an **action**, each with a why. Not advice, a recommendation or a tip.
- **Profiles** are ready-made types of person a home picks from (toddler, sinus & allergy, runner): `[profiles]` in `config.toml`. Say "the profiles that match your home"; when saying how the air suits them, talk about the person ("whether the air suits each of them"), not the profile. Never call them "needs" (the old name).
