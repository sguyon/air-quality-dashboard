# Setup

Steps for a coding agent setting up Home Air Quality for someone's home, on their computer. To put it online afterwards, see [`DEPLOYMENT.md`](DEPLOYMENT.md).

Two rules for the whole setup:

- **Keys never pass through the chat.** Don't ask the user to paste a token or key into the conversation, and don't read, print or `cat` `.env`. The user types keys into `.env` themselves, or a command writes them there without showing them.
- **`config.toml` and `.env` stay private.** Both are gitignored. Never commit them, and never paste their contents into an issue or PR.

## 0. Get the code

If you're not already in a copy of this repo, clone it and work from there:

```bash
git clone https://github.com/sguyon/home-air-quality
cd home-air-quality
```

## 1. Copy the config

```bash
cp config.example.toml config.toml
```

Everything about the home goes in `config.toml`. The comments in it say what each setting does.

## 2. The place

Ask the user for their address (a street corner or a neighborhood is enough). Then fill `[place]`:

- `name`: what the page calls the home, usually the neighborhood ("Maplewood").
- `lat`, `lon`: the address's coordinates, **rounded to 2 decimals** (about 1 km). The page shows them, and weather, pollen and smoke don't need more. `scripts/check_config.py` flags more decimals.
- `timezone`: the IANA name for the address ("America/Chicago").
- `indoor`, `outdoor`: ask the user which monitors they have: an indoor one, an outdoor one, or both. Each line says what to call that monitor in sentences ("bedroom", "balcony"). Delete the line of a monitor they don't have; one must stay. The page finds the monitors through the token on its own: the first one AirGradient lists as indoor and the first as outdoor.
- `pollen_zip`: the US ZIP code, for the pollen.com link. Delete the line outside the US.
- `region` (optional): the city or region, used in a few sentences ("the usual Chicago season"). Leave it out for neutral wording.

The `[[pollen_seasons]]` dates in the example are for the northeastern US. Adjust them for another region if the user knows the local seasons; they're typical dates, not a forecast.

Keep a copy of `config.toml` somewhere private (a password manager note, a private repo): it isn't in git, so it has no history and no backup.

### Indoor monitor only: where outdoor PM2.5 comes from

Without an outdoor monitor, the page reads outdoor PM2.5 from a source chosen now and kept: a nearby public AirGradient monitor, an estimate for the area, or Open-Meteo's model alone. Once `lat` and `lon` are filled, run:

```bash
uv run --with-requirements requirements.txt scripts/check_config.py --suggest
```

(Without uv, with Python 3.11 or newer: create the virtualenv first, with step 8's first three commands (`python3 -m venv .venv`, `. .venv/bin/activate`, `pip install -r requirements.txt`), then run `python scripts/check_config.py --suggest`.) It asks AirGradient's public list of monitors (one request, no token). It lists up to 5 public outdoor monitors reporting now within 15 km, nearest first, each with its distance, its last corrected PM2.5 and its id:

```
Public outdoor monitors reporting now within 15 km, nearest first:
  <name>, <distance> km, corrected PM2.5 <value> µg/m³, id <id>
```

(No list when none reports within 15 km; "(the 5 nearest of <n>)" after "nearest first" when more do.) Then one line with the source to choose and why, one of:

- `Suggested outdoor_from = <id>: <name>, <distance> km away, the nearest public outdoor monitor reporting now (within 3 km, its readings stand for your street).`
- `Suggested outdoor_from = "area": no public outdoor monitor within 3 km; <n> public outdoor monitors within 15 km tune the forecast to your area.`
- `Suggested outdoor_from = "model": <n> public outdoor monitors within 15 km, fewer than 2 for an area estimate, so Open-Meteo's model alone.`

Until `outdoor_from` is written, the same run also prints `Problem: … no outdoor monitor, so sources.outdoor_from is needed …`: expected at this point.

Show the user the listed monitors (name, distance, last reading) and the suggestion with its reason in plain words (the monitor's name and distance, or why it's an estimate). Then write their choice under `[sources]`: `outdoor_from = <id>` for a monitor (a number, no quotes; another listed monitor's id if they prefer it), or `outdoor_from = "area"` or `"model"`. The page labels both "Estimate for your area" (the model with "Open-Meteo" after it). If the chosen monitor stops reporting, the page shows an estimate for the area until it's back, and step 7's check says when it has been silent for 7 days, with the next best.

### Outdoor monitor only

Delete the `indoor` line; `outdoor_from` isn't needed. The toddler profile can still be picked: it shows greyed, "Needs an indoor monitor", and gives no actions until an indoor monitor is added and named in `indoor`.

## 3. The profiles

Ask the user: "Which profiles fit your home: a toddler, sinus allergies, a runner? You can pick several." Then set each one in `[profiles]` to `true` (picked) or `false`:

- `toddler`: a small child at home. CO₂ and the air at sleep time, and whether outdoor air is fine for them.
- `sinus`: sinus trouble or allergies. Humidity and pollen.
- `runner`: someone who runs outdoors. When outdoor PM2.5, smoke and a road's rush hours make a run worth it.

These are the only profiles the page knows. A new one is a code change (see "Adding a profile" below). A config from before this name may say `[needs]` instead: it still works, and `scripts/check_config.py` notes the old name.

Then ask what they have to dry a damp room, and set `[home] appliances` to `["dehumidifier", "ac_dry"]` (both, the default), one of them, or `[]`: the humidity action uses these.

## 4. The road: leave it out

In this version the road is off for new homes: leave the `[road]` section commented out. The page then has no road, no rush-hour rule and no exhaust on the map.

If the user wants one later, a road needs a route file. It's possible to build, but untested:

- A JSON array of `[longitude, latitude]` points in order along the road (the `coordinates` of a GeoJSON LineString, without the wrapper). `static/bqe.json`, the demo's road, is an example: 120 points.
- At least one point within 2 km of the home, or set `toward` by hand: the compass bearings (degrees) from the home toward the road, `[min, max]`.
- Then fill `[road]`: `name`, `route` (the file's path from the repo folder), `rush` (`[start hour, end hour, label]`, 24-hour clock).

A route can be traced from OpenStreetMap data, but nothing in this repo does it yet.

## 5. The AirGradient token

The page reads the monitors through AirGradient's API, with the user's token.

**Getting it:** the user logs in to the AirGradient dashboard (https://app.airgradient.com), opens the menu at the top left, goes to their place's **Connectivity Settings** (some versions: **General Settings → Connectivity**), turns on API access and copies the token. These steps come from integrations' docs, not AirGradient's own; if the menu differs, the user looks for "API access" in the dashboard settings.

**Putting it in `.env`:** the user does it, never through the chat. Either:

- they open `.env` in an editor (create it if missing) and add a line `AIRGRADIENT_TOKEN=<their token>`; or
- they run this in their own terminal, in the repo folder, then paste the token and press Enter (nothing shows while they paste):

  ```bash
  read -rs T && printf '\nAIRGRADIENT_TOKEN=%s\n' "$T" >> .env && unset T
  ```

Don't copy `.env.example` to `.env`: the first line for a key wins, so a placeholder line above the real one hides it (the server and `scripts/check_config.py` treat placeholders as missing). If `.env` already has an `AIRGRADIENT_TOKEN` line, the user replaces it instead of adding a second one.

## 6. Pollen: now or later

Ask the user: set up pollen now, or later? Skipping is fine. Without a key the pollen card says "Off" ("Needs a Google Pollen key") and keeps its season calendar, and the sinus & allergy profile goes on humidity only. To turn pollen off entirely, set `pollen = false` under `[sources]`.

The key comes from Google's Pollen API. It needs a Google Cloud project with billing turned on. The API has a free monthly allowance, and the app makes about one call a day, since it keeps each day's pollen.

**With `gcloud`** (the agent runs the commands, except the two the user does):

1. The user signs in, in Claude Code by typing: `! gcloud auth login`. In another agent, in their own terminal.
2. Pick a project: an existing one (`gcloud projects list`), or a new one (`gcloud projects create <id>`). Then `gcloud config set project <id>`.
3. Billing: `gcloud billing accounts list`. If there's an account, link it: `gcloud billing projects link <id> --billing-account=<account id>`. If there's none, the user adds one in the Cloud console (it asks for a card): https://console.cloud.google.com/billing.
4. Enable the Pollen API and the API Keys API (`gcloud services api-keys` needs it), create a key limited to the Pollen API, and write it into `.env` without printing it:

   ```bash
   gcloud services enable pollen.googleapis.com apikeys.googleapis.com
   gcloud services api-keys create --key-id=home-air-pollen --display-name="Home Air Quality pollen" \
     --api-target=service=pollen.googleapis.com >/dev/null 2>&1
   gcloud services api-keys describe home-air-pollen --format='value(displayName)'
   K="$(gcloud services api-keys get-key-string home-air-pollen --format='value(keyString)')" \
     && [ -n "$K" ] && printf '\nGOOGLE_POLLEN_API_KEY=%s\n' "$K" >> .env; unset K
   ```

   The output of `create` and `get-key-string` contains the key. Never run either of them again without the redirect or the `K="$(…)"` capture above, or the key lands in the chat. `describe` confirms the key exists without showing it.

   If `.env` already has a `GOOGLE_POLLEN_API_KEY` line, remove it first without printing anything: `{ grep -v '^GOOGLE_POLLEN_API_KEY=' .env || true; } > .env.tmp && mv .env.tmp .env`.

**Without `gcloud`**, give the user these steps in the Cloud console (https://console.cloud.google.com):

1. Pick or create a project, and make sure billing is on.
2. APIs & Services → Library → "Pollen API" → Enable.
3. APIs & Services → Credentials → Create credentials → API key. Edit the key: under API restrictions, restrict it to the Pollen API.
4. Copy the key into `.env` as `GOOGLE_POLLEN_API_KEY=<key>`, the same way as the token.

## 7. Check the config

```bash
uv run --with-requirements requirements.txt scripts/check_config.py
```

Without uv, in the virtualenv from step 8 (Python 3.11 or newer; macOS's own `python3` may be older): `python scripts/check_config.py`. It prints `AIRGRADIENT_TOKEN set` or `missing` (and the same for the pollen key), never their values, then which monitors the home has (`Monitors: indoor and outdoor`, `Monitors: outdoor only`, or `Monitors: indoor only; outdoor PM2.5 from …`), then any problems in plain words, then `Config OK`. For a home with an indoor monitor only, it also checks the chosen source is reporting (one request to AirGradient's public list). Fix every problem it lists and run it again.

## 8. Run it

One command, with [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 and the packages on the fly):

```bash
uv run --with-requirements requirements.txt server.py
```

Without uv, with Python 3.11 or newer:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Then open http://localhost:5555. Set `PORT` to use another port (`PORT=5600 uv run …`). The page answers only on this computer; to open it from a phone on the same network, start it with `HOST=0.0.0.0` and open `http://<this computer's address>:5555` on the phone. The server reads `config.toml` and `.env` when it starts: restart it after changing them. Flask may print a line about python-dotenv; ignore it, the server reads `.env` itself.

**What the user should see:**

- No token yet: the page with their home's name and a card that says "Config loaded. Add AIRGRADIENT_TOKEN to .env".
- With the token: their monitors' readings, the actions, the profiles they picked and whether the air suits each of them, and the local conditions for their place.
- Indoor monitor only: the outdoor card named after the source: "Nearby public monitor" with that monitor's name and distance, or "Estimate for your area".
- Outdoor monitor only: a greyed indoor card titled "No indoor monitor", and the toddler profile, if picked, greyed with "Needs an indoor monitor".
- No `config.toml` and no token: the demo, with made-up data.
- A token but no `config.toml`: the server stops with "No config: copy config.example.toml to config.toml (or set CONFIG_TOML)".

If a monitor named in `[place]` is missing on the page, check that the token's account has a monitor of that kind: one set as indoor for `indoor`, one set as outdoor for `outdoor`.

## Outside the US

The page is built for the US. Outside it, in `config.toml`:

- set `smoke = false` under `[sources]` (NOAA's smoke map covers North America);
- set `pollen = false` under `[sources]`;
- delete the `pollen_zip` line.

The weather card's forecast link still goes to the US National Weather Service, which has no page for other places. Open-Meteo (weather and the PM2.5 forecast) and AirGradient's nearby monitors work everywhere.

## Adding a profile

A profile is code, not a setting. To add one, touch each of these and keep the tests green (`pytest -q && node --test tests/`):

- `config.py`: add it to `PROFILES`.
- `summary.py`: its state in `profiles_row`, and which items serve it.
- `server.py`: its line in `build_profiles`.
- `phrases.py`: its sentences, in `PILLS`.
- `static/home.js`, `static/app.js`, `static/summary.js`: its name, icon and wording.
- `index.html`: its chip under "Profiles" in the Home menu.
- `config.example.toml`: a commented line under `[profiles]`.
- `demo/` and its tests: the demo moments are the test fixtures, so a new profile shows up in them in the same commit.

### Ideas for more profiles

The three profiles come from one household. Other homes have other people in them. Each idea below lists what the page would watch for that person and whether the data is already there. If you build one, a pull request is welcome; if you only want one, open an issue saying which and why.

| Profile | What it would watch | Data today |
|---|---|---|
| A light sleeper | Bedroom CO₂ overnight (under 1,000 ppm), bedroom temperature (about 16–19 °C), outside noise or pollen if the window stays open | Yes: indoor CO₂, temperature, pollen |
| Someone working from home | CO₂ during work hours, with a nudge to air out before the room gets stuffy (around 1,000 ppm) | Yes: indoor CO₂ |
| Someone with asthma or sensitive lungs | Stricter PM2.5 lines inside and out, ozone, and smoke days | Partly: PM2.5 and smoke yes; ozone not fetched yet (Open-Meteo has it) |
| Someone who cooks on gas | NOx and PM spikes indoors after cooking, and how long they take to clear | Yes: indoor NOx index and PM2.5 |
| Someone sensitive to mold | Indoor humidity above 60% for days, not hours | Yes: indoor humidity history |
| A baby | Humidity 40–60%, temperature, CO₂ at night | Yes, if the indoor monitor is in the baby's room |
| Someone who cycles to work | Outdoor PM2.5 and the road's rush at fixed commute times | Yes: like the runner profile, with set hours |
| A pet bird | Indoor VOCs (birds react to fumes from non-stick pans and sprays) | Yes: indoor VOC index |

Profiles that only re-read existing data (most of the table) are the easiest start: copy the runner or toddler profile and change what it reads.
