"""AirGradient Dashboard — Local proxy server.

Deployed on Railway with Anthropic API integration for AI analysis.
"""

import json
import math
import os
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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def api_get(path, params=None):
    p = {"token": TOKEN}
    if params:
        p.update(params)
    r = requests.get(f"{API_BASE}{path}", params=p, timeout=10)
    r.raise_for_status()
    return r.json()


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
    return send_file("index.html")


@app.route("/api/current")
def current():
    return jsonify(api_get("/locations/measures/current"))


@app.route("/api/history/<int:location_id>")
def history(location_id):
    params = {}
    if request.args.get("from"):
        params["from"] = request.args["from"]
    if request.args.get("to"):
        params["to"] = request.args["to"]
    return jsonify(api_get(f"/locations/{location_id}/measures/past", params))


@app.route("/api/neighborhood")
def neighborhood():
    data = requests.get(
        f"{API_BASE}/world/locations/measures/current", timeout=15
    ).json()
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
    """Stream LLM analysis of current air quality data."""
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 500

    data = request.json

    prompt = f"""You are an air quality analyst for a home in Greenpoint, Brooklyn (near the BQE and Newtown Creek industrial area). Analyze the current sensor readings and provide practical, specific insights.

Current readings:
- INDOOR: PM2.5={data.get('indoor_pm25')} µg/m³, PM1={data.get('indoor_pm01')} µg/m³, PM10={data.get('indoor_pm10')} µg/m³, CO2={data.get('indoor_co2')} ppm, Temp={data.get('indoor_temp_f')}°F, Humidity={data.get('indoor_humidity')}%, VOC Index={data.get('indoor_voc')}, NOx Index={data.get('indoor_nox')}
- OUTDOOR: PM2.5={data.get('outdoor_pm25')} µg/m³, PM1={data.get('outdoor_pm01')} µg/m³, PM10={data.get('outdoor_pm10')} µg/m³, CO2={data.get('outdoor_co2')} ppm, Temp={data.get('outdoor_temp_f')}°F, Humidity={data.get('outdoor_humidity')}%, VOC Index={data.get('outdoor_voc')}, NOx Index={data.get('outdoor_nox')}
- NEIGHBORHOOD: {data.get('neighbor_count')} monitors within 15km, average PM2.5={data.get('neighbor_avg_pm25')} µg/m³, your rank={data.get('neighbor_rank')}/{data.get('neighbor_count')}

Give 3-4 concise, actionable insights. Be specific to Greenpoint/Brooklyn context (BQE traffic, industrial area, waterfront). Use plain language, no jargon. Each insight should be 1-2 sentences max. Format as a JSON array of objects with "icon" (single emoji), "title" (short), and "desc" (detail) fields."""

    def stream():
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 512,
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
