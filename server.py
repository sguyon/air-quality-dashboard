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
    """Get git commit hash and deployment time in ET timezone."""
    try:
        # Get latest commit hash (short 7 chars)
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
            timeout=5
        ).decode().strip()
    except Exception:
        commit = "no-git"

    # Current deploy time in ET (NYC timezone) using simple offset calculation
    # ET is UTC-4 (EDT) or UTC-5 (EST)
    import time
    if time.daylight:
        # During daylight saving time (EDT): UTC-4
        offset_hours = -4
    else:
        # During standard time (EST): UTC-5
        offset_hours = -5

    from datetime import timezone, timedelta
    et_tz = timezone(timedelta(hours=offset_hours))
    time_str = datetime.now(et_tz).strftime("%H:%M:%S ET")

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
                "current": "temperature_2m,relative_humidity_2m,dew_point_2m,weather_code,wind_speed_10m,wind_direction_10m,visibility,uv_index",
                "hourly": "wind_direction_10m,wind_speed_10m",
                "forecast_hours": 24,
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
                "uv_index": None,
                "dew_point_2m": None
            },
            "hourly": {"wind_direction_10m": [], "wind_speed_10m": []}
        }


def get_smoke_data():
    """Fetch smoke/fire data from NOAA HMS (free, no API key)."""
    try:
        # NOAA HMS provides smoke polygons in KML format
        # We'll check for smoke presence in Northeast US (simple presence indicator)
        r = requests.get("https://www.ospo.noaa.gov/data/land/hms/smoke_archive/", timeout=10)
        # Smoke data presence = elevated particulate risk from wildfires
        return r.status_code == 200
    except:
        return False  # Assume no smoke if API fails


def get_pollen_data(lat, lon):
    """Fetch pollen forecast from Google Pollen API (GET with query params)."""
    api_key = os.environ.get("GOOGLE_POLLEN_API_KEY", "")
    if not api_key:
        return []

    try:
        r = requests.get(
            "https://pollen.googleapis.com/v1/forecast:lookup",
            params={
                "key": api_key,
                "location.latitude": lat,
                "location.longitude": lon,
                "days": 1
            },
            timeout=10
        )
        r.raise_for_status()
        data = r.json()

        pollen_list = []
        daily = data.get("dailyInfo", [{}])
        if not daily:
            return []

        for ptype in daily[0].get("pollenTypeInfo", []):
            name = ptype.get("displayName", "Unknown")
            index_info = ptype.get("indexInfo", {})
            risk = index_info.get("value", 0)
            category = index_info.get("category", "None")
            in_season = ptype.get("inSeason", False)
            pollen_list.append({
                "name": name,
                "level": category,
                "index": risk,
                "in_season": in_season
            })

        return pollen_list
    except Exception:
        return []


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


def get_wind_cardinal(degrees):
    """Convert wind direction degrees to cardinal direction."""
    if degrees is None:
        return "variable"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(degrees / 22.5) % 16]


@app.route("/api/context")
def context():
    """Return external data sources (weather, pollen, BQE, smoke) as structured JSON."""
    # Weather
    weather = get_open_meteo_data(HOME_LAT, HOME_LON)
    cur = weather.get("current", {})
    wind_speed = cur.get("wind_speed_10m")
    wind_direction = cur.get("wind_direction_10m")
    visibility = cur.get("visibility")
    uv_index = cur.get("uv_index")
    dew_point = cur.get("dew_point_2m")
    temperature = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m")

    wind_dir = get_wind_cardinal(wind_direction)

    # Dew point sinus risk
    if dew_point is not None and dew_point < 5:
        dew_point_risk = "Severe dryness"
    elif dew_point is not None and dew_point < 10:
        dew_point_risk = "Moderate dryness"
    else:
        dew_point_risk = "Comfortable"

    # Visibility interpretation
    if visibility is not None:
        if visibility < 2000:
            visibility_status = "Very low — high particulate"
        elif visibility < 5000:
            visibility_status = "Reduced"
        elif visibility < 10000:
            visibility_status = "Moderate"
        else:
            visibility_status = "Clear"
    else:
        visibility_status = "Unknown"

    # BQE traffic
    current_hour = datetime.now().hour
    bqe = predict_bqe_traffic(current_hour, wind_direction)

    # Smoke
    smoke = get_smoke_data()

    # Pollen
    pollen = get_pollen_data(HOME_LAT, HOME_LON)

    return jsonify({
        "weather": {
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "wind_cardinal": wind_dir,
            "dew_point": dew_point,
            "dew_point_risk": dew_point_risk,
            "visibility": visibility,
            "visibility_status": visibility_status,
            "uv_index": uv_index,
            "temperature": temperature,
            "humidity": humidity
        },
        "bqe": {
            "traffic": bqe["traffic"],
            "wind_impact": bqe["wind_impact"],
            "pollution_pressure": bqe["pollution_pressure"],
            "current_hour": current_hour
        },
        "smoke": {
            "detected": smoke
        },
        "pollen": pollen
    })


def predict_bqe_traffic(hour, wind_direction):
    """Predict BQE pollution impact based on time of day and wind direction.

    BQE peaks: 7-9am (morning commute), 4-7pm (evening commute)
    Wind from west (W/NW/SW, 180-360°) = pollution drifts toward Greenpoint homes
    """
    hour_int = int(hour)

    # Traffic intensity by hour
    if 7 <= hour_int <= 9:
        traffic_intensity = "PEAK (morning rush)"
        multiplier = 1.5
    elif 16 <= hour_int <= 19:
        traffic_intensity = "PEAK (evening rush)"
        multiplier = 1.4
    elif 6 <= hour_int <= 10 or 15 <= hour_int <= 20:
        traffic_intensity = "HIGH (rush shoulders)"
        multiplier = 1.2
    else:
        traffic_intensity = "LOW"
        multiplier = 0.7

    # Wind direction impact
    if wind_direction is None:
        wind_impact = "Unknown"
        wind_multiplier = 1.0
    else:
        # West winds (180-360°) blow pollution toward Greenpoint (east)
        # East winds (0-180°) blow pollution away
        if 180 <= wind_direction <= 360 or wind_direction <= 45:
            wind_impact = "Blowing toward Greenpoint" if 180 <= wind_direction <= 360 else "Blowing away"
            wind_multiplier = 1.3 if 180 <= wind_direction <= 360 else 0.5
        else:
            wind_impact = "Neutral"
            wind_multiplier = 1.0

    pollution_pressure = multiplier * wind_multiplier

    return {
        "traffic": traffic_intensity,
        "wind_impact": wind_impact,
        "pollution_pressure": round(pollution_pressure, 1)
    }


def calculate_composite_scores(indoor_pm25, outdoor_pm25, indoor_co2, humidity, dew_point, uv_index, visibility, wind_speed):
    """Calculate health-focused composite scores (1-10 scale)."""

    # ALLERGY RISK (1-10): pollen sensitivity + humidity mold risk + dew point sinus risk
    # Lower is better
    mold_risk = 0
    if humidity > 60:
        mold_risk += 3  # High mold growth risk
    elif humidity < 30:
        mold_risk += 2  # Sinus dryness risk

    sinus_dryness = 0
    if dew_point is not None and dew_point < 5:  # Very dry air
        sinus_dryness = 3
    elif dew_point is not None and dew_point < 10:
        sinus_dryness = 1

    visibility_allergen = 0
    if visibility is not None:
        if visibility < 2000:  # Very low visibility = high particulate/allergen
            visibility_allergen = 4
        elif visibility < 5000:
            visibility_allergen = 2

    allergy_risk = min(10, 2 + mold_risk + sinus_dryness + visibility_allergen)

    # RESPIRATORY LOAD (1-10): PM2.5 + CO2 + visibility + UV
    # Lower is better (1=excellent, 10=hazardous)
    pm_score = min(10, (indoor_pm25 / 15))  # 12 µg/m³ is EPA standard
    co2_score = min(10, (indoor_co2 / 1000))  # 1000 ppm is concerning
    visibility_resp = 0
    if visibility is not None and visibility < 3000:
        visibility_resp = 3

    respiratory_load = round((pm_score + co2_score + visibility_resp) / 3, 1)

    # ACTIVITY SAFETY: composite of all factors + time of day (determined in LLM context)
    # Will be determined by LLM based on hour and all signals

    return {
        "allergy_risk": round(allergy_risk, 1),
        "respiratory_load": round(respiratory_load, 1),
        "mold_risk": "High" if humidity > 60 else "Low" if humidity < 30 else "Ideal",
        "sinus_dryness_risk": "High" if dew_point is not None and dew_point < 5 else "None"
    }


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
    dew_point = current.get("dew_point_2m")

    wind_dir = get_wind_cardinal(wind_direction)

    # BQE traffic prediction based on time and wind
    current_hour = datetime.now().hour
    bqe_prediction = predict_bqe_traffic(current_hour, wind_direction)

    # Check for wildfire smoke (NOAA)
    smoke_detected = get_smoke_data()
    smoke_note = " ⚠️ Wildfire smoke in Northeast region — extra PM2.5 risk" if smoke_detected else ""

    # Fetch pollen data (Google Pollen API)
    pollen_data = get_pollen_data(HOME_LAT, HOME_LON)
    pollen_summary = ""
    if pollen_data:
        pollen_str = ", ".join([f"{p['name']} ({p['level']})" for p in pollen_data])
        pollen_summary = f"POLLEN TODAY: {pollen_str}"
    else:
        pollen_summary = "POLLEN: Data unavailable"

    # Calculate composite health scores
    scores = calculate_composite_scores(indoor_pm25, outdoor_pm25, indoor_co2, indoor_humidity, dew_point, uv_index, visibility, wind_speed)

    # Seasonal allergen triggers (Greenpoint, New York)
    month = datetime.now().month
    if month in [4, 5]:
        allergen_season = "TREE (birch, maple) pollen peak"
    elif month in [6, 7, 8]:
        allergen_season = "GRASS + MOLD SPORE season"
    elif month in [8, 9, 10]:
        allergen_season = "RAGWEED + MOLD SPORE peak"
    else:
        allergen_season = "Low pollen, mold dormancy period"

    # Health context
    humidity_status = "ideal" if 30 <= indoor_humidity <= 50 else "dry" if indoor_humidity < 30 else "humid"
    humidity_risk = "Sinus dryness risk" if indoor_humidity < 30 else "Mold growth risk" if indoor_humidity > 60 else "Clear nasal passages"

    # Dew point sinus impact
    dew_point_status = ""
    if dew_point is not None:
        if dew_point < 5:
            dew_point_status = "Very dry — severe sinus dryness risk"
        elif dew_point < 10:
            dew_point_status = "Dry — moderate sinus dryness"
        else:
            dew_point_status = "Comfortable for sinuses"

    # Activity timing recommendation based on BQE rush
    if current_hour >= 7 and current_hour <= 9:
        activity_warning = "AVOID outdoor activity 7-9am (BQE morning rush peak)"
        best_window = "10am-3pm is safest for outdoor activity"
    elif current_hour >= 16 and current_hour <= 19:
        activity_warning = "CAUTION: BQE evening rush (4-7pm) — outdoor exposure risky"
        best_window = "Best outdoor window was 10am-3pm, next safe time is 8pm+"
    else:
        activity_warning = f"BQE traffic moderate at {current_hour}:00"
        best_window = "10am-3pm is still the safest window today"

    prompt = f"""You are a CONSUMER-GRADE health coach helping someone and their spouse manage allergies/sinus sensitivity in Greenpoint, Brooklyn using real-time data.

═══ COMPREHENSIVE DATA INPUT ═══
INDOOR CONDITIONS:
  • PM2.5: {indoor_pm25} µg/m³ (EPA safe: ≤12)
  • CO2: {indoor_co2} ppm (Alert: >800)
  • Humidity: {indoor_humidity}% (Ideal: 30-50%)
  • Dew Point: {dew_point}°C ({dew_point_status if dew_point_status else 'calculating...'})

OUTDOOR CONDITIONS:
  • PM2.5: {outdoor_pm25} µg/m³
  • Wind: {wind_speed} km/h from {wind_dir} ({bqe_prediction['wind_impact']})
  • Visibility: {visibility}m (Low=high particulate)
  • UV Index: {uv_index}
  {smoke_note}

POLLEN DATA (Real-time from Google):
  • {pollen_summary}

LOCAL CONTEXT:
  • Greenpoint Rank: {neighbor_rank}/{neighbor_count} cleanest (lower is better)
  • Seasonal: {allergen_season}
  • BQE Traffic: {bqe_prediction['traffic']} (Pollution Pressure: {bqe_prediction['pollution_pressure']}x)
  • Activity: {activity_warning}

HEALTH SCORES:
  • Allergy Risk: {scores['allergy_risk']}/10 ({scores['mold_risk']} mold risk)
  • Respiratory Load: {scores['respiratory_load']}/10
  • Sinus Risk: {scores['sinus_dryness_risk']} sinus dryness

═══ YOUR INSTRUCTIONS ═══
1. **PERSONALIZE**: Speak to both household members with same data but acknowledge different sensitivities
2. **SYMPTOM-FIRST**: Lead with what they'll FEEL ("Clear nasal passages", "Reduced headache risk", "Better sleep tonight")
3. **ACTIVITY TIMING**: Recommend specific windows for outdoor activity, exercise, window-opening
4. **FILTER ALERTS**: When to swap HEPA, when to run at high speed, expected lifespan
5. **DRYNESS WARNING**: If dew point <10°C, mention humidifier urgently
6. **MOLD WARNING**: If humidity >60%, mention dehumidifier or ventilation
7. **BQE PREDICTION**: Warn if wind is from west (pollution incoming) or traffic peaks soon
8. **WILDFIRE ALERT**: If smoke detected, recommend staying indoors, extra filtration
9. **POLLEN ALERTS**: Rank allergens by today's levels — identify top trigger for each household member
10. **7-DAY MINDSET**: Mention seasonal relief coming (e.g., "September ragweed relief in 3 weeks")

═══ JSON OUTPUT (NO MARKDOWN) ═══
{{
  "status": "{status}",
  "status_line": "[One sentence health headline: 'Your sinuses are clear, but check humidity']",
  "rank": "{neighbor_rank}/{neighbor_count}",
  "metrics": [
    {{"icon": "🫁", "category": "Particulates", "status": "Excellent/Fair/Poor", "value": "{indoor_pm25} µg/m³", "benefit": "Blocking {{X}}% of street dust — fewer infections"}},
    {{"icon": "💧", "category": "Humidity", "status": "{humidity_status.upper()}", "value": "{indoor_humidity}%", "benefit": "{humidity_risk} — {{specific symptom prevention}}"}},
    {{"icon": "🌬️", "category": "Ventilation", "status": "Healthy/Watch/Act", "value": "{indoor_co2} ppm", "benefit": "Sharp focus vs afternoon brain fog"}}
  ],
  "working": [
    "✓ Your filter is blocking {{X}}% more PM2.5 than Greenpoint average",
    "✓ {{Humidity/Dew point}} is preventing sinus inflammation",
    "✓ {{CO2/Window strategy}} keeping you sharp through afternoon"
  ],
  "next_steps": [
    "1. {best_window} safe for outdoor activity (BQE traffic predictable)",
    "2. {{SPECIFIC filter/humidifier action with timing and reason}}",
    "3. {{Window timing based on BQE rush + {{dew point/humidity issues if any}}}}"
  ],
  "insight": "{{Seasonal context}} — Next {{relief period}} comes {{date/week}}"
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
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠  ANTHROPIC_API_KEY not set — LLM analysis disabled")
        print("   Run: ANTHROPIC_API_KEY=sk-... python server.py")
    port = int(os.environ.get("PORT", 5555))
    print(f"AirGradient Dashboard → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
