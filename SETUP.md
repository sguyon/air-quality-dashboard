# Setup

Steps for a coding agent setting up Home Air Quality for someone's home, on their computer. To put it online afterwards, see [`DEPLOYMENT.md`](DEPLOYMENT.md).

Two rules for the whole setup:

- **Keys never pass through the chat.** Don't ask the user to paste a token or key into the conversation, and don't read, print or `cat` `.env`. The user types keys into `.env` themselves, or a command writes them there without showing them.
- **`config.toml` and `.env` stay private.** Both are gitignored. Never commit them, and never paste their contents into an issue or PR.

## How to ask

The user answers up to seven questions, **one per message**, in this order: address → monitors → profiles → drying (indoor monitor only) → outdoor source (no outdoor monitor only) → token → pollen. Skip what doesn't apply. Keep it easy for them:

- **One topic per question,** in plain words and short sentences: many users read English as a second language. Say in a sentence why you ask and what each choice leads to.
- **Don't ask what you can find out:** the home's name, the timezone and the coordinates come from `scripts/setup.py` (step 1).
- **With a question tool** (Claude Code's AskUserQuestion, or your agent's equivalent), use it for every question with options, one question per call: 2–4 options, the recommended option first with "(Recommended)" in its label, several picks allowed where the question says "pick any". The tool adds "Other" itself. Ask free-text questions (the address) in a normal message.
- **Without one,** send each question as written below, alone in its message: lettered options, the default marked. A missing answer or "ok" takes the default.
- **Ask each question once.** If the user already answered one (in their first message, or earlier), don't ask it again.
- **End with a recap** and write nothing until the user says ok.

**The home** (questions 1 and 2, one message each)

```
1. What's your home address?
   The page uses it for weather, pollen and the public monitors near you. It keeps only a rough
   location (about 1 km). If you'd rather not share your address, a nearby landmark works too, or
   a house number on your street (it doesn't have to be yours).
   e.g. "350 5th Ave, New York" or "Times Square, New York"

2. Which AirGradient monitors do you have? The app works with one indoor monitor, one outdoor
   monitor, or one of each.
   a) Indoor only: an AirGradient ONE (or an indoor DIY kit)
   b) Outdoor only: an Open Air (or an Open Air Max)
   c) One of each
   d) Something else (tell me)
   Optional: where they are ("bedroom", "balcony"). If you skip it, I'll call them "home" and "outside".
```

For "something else": the app reads one indoor and one outdoor AirGradient monitor (with more of one kind, it uses the first one AirGradient lists), tells them apart by model (Open Air models are outdoor), and reads no other brand for now.

After question 2, run step 1: it finds the place, and for an indoor-only home it lists the public monitors for question 5.

**The people at home** (questions 3 and 4, one message each)

```
3. Which profiles fit your home? A profile tailors the advice to someone who lives there.
   Pick any, or none.
   1) Toddler: stale air (CO₂) and the air at nap and bed time
   2) Sinus or allergies: humidity and pollen
   3) Runner: when the air outside is good for a run
   4) Something else (not built yet: it needs a code change)

4. Which of these do you have at home? When the air inside gets too humid (too much water in
   the air, which can lead to mold), the page tells you what to turn on. Pick any, or none.
   a) A dehumidifier (a machine that takes water out of the air)
   b) An air conditioner with a "dry" mode

```

Without an indoor monitor, skip question 4 (the humidity action reads the indoor monitor), and add under question 3: "The toddler profile reads CO₂ indoors, so it stays greyed until you add an indoor monitor." For "something else": say which profile they meant, that it isn't built, and that an adventurous user's agent can add it ("Adding a profile" below); a pull request is welcome.

**Outdoor air, only without an outdoor monitor** (question 5) (the monitors and the suggestion come from step 1's output)

```
5. Where should outdoor air readings come from? You don't have an outdoor monitor, so the
   page uses one nearby.
   a) <name>, a public monitor <d> km away (Recommended: the closest, real readings)
   b) <name>, <d> km
   c) <name>, <d> km
   d) An estimate for your area: less precise, but it doesn't depend on one monitor
```

Put the suggested source first, with its reason in plain words (the `Suggested outdoor_from` line says it). If they pick a monitor, add: "If it stops reporting, the page shows the estimate until it's back."

**The keys** (questions 6 and 7, one message each)

```
6. Your AirGradient token (required). The app reads your monitors with an access code from
   AirGradient, called a token. Without it, the page can't show your readings. It takes about
   2 minutes: I'll tell you where to click in your AirGradient dashboard and give you a command
   that saves it on this computer. You never paste it here.
   a) Now (Recommended)
   b) Later: the page says "Add AIRGRADIENT_TOKEN to .env" until then

7. Pollen levels (optional) come from Google and need a free Google key. It takes 5–10 minutes:
   the hard part is creating a Google Cloud account (with a payment card) and finding your way
   in Google's console, so I do every step I can for you. This app stays within Google's free
   allowance, and setup caps its use so it can't cost money.
   a) Later (Recommended)
   b) Now
```

**Recap, before writing anything:** the command prints it (step 2's `--check` output). Show the user that recap as is, don't rewrite it, and ask them to reply "ok" or the number of a line to change.

One recap, one ok. If the user gave every answer up front and asked you to set it up, still show the recap once, then write after their ok without asking again.

## 0. Get the code

If you're not already in a copy of this repo, clone it and work from there. Every command below runs in the repo folder. Set it up in this folder: never copy or move the project elsewhere (for Docker too), or the config ends up outside the copy the user runs.

```bash
git clone https://github.com/sguyon/home-air-quality
cd home-air-quality
```

The commands use [uv](https://docs.astral.sh/uv/), which installs Python 3.12 and the packages on the fly. Without uv, with Python 3.11 or newer (macOS's own `python3` may be older): `python3 -m venv .venv`, `. .venv/bin/activate`, `pip install -r requirements.txt`, then replace `uv run --with-requirements requirements.txt` with `python` in every command below.

## 1. Look up the place

After question 2:

```bash
uv run --with-requirements requirements.txt scripts/setup.py --check --address "Times Square, New York" --monitors indoor
```

It writes nothing. It sends the address to OpenStreetMap once (or Open-Meteo if OpenStreetMap finds nothing) and keeps only the coordinates, rounded to about 1 km. It prints:

- `Place:` what it found, the rounded coordinates, the timezone and the ZIP (US). Check it's the right city.
- `Name on the page:` the area the user named, or the address's district. If the user calls it something else ("Capitol Hill"), pass `--name`.
- For an indoor-only home, `Outdoor air:` and the public monitors within 15 km with their ids: question 5's options.

If it says several places match, ask the user which city and add it to `--address`. If it finds nothing, ask for a landmark near them or a house number on their street, or coordinates from a map app (`--lat`, `--lon`).

## 2. The recap

With every answer, run the same command again, still with `--check`. One flag per question:

| Question | Flag | Values (default) |
|---|---|---|
| 1. Address | `--address "…"` | text, or `--lat` and `--lon` |
| 2. Monitors | `--monitors` | `indoor`, `outdoor`, `both` |
| 2. Their names | `--indoor-name`, `--outdoor-name` | (`home`, `outside`) |
| 3. Profiles | `--profiles` | any of `toddler,sinus,runner`, or (`none`) |
| 4. Drying (indoor monitor only) | `--dry` | any of `dehumidifier,ac_dry`, or (`none`) |
| 5. Outdoor air (indoor only) | `--outdoor-from` | (`suggest`), a monitor's id, `area`, `model` |
| 6. Token | `--token` | (`now`), `later` |
| 7. Pollen | `--pollen` | (`later`), `now`, `off` |

Overrides when the lookup is wrong or the user knows better: `--name`, `--lat` and `--lon`, `--zip`, `--region` (the city in a few sentences, `""` for none), `--timezone`.

A profile the page doesn't know stops the command with "Not a profile yet": see "Adding a profile" below.

**Pollen seasons.** The pollen card's season calendar is kept for the northeastern US (its dates are typical there) and left out elsewhere. If the user wants one, look up the region's typical seasons and pass each with `--season` (repeatable): `--season "Tree: Jan 15 – Apr 30, peak Feb 1 – Mar 15"`. Names are Tree, Grass or Weed (the types Google reports), the peak is optional, and a season can't cross the new year. Say where the dates came from: they're typical dates, not a forecast.

**Outside the US,** the command turns off wildfire smoke (NOAA covers North America), leaves out the pollen.com link and, without `--season`, the season calendar. Google's pollen covers more than 65 countries, so pollen can stay. The weather card's forecast link still goes to the US National Weather Service, which has no page for other places.

Show the user the recap the command prints, as is (see "Recap, before writing anything" above), and wait for ok.

## 3. Write it

The same command without `--check`. It writes `config.toml` from `config.example.toml`, keeping its comments (they say what each setting does), then checks it and ends with `Config OK`, then prints the next steps.

If `config.toml` is already there, it writes nothing and shows what would change. Ask the user before running it again with `--replace`, which saves the old file as `config.toml.bak-<date>-<time>` next to it first. Don't make backups yourself.

Tell the user to keep a copy of `config.toml` somewhere private (a password manager note, a private repo): it isn't in git, so it has no history and no backup.

## 4. The AirGradient token

Question 6. The page reads the monitors through AirGradient's API, with the user's token. Tell the user these steps (step 3's output prints them too):

1. Open the AirGradient dashboard, [app.airgradient.com](https://app.airgradient.com), and log in.
2. In the menu: **General Settings → Connectivity → API access**. Turn API access on if it's off.
3. Copy the token shown there. Don't paste it in the chat. Save it with this command, which the user runs **in their own Terminal window**, in the repo folder, **not through the agent**: it needs a terminal to read the token without showing it, and Claude Code's `!` commands have none.

   ```
   uv run --with-requirements requirements.txt scripts/setup.py token
   ```

   (Without uv: `python scripts/setup.py token`.) It asks for the token without showing it, replaces any `AIRGRADIENT_TOKEN` line already in `.env` (or adds one), and prints only "Token saved in .env". Never run it yourself with the token.

For "later", put these steps in the handover's checklist, with "then restart the server" (step 8).

## 5. Pollen: now or later

Question 7. Skipping is fine. Without a key the pollen card says "Off" ("Needs a Google Pollen key") and keeps its season calendar, and the sinus & allergy profile goes on humidity only. `--pollen off` turns pollen off entirely; for "later", adding the key later needs only a restart.

For "now", step 3's output says whether `gcloud` is installed and signed in. The key comes from Google's Pollen API. It needs a Google Cloud project with billing turned on: 5–10 minutes, most of it creating the account and adding a payment card. Do every step you can with `gcloud` so the user only signs in and adds the card. Google gives 5,000 calls a month free, then charges $10 per 1,000 (Google's price list, checked November 2026). The app keeps each day's pollen until midnight, so each running copy (your computer, a server) makes about one call a day, plus one after each restart or deploy, and one when the page's Refresh button is pressed more than 10 minutes after the last. The setup below caps the calls at 150 a day and limits the key to the Pollen API, so a bug or a leaked key can't run up a bill.

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
5. Cap the calls: at most 150 pollen forecasts a day (under 5,000 a month, the free allowance), and no heatmap calls (the app doesn't use them). The quota commands are in gcloud's beta group: `gcloud components install beta` if it's missing.

   ```bash
   gcloud beta quotas preferences create --project=<id> --service=pollen.googleapis.com \
     --quota-id=ForecastQueriesPerDay --preferred-value=150 --preference-id=pollen-forecast-daily-cap \
     --allow-high-percentage-quota-decrease
   gcloud beta quotas preferences create --project=<id> --service=pollen.googleapis.com \
     --quota-id=HeatMapQueriesPerDay --preferred-value=0 --preference-id=pollen-heatmap-off \
     --allow-high-percentage-quota-decrease
   gcloud beta quotas info list --service=pollen.googleapis.com --project=<id> --format='table(quotaId,dimensionsInfos[0].details.value)'
   ```

   The last command shows the limits: 150 for `ForecastQueriesPerDay`, 0 for `HeatMapQueriesPerDay`. When a day's 150 are used, the pollen card says "No data" until the next day; nothing is charged. If the project already used more than 150 pollen calls in a recent day, Google refuses the cap; add `--allow-quota-decrease-below-usage` to the first command, and tell the user, since something called pollen far more than the app does.

**Without `gcloud`**, give the user these steps in the Cloud console (https://console.cloud.google.com):

1. Pick or create a project, and make sure billing is on.
2. APIs & Services → Library → "Pollen API" → Enable.
3. APIs & Services → Credentials → Create credentials → API key. Edit the key: under API restrictions, restrict it to the Pollen API.
4. Copy the key into `.env` as `GOOGLE_POLLEN_API_KEY=<key>`: they open `.env` in an editor and add the line (replacing one that's already there).
5. Cap the calls: APIs & Services → Pollen API → Quotas & System Limits. Set the forecast's per-day limit ("Pollen - Forecast Usage", per day) to 150 and the heatmap's per-day limit ("Pollen - HeatMap Usage", per day) to 0.

## 6. Run it

Step 3's output gives the exact command, from the repo folder, on a free port:

```bash
uv run --with-requirements requirements.txt server.py
```

Then open http://localhost:5555. "localhost" means "this computer": the address works only in a browser on the computer running the server. If port 5555 is taken (step 3 says so), set another with `PORT=5600 uv run …` and use that port everywhere after. The server reads `config.toml` and `.env` when it starts: restart it after changing them. To stop it, press Ctrl+C in its terminal (or stop the process you started). Flask may print a line about python-dotenv; ignore it, the server reads `.env` itself.

**On a phone,** in plain words for the user: the phone and the computer must be on the same Wi-Fi. Start the server with `HOST=0.0.0.0` in front (`HOST=0.0.0.0 uv run …`); anyone on that Wi-Fi can then open the page. Find the computer's address on the Wi-Fi (macOS: `ipconfig getifaddr en0`; Linux: `hostname -I`; Windows: `ipconfig`, the "IPv4 Address"), and give the user the exact address to type on the phone, like `http://192.168.1.23:5555`. To open it away from home, put it online ([`DEPLOYMENT.md`](DEPLOYMENT.md)).

**What the user should see:**

- No token yet: the page with their home's name and a card that says "Config loaded. Add AIRGRADIENT_TOKEN to .env".
- With the token: their monitors' readings, the actions, the profiles they picked and whether the air suits each of them, and the local conditions for their place.
- Indoor monitor only: the outdoor card named after the source: "Nearby public monitor" with that monitor's name and distance, or "Estimate for your area".
- Outdoor monitor only: a greyed indoor card titled "No indoor monitor", and the toddler profile, if picked, greyed with "Needs an indoor monitor".
- No `config.toml` and no token: the demo, with made-up data.
- A token but no `config.toml`: the server stops with "No config: copy config.example.toml to config.toml (or set CONFIG_TOML)".

## 7. Check it's live

With the server running:

```bash
uv run --with-requirements requirements.txt scripts/setup.py --live
```

Add the address if it isn't http://localhost:5555 (`--live http://localhost:5600`; Docker: `--live http://localhost:8000`). It asks the running page, with GET requests only: that it answers, that the token is set, which monitors it reads and how old their last readings are, the outdoor source (indoor only), and that the page's name, monitors and profiles match `config.toml`. It ends with `Live OK`, or says what to fix. A missing monitor usually means the token's account has no monitor set as that kind (indoor or outdoor) in AirGradient's dashboard.

## 8. Hand over

Before you finish, tell the user in a few lines:

- the address to open (http://localhost:5555, or the port you used), the phone address if they want it, and what they should see there;
- how to start it again, as one command with the full path, e.g. `cd /Users/dana/home-air-quality && uv run --with-requirements requirements.txt server.py` (with the same `PORT` and `HOST`), and how to stop it (Ctrl+C in its terminal, or the process you started in the background, and where its log is);
- anything left for later, as a short checklist. The usual one is the token: step 4's steps, then restart the server and run `setup.py --live`.

If the user is away and your checks passed (`Config OK`, `Live OK`, or `/health` answers without a token yet), don't wait for them to look at the page: put the address and what to check in that message.

## The road

In this version the road is off for new homes: `setup.py` leaves the `[road]` section commented out. The page then has no road, no rush-hour rule and no exhaust on the map.

If the user wants one later, a road needs a route file. It's possible to build, but untested:

- A JSON array of `[longitude, latitude]` points in order along the road (the `coordinates` of a GeoJSON LineString, without the wrapper). `static/bqe.json`, the demo's road, is an example: 120 points.
- At least one point within 2 km of the home, or set `toward` by hand: the compass bearings (degrees) from the home toward the road, `[min, max]`.
- Then fill `[road]`: `name`, `route` (the file's path from the repo folder), `rush` (`[start hour, end hour, label]`, 24-hour clock).

A route can be traced from OpenStreetMap data, but nothing in this repo does it yet.

## Adding a profile

A profile is code, not a setting. To add one, touch each of these and keep the tests green (`pytest -q && node --test tests/`):

- `config.py`: add it to `PROFILES`.
- `summary.py`: its state in `profiles_row`, and which items serve it.
- `server.py`: its line in `build_profiles`.
- `phrases.py`: its sentences, in `PILLS`.
- `static/home.js`, `static/app.js`, `static/summary.js`: its name, icon and wording.
- `index.html`: its chip under "Profiles" in the Home menu.
- `config.example.toml`: a commented line under `[profiles]`.
- `scripts/setup.py`: its words in `PROFILE_WORDS`.
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
