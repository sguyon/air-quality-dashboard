# Deployment

For access away from home, use Railway. For a home server or NAS, use Docker Compose. Keep `config.toml` and `.env` private. Agents run commands themselves and ask before each change to a live service or account.

## Railway

Railway builds from this repo's `Dockerfile`. There is no login on the page: anyone with its address can see the readings and the home's rounded location (about 1 km). Keep the address private; telling search engines not to index it is not access control.

Prepare `config.toml` with [SETUP.md](SETUP.md). Install the [Railway CLI](https://docs.railway.com/guides/cli); the user signs in with `railway login`. From the repo folder, create a project and service:

```bash
railway init --name home-air
railway add --service home-air
```

Send settings using the helper, after the user's OK:

```bash
uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py railway --service home-air
```

It sends `CONFIG_TOML` from `config.toml` and each set key from `.env` through stdin, and prints only the names sent. Neither private file is uploaded with the code. A user going straight to Railway without a local run pastes `AIRGRADIENT_TOKEN` into the service's Variables form instead; agents never handle the pasted token.

Deploy and create an address, with approval for each command:

```bash
railway up --service home-air --detach
railway domain --service home-air
```

Open the URL it prints. Run `scripts/setup.py --live https://<your-domain>` with the same uv prefix to verify that destination. If needed, check `railway logs --service home-air`.

After config or key changes, rerun the transfer helper (it may redeploy). After code changes, rerun `railway up --service home-air --detach`.

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
