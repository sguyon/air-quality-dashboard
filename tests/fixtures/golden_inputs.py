"""Made-up inputs for the golden test: one payload and canned upstreams, all generated here (no real readings).

The story: Tue 21 Apr 2026. CO₂ 1,240 after a stale night (over 800 from 10 PM to 7 AM); indoor humidity 64% with
wetter air outside; the wind from 135° (south-east) all day, so the morning and evening rushes blow toward home;
outdoor PM2.5 clean until mid-afternoon, then rising to 25 at 7 PM; tree pollen 4 of 5.
Times are New York local, as Open-Meteo returns them for the reference home.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
MORNING = datetime(2026, 4, 21, 7, 45, tzinfo=TZ)   # the brief's moment: in the morning rush
EVENING = datetime(2026, 4, 21, 16, 30, tzinfo=TZ)  # in the evening rush, with the PM2.5 peak ahead

PAYLOAD = {
    "indoor_co2": 1240, "indoor_humidity": 64, "indoor_temp_c": 21, "indoor_pm25": 3,
    "outdoor_pm25": 7, "outdoor_humidity": 85, "outdoor_temp_c": 20,
    "indoor_location_id": 1, "outdoor_location_id": 2,
}

DAYS = [datetime(2026, 4, 20, tzinfo=TZ) + timedelta(days=d) for d in range(3)]   # 20, 21, 22 April
HOURS = [d + timedelta(hours=h) for d in DAYS for h in range(24)]


def key(t):
    return t.strftime("%Y-%m-%dT%H:00")


def pm_at(hour):
    """The air model's outdoor PM2.5 by hour of day: clean, then the evening build-up to 25 at 7 PM."""
    return {16: 12, 17: 16, 18: 21, 19: 25, 20: 22, 21: 17, 22: 12}.get(hour, 7)


def wind_at(hour):
    return 300 if hour >= 23 or hour < 5 else 135   # away overnight, south-east from 5 AM


WEATHER = {
    "current": {"temperature_2m": 20, "relative_humidity_2m": 85, "dew_point_2m": 17.4, "wind_direction_10m": 135,
                "wind_speed_10m": 9, "uv_index": 2, "weather_code": 3, "visibility": 16000, "cloud_cover": 60},
    "hourly": {
        "time": [key(t) for t in HOURS],
        "temperature_2m": [12 + 6 * (11 <= t.hour <= 17) for t in HOURS],
        "dew_point_2m": [15 if t.hour < 12 else 9 for t in HOURS],   # the afternoon dries out
        "precipitation_probability": [70 if t.hour in (13, 14) else 10 for t in HOURS],
        "precipitation": [0.6 if t.hour in (13, 14) else 0 for t in HOURS],
        "weather_code": [61 if t.hour in (13, 14) else 3 for t in HOURS],
        "uv_index": [7 if 11 <= t.hour <= 14 else 2 for t in HOURS],
        "wind_direction_10m": [wind_at(t.hour) for t in HOURS],
        "wind_speed_10m": [9 for _ in HOURS],
    },
    "daily": {"time": [d.strftime("%Y-%m-%d") for d in DAYS],
              "sunrise": [d.strftime("%Y-%m-%dT06:17") for d in DAYS],
              "sunset": [d.strftime("%Y-%m-%dT19:38") for d in DAYS]},
}

AIR = {key(t): pm_at(t.hour) for t in HOURS}

SMOKE = {"checked": True, "detected": False, "density": None, "date": "2026-04-21"}

POLLEN = {
    "today": [{"name": "Tree", "level": "High", "index": 4, "in_season": True},
              {"name": "Grass", "level": "Very Low", "index": 1, "in_season": True},
              {"name": "Weed", "level": "None", "index": 0, "in_season": False}],
    "tomorrow": [{"name": "Tree", "level": "Moderate", "index": 3, "in_season": True},
                 {"name": "Grass", "level": "Very Low", "index": 1, "in_season": True},
                 {"name": "Weed", "level": "None", "index": 0, "in_season": False}],
}


def history(location_id, now_local, hours=24):
    """Ten-minute readings for the last day, up to five minutes ago, like server.history_points returns them."""
    out = []
    t = now_local - timedelta(hours=hours)
    while t <= now_local - timedelta(minutes=5):
        if location_id == 1:   # indoor
            night = t.hour >= 22 or t.hour < 7
            recent = now_local - t <= timedelta(minutes=90)
            co2 = 1240 if recent else 1100 + 5 * (t.minute // 10) if night else 690
            rh = 64 if now_local - t <= timedelta(hours=5) else 55
            out.append((t, {"timestamp": t.isoformat(), "rco2": co2, "rhum": rh, "atmp": 21, "pm02": 3}))
        elif location_id == 2:   # outdoor: the monitor reads what the model says, so calibration keeps its level
            out.append((t, {"timestamp": t.isoformat(), "pm02": pm_at(t.hour), "rhum": 85, "atmp": 20}))
        t += timedelta(minutes=10)
    return out


def install(server, monkeypatch, now):
    """Point every upstream the summary and /api/context read at the canned data above, at a fixed clock."""
    monkeypatch.setattr(server, "local_now", lambda: now)
    monkeypatch.setattr(server, "get_open_meteo_data", lambda *a, **k: WEATHER)
    monkeypatch.setattr(server, "get_air_forecast", lambda *a, **k: dict(AIR))
    monkeypatch.setattr(server, "smoke_status", lambda *a, **k: dict(SMOKE))
    monkeypatch.setattr(server, "get_smoke_data", lambda *a, **k: SMOKE["detected"])
    monkeypatch.setattr(server, "get_pollen_days", lambda *a, **k: {d: [dict(p) for p in v] for d, v in POLLEN.items()})
    monkeypatch.setattr(server, "get_pollen_data", lambda *a, **k: [dict(p) for p in POLLEN["today"]])
    monkeypatch.setattr(server, "history_points", history)
