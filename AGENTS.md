# AGENTS.md

## Cursor Cloud specific instructions

This is a small single-service app: a Flask proxy server (`server.py`) that serves a
single static frontend (`index.html`, vanilla JS + Chart.js from CDN) and proxies to the
AirGradient and Anthropic APIs. There is no database, no build step, and no Node/frontend
tooling. Dependencies are Python only (`requirements.txt`), installed into a `.venv`
(the update script keeps this in sync).

### Running the server
- Run it via gunicorn (matches the `Procfile`):
  `.venv/bin/gunicorn server:app --bind 0.0.0.0:5555 --reload`
  (`--reload` gives dev-style hot reload). Default port is `5555`; override with `PORT`.
- Do NOT use the README's `python server.py`: the `__main__` block references an undefined
  `ANTHROPIC_API_KEY` name (line ~177) and crashes with `NameError`. gunicorn imports
  `server:app` and never executes that block, so it works fine. (This is a pre-existing
  code bug, not an environment problem.)

### Secrets / behavior without them
- Secrets are read from a `.env` file in the repo root (gitignored) or from real env vars:
  `AIRGRADIENT_TOKEN` (required for the main dashboard data), `ANTHROPIC_API_KEY` (optional,
  enables the "Analyze with AI" button), `PORT` (optional).
- Prefer the `.env` file: injected/exported secret env vars do NOT reliably reach a server
  launched inside a tmux session (the tmux daemon starts with a stripped environment), so
  write a gitignored `.env` (`printf 'AIRGRADIENT_TOKEN=%s\n' "$AIRGRADIENT_TOKEN" > .env`,
  same for `ANTHROPIC_API_KEY`) and restart gunicorn; `server.py` loads it at import time.
  Verify with `curl -s localhost:5555/health` (both `*_set` flags should be `true`).
- `AIRGRADIENT_TOKEN` is tied to a private AirGradient account. Without it, `/api/current`
  and `/api/history/<id>` return upstream 401. Because the frontend's `refresh()` calls
  `/api/current` and `/api/neighborhood` together in a single `Promise.all`, a missing token
  makes the ENTIRE dashboard body stay in the skeleton/"Connecting..." state (nothing renders).
- `/api/neighborhood` needs no token (it hits AirGradient's public world endpoint) and
  returns real live data — useful for verifying the proxy works end-to-end without any secret.
- `/health` reports which tokens are set and always works.
- The frontend loads Chart.js from a CDN, so browser charts need outbound internet access.

### Quick verification
- `curl -s localhost:5555/health` and `curl -s localhost:5555/api/neighborhood` are the
  fastest ways to confirm the server + proxy are healthy without any secrets.
