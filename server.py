"""AirGradient Dashboard — Local proxy server.

Deployed on Railway with Anthropic API integration for AI analysis.
"""

import json
import math
import os
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
import requests

# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

app = Flask(__name__)

API_BASE = "https://api.airgradient.com/public/api/v1"
TOKEN = os.environ.get("AIRGRADIENT_TOKEN", "")
HOME_LAT = 40.72717732493724
HOME_LON = -73.9506644567995
NEARBY_RADIUS_KM = 15


def get_build_info():
    """Get git commit hash and deployment time."""
    try:
        # Get latest commit hash (short 7 chars)
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        commit = "unknown"

    # Current deploy time
    time_str = datetime.now().strftime("%H:%M:%S UTC")

    return f"v2 · {commit} · {time_str}"


def api_get(path, params=None):
    p = {"token": TOKEN}
    if params:
        p.update(params)
    try:
        r = requests.get(f"{API_BASE}{path}", params=p, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        raise RuntimeError(f"AirGradient API returned {status}: {e.response.text[:300]}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"AirGradient API unreachable: {e}") from e


def get_open_meteo_data(lat, lon):
    """Fetch weather + allergen data from Open-Meteo (free, no API key)."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,visibility,uv_index",
                "timezone": "America/New_York"
            },
            timeout=10
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        # Gracefully degrade if Open-Meteo fails
        return {
            "current": {
                "wind_speed_10m": None,
                "wind_direction_10m": None,
                "visibility": None,
                "uv_index": None
            }
        }


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


@app.route("/")
def index():
    html_path = Path(__file__).parent / "index.html"
    html = html_path.read_text()

    # Inject build info into a data attribute on the body
    build_info = get_build_info()
    html = html.replace(
        '<body>',
        f'<body data-build="{build_info}">'
    )

    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/test")
def test():
    html_path = Path(__file__).parent / "index2.html"
    html = html_path.read_text()

    # Inject build info into a data attribute on the body
    build_info = get_build_info()
    html = html.replace(
        '<body>',
        f'<body data-build="{build_info}">'
    )

    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/manifest.json")
def manifest():
    return send_file(Path(__file__).parent / "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_file(Path(__file__).parent / "sw.js", mimetype="application/javascript")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "airgradient_token_set": bool(TOKEN),
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.route("/api/current")
def current():
    try:
        return jsonify(api_get("/locations/measures/current"))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/history/<int:location_id>")
def history(location_id):
    params = {}
    if request.args.get("from"):
        params["from"] = request.args["from"]
    if request.args.get("to"):
        params["to"] = request.args["to"]
    try:
        return jsonify(api_get(f"/locations/{location_id}/measures/past", params))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/neighborhood")
def neighborhood():
    try:
        r = requests.get(
            f"{API_BASE}/world/locations/measures/current", timeout=15
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Neighborhood data unavailable: {e}"}), 502
    nearby = []
    for loc in data:
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat and lon:
            d = haversine_km(HOME_LAT, HOME_LON, lat, lon)
            if d < NEARBY_RADIUS_KM:
                loc["distance_km"] = round(d, 1)
                nearby.append(loc)
    nearby.sort(key=lambda x: x["distance_km"])
    return jsonify(nearby)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Stream LLM analysis of current air quality data with weather context."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 500

    data = request.json

    indoor_pm25 = float(data.get('indoor_pm25', 0))
    outdoor_pm25 = float(data.get('outdoor_pm25', 0))
    indoor_co2 = float(data.get('indoor_co2', 0))
    indoor_humidity = float(data.get('indoor_humidity', 50))
    neighbor_rank = int(data.get('neighbor_rank', 1))
    neighbor_count = int(data.get('neighbor_count', 1))

    # Determine status
    if indoor_pm25 <= 12 and indoor_co2 <= 600:
        status = "GOOD"
    elif indoor_pm25 <= 35 and indoor_co2 <= 800:
        status = "FAIR"
    else:
        status = "POOR"

    # Fetch weather context from Open-Meteo (free API, no key needed)
    weather = get_open_meteo_data(HOME_LAT, HOME_LON)
    current = weather.get("current", {})
    wind_speed = current.get("wind_speed_10m")
    wind_direction = current.get("wind_direction_10m")
    visibility = current.get("visibility")
    uv_index = current.get("uv_index")

    # Map wind direction to cardinal
    def get_wind_cardinal(degrees):
        if degrees is None: return "variable"
        dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return dirs[round(degrees / 22.5) % 16]

    wind_dir = get_wind_cardinal(wind_direction)

    # Seasonal allergen triggers (Greenpoint, New York)
    from datetime import datetime
    month = datetime.now().month
    if month in [4, 5]:
        allergen_season = "TREE (birch, maple) pollen season - high respiratory risk"
    elif month in [6, 7, 8]:
        allergen_season = "GRASS + MOLD SPORE season - sinus/bronchial inflammation risk"
    elif month in [8, 9, 10]:
        allergen_season = "RAGWEED + MOLD SPORE peak - severe allergy season"
    else:
        allergen_season = "Low pollen season - mold spores still present indoors"

    # Health context
    humidity_status = "ideal" if 30 <= indoor_humidity <= 50 else "dry" if indoor_humidity < 30 else "humid"
    humidity_risk = "Sinus dryness risk" if indoor_humidity < 30 else "Mold growth risk" if indoor_humidity > 60 else "Clear nasal passages"

    prompt = f"""You are a HEALTH-FOCUSED air quality coach for someone with allergies/sinus sensitivity in Greenpoint, Brooklyn.

CURRENT CONDITIONS:
- INDOOR: PM2.5={indoor_pm25} µg/m³, CO2={indoor_co2} ppm, Humidity={indoor_humidity}% ({humidity_status})
- OUTDOOR: PM2.5={outdoor_pm25} µg/m³
- WEATHER: Wind {wind_speed} km/h from {wind_dir}, Visibility {visibility}m, UV Index {uv_index}
- GREENPOINT RANK: {neighbor_rank}/{neighbor_count} cleanest
- SEASONAL: {allergen_season}

HEALTH-FIRST INSTRUCTIONS:
1. Lead with sinus/allergy outcomes ("sinuses happy", "congestion prevented", "breathing easier")
2. Explain humidity connection to symptoms: 40%=clear nasal passages, <30%=sinus dryness risk, >60%=mold risk
3. Tie wind direction to BQE traffic impact: West wind = BQE pollution incoming
4. Reference allergen types being blocked (dust mites, mold spores, tree/grass/ragweed pollen)
5. Use health metrics: "30-40% fewer infections", "reduce sinus headache risk", "better sleep quality"
6. Include seasonal context (April=birch, Aug=ragweed, winter=mold dormancy = relief window)

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "status": "{status}",
  "status_line": "[Health outcome in one sentence, e.g. 'Your sinuses are happy right now']",
  "rank": "{neighbor_rank}/{neighbor_count}",
  "metrics": [
    {{"icon": "🫁", "category": "Particulates", "status": "Excellent/Fair/Poor", "value": "{indoor_pm25} µg/m³", "benefit": "[Health impact, e.g. 'Blocking X% of street dust']"}},
    {{"icon": "💧", "category": "Humidity", "status": "{humidity_status.upper()}", "value": "{indoor_humidity}%", "benefit": "{humidity_risk}"}},
    {{"icon": "🌬️", "category": "Ventilation", "status": "Healthy/Watch/Act", "value": "{indoor_co2} ppm", "benefit": "[Mental clarity, breathing outcome]"}}
  ],
  "working": [
    "[Bullet point about what's protecting their health right now]",
    "[Another protection working]",
    "[Third protection if relevant]"
  ],
  "next_steps": [
    "[SPECIFIC action (time, method, why it matters, expected outcome)]",
    "[Action 2]",
    "[Action 3 if urgent]"
  ],
  "insight": "[Seasonal or Greenpoint-specific insight, e.g. 'April is high birch pollen — watch outdoor readings']"
}}"""

    def stream():
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 2048,
                "stream": True,
                "messages": [{"role": "user", "content": prompt}],
            },
            stream=True,
            timeout=30,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                    if event.get("type") == "content_block_delta":
                        text = event["delta"].get("text", "")
                        if text:
                            yield f"data: {json.dumps({'text': text})}\n\n"
                    elif event.get("type") == "message_stop":
                        break
                except json.JSONDecodeError:
                    pass
        yield "data: [DONE]\n\n"

    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("⚠  ANTHROPIC_API_KEY not set — LLM analysis disabled")
        print("   Run: ANTHROPIC_API_KEY=sk-... python server.py")
    port = int(os.environ.get("PORT", 5555))
    print(f"AirGradient Dashboard → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
