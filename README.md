# Home Air Quality

I have two [AirGradient](https://www.airgradient.com) monitors at home: one inside, one outside. AirGradient's own dashboard shows the readings well, but not what they mean for me. So I rebuilt the front end around my needs.

The page connects the indoor and outdoor air to more sources: nearby public monitors, weather, pollen, wildfire smoke, and the BQE, the expressway about a kilometer away. Then it answers the questions we actually ask: should I open a window, is the room too damp, is now a good time to run, is pollen season coming, are the monitors working.

The advice is generated with AI: fixed rules decide what to do, and an AI model writes the explanation, checked against the data.

**🌐 Live Dashboard:** https://air-quality-dashboard.up.railway.app/

<p align="center">
  <img src="docs/screenshot.png" alt="Home Air Quality: AI advice, home monitors, history, local conditions and the neighborhood map" width="720" />
</p>

## Features

- **AI summary:** the most pressing answer for my needs (a toddler, sinus and allergies, running) leads, with a picture of why: for damp air, humidity inside vs outside now and over the last 24 hours. Rules decide; Claude writes the explanation (see below). A slim banner says it's AI, from how many sources, and how fresh it is, with a refresh button
- **Need cards:** Toddler (room CO₂), Sinus & allergy (humidity and pollen), Runner (outdoor PM2.5), side by side: the answer, the number with its state, a 24 h chart with the limit (orange past it), and what the reading means
- **Coming up:** the next 12 hours in at most four lines: the best time to air, a good time to run, the BQE rush judged by the forecast wind, rain or snow, big temperature changes, haze or the air clearing (Open-Meteo's air-quality forecast), high pollen tomorrow, dry air at night, strong sun, icy paths, sunrise or sunset. Nothing repeats the headline or a card
- **Home monitors:** indoor and outdoor AirGradient readings: PM2.5, CO₂, temperature and humidity in words, then gases (VOC, NOx) and particles (PM1, PM10), plus status and Wi-Fi. Each card has a small scene that follows the live sky and the weather. Temperatures show in °C by default, with a °F switch in the Weather & theme menu
- **History:** PM2.5 and CO₂, indoors and outdoors, over 1 h, 6 h, 24 h or 7 d. Time over the limit is shaded amber, and hovering one chart marks the same moment on all of them
- **Local conditions:** weather with dew point and sinus dryness, pollen with the usual New York season, a BQE traffic estimate, and a NOAA smoke check. Each card's title links to a public source page, and its dot says whether the source answered
- **Neighborhood:** your outdoor PM2.5 against public AirGradient monitors within 15 km
- **Live sky:** the page background follows the real sun, clouds, wind, rain and outdoor haze. The Weather & theme menu turns it off, previews moments (presets, a random cycle, sliders), and opens a weather view that hides the page. It stays still with reduced motion
- **Light and dark themes:** follows the system setting, with a quick switch in the weather control
- **Installable:** works as a Progressive Web App on Android, iOS, and desktop; offline it shows the last readings and summary

## Install

Open https://air-quality-dashboard.up.railway.app/ and choose **Install app** (Chrome or Edge, Android or desktop) or **Share → Add to Home Screen** (Safari on iOS). The installed app opens full screen and keeps the last readings for offline use.

To refresh the screenshot above after a change: `scripts/screenshot.sh` (needs the local server running, Google Chrome, Node.js and ImageMagick).

## Local Setup

### Prerequisites
- Python 3.9+
- AirGradient API token
- Anthropic API key (optional, for the AI explanations)
- Google Pollen API key (optional, for pollen)

### Installation

```bash
# Clone the repo
git clone https://github.com/sguyon/air-quality-dashboard.git
cd air-quality-dashboard

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "AIRGRADIENT_TOKEN=your_token_here" > .env
echo "ANTHROPIC_API_KEY=your_key_here" >> .env

# Run locally
python server.py
```

Open `http://localhost:5555` in your browser. For auto-reload while editing, run `flask --app server run --port 5555 --reload --no-debugger` instead.

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `AIRGRADIENT_TOKEN` | ✅ Yes | `your-airgradient-token` |
| `ANTHROPIC_API_KEY` | Optional | `your-anthropic-key` |
| `GOOGLE_POLLEN_API_KEY` | Optional | `your-google-pollen-key` |
| `AI_CAP_PER_IP_HOUR` / `AI_CAP_PER_MINUTE` / `AI_CAP_PER_DAY` | Optional | `20` / `10` / `300` (limits on paid model calls; past them the advice uses the rules' wording) |
| `PORT` | Optional | `5555` (default) |

Get your AirGradient token from [dashboard.airgradient.com](https://dashboard.airgradient.com).  
Get your Anthropic API key from [console.anthropic.com](https://console.anthropic.com).

## How the AI Advice Works

The AI summary is written for my three needs: a toddler, sinus and allergies, and running.

1. **Readings.** The page sends the latest monitor readings to `POST /api/analyze` with `"format": "read"`. The server adds Open-Meteo weather, Google Pollen, NOAA smoke, the BQE estimate (hour × wind), and the last 24 hours of indoor and outdoor history.
2. **Rules decide.** Fixed thresholds set the headline action and each need's state and color: indoor CO₂ against 800 ppm for the window, indoor humidity against 30% (too dry) and 60% (too damp), outdoor PM2.5 against 12 and 35 µg/m³ with the BQE rush (7–10 AM, 4–8 PM) and the wind for the run, and the Google pollen index (0 to 5). The window rule also checks whether the outside air is damper than inside. Green means fine, amber means something to do, red means a bad level.
3. **Claude writes.** Claude Haiku 5.5, at low effort, writes two things: one line under the headline on why, and one plain-English line per card on what the reading does to people. It also sees what's coming later (the best time to air, rain, haze), so it can't contradict Coming up. It cannot change an action or a number.
4. **The server checks.** A line that cites a number not in the data, names an appliance, or runs long is replaced by the rule's own line. Without an API key, or if the call fails, everything comes from the rules and the byline says so.

The server reuses a summary for 20 minutes unless the actions, the readings or the hour change, and the page asks for a new one at most every 10 minutes. **Refresh** reloads the readings and writes a new summary, showing each step.

The previous page, with its streaming analysis, stays at `/v1`.

## Branching & Deployments

Features branch off `dev` and merge back through a PR; `dev` is promoted to `main` through another PR. Railway deploys each branch on push:

| Branch | URL | Purpose |
|--------|-----|---------|
| `dev` | https://air-quality-dashboard-dev.up.railway.app/ | Staging |
| `main` | https://air-quality-dashboard.up.railway.app/ | Production |

Locally and on `dev`, a build line and a **Clear cache** button sit under the footer. Production never shows them.

The tab icon, home-screen icon and title also say where you are: **DEV** (amber band) locally and on local network addresses, **PREVIEW** (violet band) on the `dev` deployment, and the plain icon in production (`icon_env()` in `server.py`).

The full workflow and the rules for agents are in `AGENTS.md`.

## Tech Stack

- **Backend:** Flask + Gunicorn (Python)
- **Frontend:** Vanilla JavaScript, inline SVG charts, CSS custom properties. `index.html` holds the markup; `static/` holds `app.css`, `app.js` (data, summary, charts) and `sky.js` (the live sky)
- **Data:** AirGradient Public API, Open-Meteo, Google Pollen, NOAA Hazard Mapping System
- **AI:** Claude Haiku 5.5 through the Anthropic API
- **PWA:** Web app manifest with PNG and maskable icons (`static/icons/`); a service worker that caches `/static/` files by content hash
- **Deployment:** Railway

## License

MIT
