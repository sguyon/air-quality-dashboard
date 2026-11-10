# Optional settings

These can wait until your monitors show readings. Agents run the commands they can; ask before each change to a live account or service. Never read or print .env, or ask for a key in chat.

## Pollen

Without a Google key, pollen is off and the sinus & allergy profile uses humidity alone. Add `GOOGLE_POLLEN_API_KEY` to `.env` in your editor and restart, or transfer it to Railway with `scripts/setup.py railway --service <name>` after approval. Set `[sources] pollen = false` to turn it off entirely.

The key comes from Google's Pollen API. It needs a Google Cloud project with billing turned on: 5–10 minutes, most of it creating the account and adding a payment card. Do every step you can with `gcloud` so the user only signs in and adds the card. Google gives 5,000 calls a month free, then charges $10 per 1,000 (Google's price list, checked November 2026). The app keeps each day's pollen until midnight, so each running copy (your computer, a server) makes about one call a day, plus one after each restart or deploy, and one when the page's Refresh button is pressed more than 10 minutes after the last. The setup below caps the calls at 150 a day and limits the key to the Pollen API, so a bug or a leaked key can't run up a bill.

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

   The last command shows the limits: 150 for `ForecastQueriesPerDay`, 0 for `HeatMapQueriesPerDay`. When a day's 150 are used, further calls are refused until the next day. A quota is a call limit; a budget alert only sends a warning. If the project already used more than 150 pollen calls in a recent day, Google refuses the cap; add `--allow-quota-decrease-below-usage` to the first command, and tell the user, since something called pollen far more than the app does.

**Without `gcloud`**, give the user these steps in the Cloud console (https://console.cloud.google.com):

1. Pick or create a project, and make sure billing is on.
2. APIs & Services → Library → "Pollen API" → Enable.
3. APIs & Services → Credentials → Create credentials → API key. Edit the key: under API restrictions, restrict it to the Pollen API.
4. Copy the key into `.env` as `GOOGLE_POLLEN_API_KEY=<key>`: they open `.env` in an editor and add the line (replacing one that's already there).
5. Cap the calls: APIs & Services → Pollen API → Quotas & System Limits. Set the forecast's per-day limit ("Pollen - Forecast Usage", per day) to 150 and the heatmap's per-day limit ("Pollen - HeatMap Usage", per day) to 0.

Also create a billing budget alert in the project's Billing → Budgets & alerts, with an amount the user chooses and email alerts enabled. An alert does not stop spending. Check restrictions on an existing key too: `gcloud services api-keys list` and `gcloud services api-keys describe <key-id>`; its API target must be `pollen.googleapis.com`. Verify the quota with the command above.

The optional `[[pollen_seasons]]` blocks in `config.example.toml` show typical northeastern US dates. Copy them only if they fit the home; elsewhere use local typical dates and say where they came from. They are a calendar, not a forecast.

## The road

In this version the road is off for new homes: `setup.py` leaves the `[road]` section out. The page then has no road, no rush-hour rule and no exhaust on the map.

If the user wants one later, a road needs a route file. It's possible to build, but untested:

- A JSON array of `[longitude, latitude]` points in order along the road (the `coordinates` of a GeoJSON LineString, without the wrapper). `static/bqe.json`, the demo's road, is an example: 120 points.
- At least one point within 2 km of the home, or set `toward` by hand: the compass bearings (degrees) from the home toward the road, `[min, max]`.
- Then fill `[road]`: `name`, `route` (the file's path from the repo folder), `rush` (`[start hour, end hour, label]`, 24-hour clock).

A route can be traced from OpenStreetMap data, but nothing in this repo does it yet.

## Adding a profile

A profile is code, not a setting. To add one, touch each of these and keep the tests green (`pytest -q && node --test tests/`):

- `config.py`: add it to `PROFILES`.
- `summary.py`: its state in `profiles_row`, and which items serve it.
- `air_read.py`: its line in `build_profiles`.
- `phrases.py`: its sentences, in `PILLS`.
- `static/home.js`, `static/app.js`, `static/summary.js`: its name, icon and wording.
- `index.html`: its chip under "Profiles" in the Home menu.
- `config.example.toml`: a commented line under `[profiles]`.
- `demo/` and its tests: the demo moments are the test fixtures, so a new profile shows up in them in the same commit.

## The demo on Vercel

The public demo runs on Vercel (`vercel.json`), with no keys. `DEMO=1` is set in the Vercel project's environment variables, not in `vercel.json`: a new Vercel project needs it added there. Live data isn't tested there: the server refreshes your monitors' readings in the background, and that hasn't been tried on Vercel's functions.

