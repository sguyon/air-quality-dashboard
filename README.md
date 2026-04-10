# Air Quality Dashboard

Real-time indoor/outdoor air quality monitoring with AI-powered analysis. Compare sensor readings, track neighborhood air quality, and get actionable insights about your local environment.

**🌐 Live Dashboard:** https://web-production-c9ff2.up.railway.app/

## Features

- **Dual Monitor Tracking** — Real-time indoor/outdoor sensor data side-by-side
- **AQI Visualization** — EPA-standard color coding with visual ring indicators
- **Time Navigation** — Jump back in time (1h, 6h, 24h, 7d) with Chart.js historical graphs
- **Neighborhood Comparison** — See how your air quality ranks vs. nearby monitors within 15km
- **AI Analysis** — Claude-powered insights contextual to Greenpoint/Brooklyn (traffic, industrial patterns, seasonal effects)
- **Dark/Light Mode** — Smooth theme switching with View Transitions API
- **Responsive Design** — Works on desktop and mobile

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

The "✨ Analyze with AI" button sends current sensor readings (indoor/outdoor PM2.5, CO2, humidity, neighborhood data) to Claude Haiku for real-time analysis.

- **Model:** Claude Haiku 4.5 (cost: ~$0.0015 per analysis)
- **Context:** Temperature, humidity, PM metrics, neighborhood ranking
- **Response:** 3-4 actionable insights formatted as cards
- **Streaming:** Real-time response with no UI lag

Manual trigger only — analysis isn't automatic to manage costs.

## Tech Stack

- **Backend:** Flask + Gunicorn (Python)
- **Frontend:** Vanilla JavaScript, Chart.js, CSS custom properties
- **API Integration:** AirGradient Public API, Anthropic API
- **Deployment:** Railway
- **Theme System:** CSS variables with View Transitions API

## Metrics Tracked

- **PM1, PM2.5, PM10** — Particulate matter (µg/m³)
- **CO2** — Carbon dioxide (ppm)
- **Temperature** — Fahrenheit (with Celsius)
- **Humidity** — Percentage
- **VOC Index** — Volatile organic compounds
- **NOx Index** — Nitrogen oxides

## License

MIT
