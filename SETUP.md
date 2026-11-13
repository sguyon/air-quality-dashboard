# Setup

**Done when** `uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py --live <the page's address>` ends with `Live OK`: the page answers with the home's settings, and each monitor has a recent reading.

For a coding agent setting this up for someone's home. Do the steps yourself when a command can. Ask one question per message, in plain words, then wait for the answer: no question tool with several questions, and don't queue the next question while you work. Skip answers the user already gave. Don't change the app's code during setup: if the token is refused twice, stop and say what the page said. Never ask for a key in chat, read or print `.env`, or commit private settings. Ask before changing a live service or account.

## Get ready

Tested on Mac and Linux. On Windows, use WSL or Docker.

Work in this repo folder throughout. If needed:

```bash
git clone https://github.com/sguyon/home-air-quality
cd home-air-quality
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if missing; use Python 3.12: `uv python install 3.12`. All commands below run from this folder. To see what's done and the next command at any point, run `uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py --status`; it changes nothing. For Docker or a home server, follow [DEPLOYMENT.md](DEPLOYMENT.md#docker) first.

## Connect AirGradient

Prepare the private token file; this keeps existing lines and sets owner-only permissions:

```bash
uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py
```

On the user's own computer, start the app now with the command under **Start and verify**. Open the exact `?setup=…` link it prints with `open '<link>'` on Mac or `xdg-open '<link>'` on Linux. The link grants access to the token box and redirects to `/`. Never enter or inspect the token through browser tools.

Then send one message, with the exact link:

> I opened the AirGradient connection page in your browser. If it didn't open, open this link: <the setup link>
>
> On that page you enter your AirGradient token. You need an AirGradient monitor that already shows readings in the AirGradient app. Follow the page's two steps: copy your token from the AirGradient dashboard (General settings → Connectivity → API access), then press Connect. If AirGradient asks you to sign in, press the page's step 1 button again afterwards.
>
> Tell me when the page says Connected, or if you don't have a monitor set up yet.

The page checks the token with AirGradient, lists the account's monitors, saves it privately and loads it without a restart. When the user says it's connected, run `scripts/setup.py` again (the command above): it prints the account's monitors without showing the token. Tell the user in one line what you found ("Connected: 2 monitors, Living room (indoor) and Back porch (outdoor).") before the next question. A fresh copy stays in the demo until the home is configured below; stop that process before restarting with the home.

Can't find the token: tell them to press "Show me where" under step 1 on the page. It opens a marked picture of AirGradient's settings page: 1 General Settings in the left menu, 2 the Connectivity tab, 3 API Access, where they turn it on and press the copy button. Walk them through those marks in words. Don't open pictures in another app: a picture of a web page in its own window looks clickable.

No monitor yet (the user says so, or the page says the account has none): stop the setup. Tell them to set up the monitor with AirGradient's instructions and come back, and that meanwhile [the demo](https://homeair.guyon.dev) shows the live readings of any public AirGradient monitor ("Near me").

Fallback, Docker or a home server: open `.env` in the user's text editor (`open -e .env` on Mac, `xdg-open .env` on Linux). Wait while they fill the empty `AIRGRADIENT_TOKEN=` line and save. Restart the app afterwards. Check only set/missing with `scripts/check_config.py`; before config exists, setup itself checks the token with AirGradient without showing it.

Going straight to Railway without a local run: the user pastes the token into the service's Variables form instead.

## Describe your home

Ask these two questions, one per message, each with its default:

1. “What neighborhood or address should the page use for weather and nearby air? A nearby landmark with its city works too. Default: a nearby landmark in the neighborhood you have already named.” Keep only the location rounded to about 1 km; don't invent a location if none is known. Before the next question, say in one line what you understood and what's kept: “Got it: near Times Square, New York. It's used for your weather, nearby public monitors and timezone; only a location rounded to about 1 km is saved, in config.toml on this computer.”
2. “Which profiles match your home: a toddler, someone with sinus trouble or allergies, someone who runs outside, or none? Pick any. Default: none.”

Then run one command, using their answers:

```bash
uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py \
  --address "Times Square, New York" --profiles sinus,runner
```

It reads the account's monitors, finds the location and timezone once, picks the outdoor source, writes a small `config.toml`, checks it and checks each monitor's latest reading. It ends with `Config OK` and `Live OK`, or says what to fix. If monitors are ambiguous, ask only which of the listed candidates to use, then pass the flag it names. Never take the first silently. If the address isn't found, retry with what the user gave (a ZIP code, a nearby street or landmark) before asking again. If several places match, ask which city or state and rerun; lookup corrections include `--name`, `--lat` with `--lon`, and `--timezone`.

No approval is needed before writing. An existing config is copied to `config.toml.bak-<time>` first and the backup's path is printed. Drying equipment defaults to none; pollen and road setup can wait. Outside the US, setup turns off NOAA smoke and omits the US pollen link. A failed public-monitor lookup uses a forecast estimate and says so.

## Start and verify

```bash
uv run --python 3.12 --with-requirements requirements.txt server.py
```

Open http://localhost:5555 on this computer. Without a token, open the printed setup link for the token box (the plain address shows the demo on a fresh copy, or says where the link is once a home is set up). Restart to get a new link. Set `PORT=5600` before the command if the port is taken, and use that port below too.

With the token and home configured, check the running page:

```bash
uv run --python 3.12 --with-requirements requirements.txt scripts/setup.py --live http://localhost:5555
```

It uses read-only GET requests and ends with `Live OK`. The page should show the monitors' readings, actions, chosen profiles and local conditions. Without an outdoor monitor, the outdoor card names a public monitor or says “Estimate for your area”. If a reading is missing, check the monitor is online and set as indoor or outdoor in AirGradient. Docker and Railway users verify their final URL without starting a local server.

## Use it again

Give the user the address, what to expect, and one start command with the full repo path: `cd /path/to/home-air-quality && uv run --python 3.12 --with-requirements requirements.txt server.py`. Include the actual port and log location if started in the background. Ctrl+C stops it in a terminal.

Change names, profiles, drying equipment (`[home] appliances`) or limits in `config.toml`; [config.example.toml](config.example.toml) explains the settings. Restart after editing config or `.env` by hand. Keep a private copy of config; it isn't in git. Optional [pollen, road tracing, new profiles and Vercel demo](docs/optional.md); [Railway and Docker deployment](DEPLOYMENT.md).
