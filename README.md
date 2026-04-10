# Air Quality Dashboard

Real-time indoor/outdoor air quality monitoring with AI-powered analysis. Compare sensor readings, track neighborhood air quality, and get actionable insights about your local environment.

**🌐 Live Dashboard:** https://web-production-c9ff2.up.railway.app/

## Features

- **Dual Monitor Tracking** — Real-time indoor/outdoor sensor data side-by-side
- **AQI Visualization** — EPA-standard color coding with visual ring indicators
- **Time Navigation** — Jump back in time (1h, 6h, 24h, 7d) with Chart.js historical graphs
- **Neighborhood Comparison** — See how your air quality ranks vs. nearby monitors within 15km
- **AI Analysis** — Claude-powered insights contextual to Greenpoint/Brooklyn (auto-analyzes every 5-10 min with smart caching)
- **Dark/Light Mode** — Smooth theme switching with View Transitions API
- **Responsive Design** — Works on desktop and mobile
- **Progressive Web App** — Install on home screen (Android/iOS/desktop), works offline with cached data

## Install on Mobile / Home Screen

The dashboard is a Progressive Web App (PWA) — you can install it like a native app on any device.

### Android (Chrome)
1. Open https://air-quality-dashboard.up.railway.app/
2. Tap menu (⋮) in the top-right → **"Install app"**
   - Or wait for the browser's install prompt to appear
3. App installs to your home screen, opens fullscreen

### iOS (Safari 15.4+)
1. Open https://air-quality-dashboard.up.railway.app/ in Safari
2. Tap the **Share** button (bottom or top-right)
3. Scroll down and tap **"Add to Home Screen"**
4. Tap **"Add"** — app now on your home screen

### Desktop (Chrome/Edge)
1. Open https://air-quality-dashboard.up.railway.app/
2. Click the **install icon** in the address bar (or menu → "Install app")
3. Opens as a standalone window (no browser UI)

### Features When Installed
- ✅ **Offline Support** — View last cached data even without internet
- ✅ **Fullscreen App** — No browser toolbar, looks like a native app
- ✅ **Fast Loading** — Static assets cached on first visit
- ✅ **Auto-Updates** — Service worker checks for updates every 60s

## Local Setup

### Prerequisites
- Python 3.8+
- AirGradient API token
- Anthropic API key (optional, for AI analysis)

### Installation

```bash
# Clone the repo
git clone https://github.com/sguyon/air-quality-dashboard.git
cd dashboard

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

Open `http://localhost:5555` in your browser.

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `AIRGRADIENT_TOKEN` | ✅ Yes | `13fbc6cc-f061-47b5-be1e-...` |
| `ANTHROPIC_API_KEY` | Optional | `sk-ant-api03-...` |
| `PORT` | Optional | `5555` (default) |

Get your AirGradient token from [dashboard.airgradient.com](https://dashboard.airgradient.com).  
Get your Anthropic API key from [console.anthropic.com](https://console.anthropic.com).

## How AI Analysis Works

The dashboard automatically analyzes air quality every 5-10 minutes when sensor data changes significantly. The top card shows Claude-powered insights with a narrative arc:

1. **Status** — "Your air is GOOD" (color-coded: green/yellow/red)
2. **Why** — What's driving the reading (traffic patterns, weather, time of day)
3. **You Can Do** — Ranked actions with expected outcomes
4. **Did You Know?** — Fun fact or personal trend

### Cost Optimization
- **Model:** Claude Haiku 4.5 (cost: ~$0.0015 per significant data change)
- **Smart Caching:** Hashes current readings; skips API call if data unchanged
- **Result:** Same cost as manual analysis, but no clicking required
- **Fallback:** If offline, shows last cached insight with timestamp

### Manual Analysis
Click the ↻ button on the AI insights card to force an immediate refresh.

## Deployment Notifications

Get instant notifications when deployments happen (no need to check Railway dashboard constantly).

### Setup Slack Notifications

1. **Create a Slack webhook:**
   - Go to [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)
   - Click "Create New App" → "From scratch"
   - Give it a name (e.g., "Railway Deployer")
   - Select your workspace
   - Enable "Incoming Webhooks" and create a webhook for your channel

2. **Add webhook to Railway:**
   - Go to Railway project → Settings → **Webhooks**
   - Click "Create Webhook"
   - Paste your Slack webhook URL
   - Enable events: `deployment.success`, `deployment.failure`

3. **Done** — You'll get Slack messages when deployments start/finish

**Alternative:** Railway also supports Discord, email, and custom webhooks. Configure in the same Settings → Webhooks section.

## Tech Stack

- **Backend:** Flask + Gunicorn (Python)
- **Frontend:** Vanilla JavaScript, Chart.js, CSS custom properties
- **API Integration:** AirGradient Public API, Anthropic API
- **Deployment:** Railway (auto-deploy on push)
- **Theme System:** CSS variables with View Transitions API
- **PWA:** Service Worker, Web App Manifest, offline caching

## Testing & Debugging

**Build Info Display** — Top-right corner shows deployment metadata:
```
v2 · abc1234 · 15:23:45 UTC
```
This helps you verify the page has updated after a deployment. Hover to brighten the text.

## Metrics Tracked

- **PM1, PM2.5, PM10** — Particulate matter (µg/m³)
- **CO2** — Carbon dioxide (ppm)
- **Temperature** — Fahrenheit (with Celsius)
- **Humidity** — Percentage
- **VOC Index** — Volatile organic compounds
- **NOx Index** — Nitrogen oxides

## License

MIT
