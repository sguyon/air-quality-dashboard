# Setup

**Done when** `scripts/run.sh scripts/setup.py --live <the page's address>` ends with `Live OK`: the page answers with the home's settings, and each monitor has a recent reading.

For a coding agent setting this up for someone's home. Do the steps yourself when a command can. Ask one question per message, in plain words, then wait for the answer. If you have a question tool (Claude Code's AskUserQuestion, for example), ask every question with it, one at a time, the default as the first option; don't write a question as plain chat text, except the address question and, where the tool can't pick several, the profiles (see **Describe your home**). Don't ask the next one until the user has answered and you've said what you did with it. Skip answers the user already gave. Don't change the app's code during setup: if the token is refused twice, stop and say what the page said. Never ask for a key in chat, read or print `.env`, or commit private settings. Ask before changing a live service or account.

## Get ready

Tested on Mac and Linux. On Windows, use WSL or Docker.

Work in this repo folder throughout. If needed:

```bash
git clone https://github.com/sguyon/home-air-quality
cd home-air-quality
```

Run every command below from this folder through `scripts/run.sh`: it uses uv, installs uv if it's missing, or falls back to Python 3.11 or newer, and says which; if none works, it stops and says what to install. To see what's done and the next command at any point, run `scripts/run.sh scripts/setup.py --status`; it changes nothing.

In a cloud sandbox (Claude Code on the web, Codex cloud) asked to set up a home: say the app can't stay there and to run setup on their own computer, then stop. Development in a sandbox is unaffected: see AGENTS.md, "Run".

## Connect AirGradient

Prepare the private token file; this keeps existing lines and sets owner-only permissions:

```bash
scripts/run.sh scripts/setup.py
```

On the user's own computer, start the app now with the command under **Start and verify**. Open the exact `?setup=…` link it writes to `app.log` with `open '<link>'` on Mac or `xdg-open '<link>'` on Linux. The link grants access to the token box and redirects to `/`. Never enter or inspect the token through browser tools.

Then send one message, with the exact link, and in the same turn run `scripts/setup.py --wait-token` (the command above with `--wait-token`):

> I opened the AirGradient connection page in your browser. If it didn't open, open this link: <the setup link>
>
> On that page you enter your AirGradient token. You need an AirGradient monitor that already shows readings in the AirGradient app. Follow the page's two steps: copy your token from the AirGradient dashboard (General settings → Connectivity → API access), then press Connect. If AirGradient asks you to sign in, press the page's step 1 button again afterwards.
>
> I'll notice when the token is saved: no need to reply. If nothing happens, type done. If you don't have a monitor set up yet, tell me.

The page checks the token with AirGradient, lists the account's monitors, saves it privately and loads it without a restart. `--wait-token` waits up to 90 seconds for that and prints the account's monitors without showing the token. If it says "Not saved yet", run it again, unless the user has written meanwhile; when they type done, run it once more. Tell the user in one line what you found ("Connected: 2 monitors, Living room (indoor) and Back porch (outdoor).") before the next question. A fresh copy stays in the demo until the home is configured below; stop it (`kill $(cat app.pid)`) before restarting with the home.

Can't find the token: tell them to press "Show me where" under step 1 on the page. It opens a marked picture of AirGradient's settings page: 1 General Settings in the left menu, 2 the Connectivity tab, 3 API Access, where they turn it on and press the copy button. Walk them through those marks in words. Don't open pictures in another app: a picture of a web page in its own window looks clickable.

No monitor yet (the user says so, or the page says the account has none): stop the setup. Tell them to set up the monitor with AirGradient's instructions and come back, and that meanwhile [the demo](https://homeair.guyon.dev) shows the live readings of any public AirGradient monitor ("Near me").

Fallback, when the token page can't open: open `.env` in the user's text editor (`open -e .env` on Mac, `xdg-open .env` on Linux). Wait while they fill the empty `AIRGRADIENT_TOKEN=` line and save. Restart the app afterwards. Check only set/missing with `scripts/check_config.py`; before config exists, setup itself checks the token with AirGradient without showing it.

## Describe your home

Ask these two questions, one per message, each with its default; the user never types a default to keep it. With a question tool, offer the answers as options with the default first, so one key keeps it, except as noted below.

1. Ask the address as plain chat text, with no options to pick, even with a question tool: “What neighborhood or address should the page use for weather and nearby air? A nearby landmark with its city works too. Default: a nearby landmark in the neighborhood you have already named. Any other reply, like ok, keeps it.” Keep only the location rounded to about 1 km; don't invent a location if none is known. Before the next question, say in one line what you understood and what's kept: “Got it: near Times Square, New York. It's used for your weather, nearby public monitors and timezone; only a location rounded to about 1 km is saved, in config.toml on this computer.”
2. The profiles. With a question tool that picks several (Claude Code's does), ask “The page suggests actions, like closing a window or running a purifier. To personalize them for your home, which of these apply?” with the three as options and None first (the default). Without a question tool that picks several (Codex's picks one), ask in plain chat text, laid out like this:

   > The page suggests actions, like closing a window or running a purifier.
   > To personalize them for your home, which of these apply?
   >
   > 1. A young child
   > 2. Sinus trouble or seasonal allergies
   > 3. Running or sport outside
   >
   > Type the numbers, like 1 3, or none.
   > Any other reply, like ok, keeps none.

   In the command below, 1 is `toddler`, 2 is `sinus` and 3 is `runner`.

Then run one command, using their answers:

```bash
scripts/run.sh scripts/setup.py \
  --address "Times Square, New York" --profiles sinus,runner
```

It reads the account's monitors, finds the location and timezone once, picks the outdoor source, writes a small `config.toml`, checks it and checks each monitor's latest reading. It ends with `Config OK` and `Live OK`, or says what to fix. If monitors are ambiguous, ask only which of the listed candidates to use, then pass the flag it names. Never take the first silently. If the address isn't found, retry with what the user gave (a ZIP code, a nearby street or landmark) before asking again. If several places match, ask which city or state and rerun; lookup corrections include `--name`, `--lat` with `--lon`, and `--timezone`.

No approval is needed before writing. An existing config is copied to `config.toml.bak-<time>` first and the backup's path is printed. Drying equipment defaults to none; pollen and road setup can wait. Outside the US, setup turns off NOAA smoke and omits the US pollen link. A failed public-monitor lookup uses a forecast estimate and says so.

## Start and verify

Start it in the background, so it keeps running after this session (it writes to `app.log`):

```bash
nohup scripts/run.sh server.py > app.log 2>&1 < /dev/null &
```

The app's address is on the first line of `app.log` (`Home Air Quality → http://localhost:<port>`): use that address below and in the last message. Open it on this computer. Without a token, open the printed setup link for the token box (the plain address shows the demo on a fresh copy, or says where the link is once a home is set up). Restart to get a new link. Set `PORT=5600` before the command if the port is taken, and use that port below too.

With the token and home configured, check the running page:

```bash
scripts/run.sh scripts/setup.py --live http://localhost:5555
```

It uses read-only GET requests and ends with `Live OK`. If the token was saved on its page in this session, the page where the user saved the token turns into the home by itself: don't open another tab. Otherwise open the address once (`open` on Mac, `xdg-open` on Linux). The page should show the monitors' readings, actions, chosen profiles and local conditions. Without an outdoor monitor, the outdoor card names a public monitor or says “Estimate for your area”. If a reading is missing, check the monitor is online and set as indoor or outdoor in AirGradient. Docker and Railway users verify their final URL without starting a local server.

## Use it again

End with this message, with the real port, and nothing after it:

> Home Air Quality is ready at this address:
>
> http://localhost:5555
>
> It stops when this computer restarts. I can make it start by itself when you log in.
>
> I can also help you set it up on a home server with Docker, or online with Railway.

The address goes alone on its line, plain; don't say a tab is open. If they ask:

- To start it by itself: `scripts/run.sh scripts/setup.py --start-at-login on` (a Mac, or Linux with systemd; elsewhere it says why not). `off` undoes it.
- For a home server: `scripts/run.sh scripts/setup.py --home-server`, then pass on its two steps; the server needs Docker. Don't offer to copy it over SSH: give the steps, and do more only if they ask. Once they've started it, check `scripts/run.sh scripts/setup.py --live http://<the server>:8000` if you can reach it.
- Online: [DEPLOYMENT.md](DEPLOYMENT.md#railway).

For later sessions, not for the message: the app writes to `app.log` in this folder, and starts again with `cd /path/to/home-air-quality && nohup scripts/run.sh server.py > app.log 2>&1 < /dev/null &` (with `PORT=` first if it isn't 5555).

Change names, profiles, drying equipment (`[home] appliances`) or limits in `config.toml`; [config.example.toml](config.example.toml) explains the settings. Restart after editing config or `.env` by hand. Keep a private copy of config; it isn't in git. Optional [pollen, road tracing, new profiles and Vercel demo](docs/optional.md); [Railway and Docker deployment](DEPLOYMENT.md).

## On your phone

To open it from a phone on the same Wi-Fi, start it with `HOST=0.0.0.0` before the start command (anyone on that Wi-Fi can then open it), and open `http://<the computer's name>.local:5555` on the phone. Away from home, use the Railway address ([DEPLOYMENT.md](DEPLOYMENT.md)). Then add it to the home screen: Share › Add to Home Screen (iPhone, Safari) or ⋮ › Install app (Android, Chrome); it opens like an app. It works offline only on https, which the Railway address has.
