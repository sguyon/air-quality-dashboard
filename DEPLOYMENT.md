# Deployment

How to put your copy online, so the page works on your phone away from home. Set it up locally first ([`SETUP.md`](SETUP.md)): you need a `config.toml` that passes `uv run --with-requirements requirements.txt scripts/check_config.py` (or `python scripts/check_config.py` in a virtualenv) and a token in `.env`.

Each method says who maintains it and when it was last tested from a fresh copy. Railway is the only one for now.

## Railway

Maintained by Sacha. Last tested: not yet.

[Railway](https://railway.com) runs the app from this folder with the `Procfile` (gunicorn) and the Python version in `.python-version`. Your agent can run every step except the ones marked "you".

**Cost:** the Hobby plan is $5 a month and includes $5 of usage. Railway also has a Free plan ($1 of usage a month) and a one-time $5 trial for new accounts (Railway's [plans page](https://docs.railway.com/reference/pricing/plans)). How much of that the app uses isn't measured here.

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

   Railway variables can hold several lines (a pasted config kept all its lines on 2026-11-09). That `--stdin` does too is to be confirmed on the first `--stdin` deploy: if the page doesn't answer, run `railway logs` and look for the config message, then paste the file into the dashboard instead (your service → Variables → `CONFIG_TOML`).

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

## Where the config lives

`config.toml` is never in this repo (it holds your home's location). The server looks for it in this order:

| Variable | Use it when |
|---|---|
| `CONFIG_TOML` | The host has no files of yours, like Railway building from this public repo: the variable holds the file's contents. Set it from your local file (`railway variable set CONFIG_TOML --stdin < config.toml`); edit the file, not the variable. |
| `CONFIG_FILE` | The file sits somewhere else, like a Docker volume (`CONFIG_FILE=/config/config.toml`). |
| *(none)* | `config.toml` at the repo root: running locally, or deploying from your own private copy of the repo where you committed it with `git add -f config.toml`. |

Keys never go in the config file; they stay in `.env` or your host's variables.

## The demo on Vercel

The public demo runs on Vercel (`vercel.json`), with no keys. `DEMO=1` is set in the Vercel project's environment variables, not in `vercel.json`: a new Vercel project needs it added there. Live data isn't tested there: the server refreshes your monitors' readings in the background, and that hasn't been tried on Vercel's functions.

## Add your method

Deployed it another way (Docker, a Raspberry Pi, Fly.io, Render…)? Keep the steps in your own copy, or send a pull request that adds a section here. Head it with who maintains it and when it was last tested from a fresh copy, like the Railway section, and keep keys out of every command and screenshot.
