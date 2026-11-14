# Deployment

For access away from home, use Railway. For a home server or NAS, use Docker Compose. Only Railway and Docker are tested: another host that runs a container (Fly.io, Render, a VPS) can build from the `Dockerfile` with the same settings, but it is untested and these steps don't cover it. Keep `config.toml` and `.env` private. Agents run commands themselves and ask before each change to a live service or account.

## Railway

Railway builds from this repo's `Dockerfile`. There is no login on the page: anyone with its address can see the readings and the home's rounded location (about 1 km). Keep the address private; telling search engines not to index it is not access control.

Prepare `config.toml` with [SETUP.md](SETUP.md). The helper below needs uv and Python 3.12 (`uv run --python 3.12` fetches Python itself); check `uv --version`. Install the [Railway CLI](https://docs.railway.com/guides/cli); the user signs in with `railway login` (`railway whoami` shows who).

`railway init` links the current folder to the new project, and every later `railway` command here uses that link. Run from a folder that has no link yet: `railway status` should say there is no linked project. A folder already linked to another project (a copy of this repo you deploy elsewhere) would send the code to the wrong one; use a fresh clone. With several workspaces, `init` asks which one, or pass `--workspace <name>`. Create the project and service, with the user's OK:

```bash
railway init --name home-air
railway add --service home-air
```

`railway list` should show the project once; if the name appears twice, delete only the one you made, by its ID (see removing it below).

Send settings using the helper, after the user's OK:

```bash
uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py railway --service home-air
```

It sends `CONFIG_TOML` from `config.toml` and each set key from `.env` through stdin, and prints only the names sent. Neither private file is uploaded with the code. It sets them without starting a deploy (`--skip-deploys`), so no empty or failing deploy starts before the code is up; the next step deploys with all of them. To set one variable yourself the same way, add `--skip-deploys` to `railway variable set`. A user going straight to Railway without a local run pastes `AIRGRADIENT_TOKEN` into the service's Variables form instead; agents never handle the pasted token.

Deploy, with approval:

```bash
railway up --service home-air --detach
```

`railway up` uploads this folder to the user's own Railway account, skipping what `.gitignore` lists (so not `config.toml` or `.env`); the Dockerfile's `.dockerignore` keeps them out of the image too. `--detach` returns at once, before the build is done. Wait for it: `railway deployment list --service home-air` shows the newest deployment's status; it should change from BUILDING or DEPLOYING to SUCCESS in about 2 to 5 minutes. On FAILED, `railway logs --service home-air --build` shows why; on CRASHED, `railway logs --service home-air`.

Create an address, with approval. A bare `railway domain` creates a public one, so check first with `railway domain list --service home-air`; empty means none yet:

```bash
railway domain --service home-air
```

The image listens on the `PORT` Railway sets, so there is no port to choose. Open the URL it prints (`railway domain list --service home-air` shows it again). Run `scripts/setup.py --live https://<your-domain>` with the same uv prefix to verify that destination; it should end with "Live OK". If it doesn't answer, check `railway logs --service home-air`. To add it to a phone's home screen, see [SETUP.md](SETUP.md#on-your-phone).

To remove it all, with the user's OK (it can't be undone): take the linked project's ID, the `id` in `railway status --json`, and run `railway delete --project <id>`. An agent can't answer its prompt, so it adds `--yes`, and `--2fa-code <code>` from the user when the account has two-factor sign-in. Then check that it is gone from `railway list`. The address stops working with it.

After config or key changes, with the user's OK, rerun the transfer helper, then `railway redeploy --service home-air --yes` to apply them (the helper sets variables without deploying). After code changes, rerun `railway up --service home-air --detach` and wait as above.

## Docker

Install Docker with Compose 2.24 or newer. Build from this repo's Dockerfile. Keep `.env` and `config.toml` beside `docker-compose.yml`.

If uv is available, follow [SETUP.md](SETUP.md) to prepare those files. Without uv, run setup inside the image, mounting this repo so files are written here. This uses a temporary container and does not start a live service. If config does not exist yet, create an empty mount source first with `touch config.toml`:

```bash
docker compose build
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD:/work" -w /work \
  home-air-quality python scripts/setup.py
```

Open `.env` in the user's editor and wait while they paste the token (see SETUP.md). Ask the location and profiles, then run the same container command with `--address "…" --profiles none`. It writes the config and checks it and the monitors. On Linux, the app's container user must be able to read the mounted config: `chmod 644 config.toml`.

Start with the user's OK:

```bash
docker compose up -d
```

Open http://localhost:8000. Verify with `docker compose exec home-air-quality python scripts/setup.py --live http://localhost:8000`. If you change only the host port mapping, open that host address in your browser and keep http://localhost:8000 in the container's verification command. Change the verification port only if you also change PORT inside the container. `docker compose logs` shows startup problems.

To open it from a phone on the same network, change the Compose port line to `"8000:8000"`, recreate the service, and use `http://<server-address>:8000`. Anyone on that network can then see the page; it has no password or HTTPS. Don't forward this port on your router. Use Railway or a home VPN for access from outside.

After config or `.env` changes: `docker compose up -d --force-recreate` (recreation reloads environment variables). After pulling code: `docker compose up -d --build`. These change the running service and need approval.
