"""Shared fixtures: the Flask app with every upstream fetch replaced by canned data, so no test touches the network."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

SAMPLE_PAYLOAD = {
    "indoor_co2": 1240, "indoor_humidity": 64, "indoor_temp_c": 21, "outdoor_pm25": 4,
    "outdoor_humidity": 80, "outdoor_temp_c": 21, "indoor_location_id": 1, "outdoor_location_id": 2,
}

WEATHER = {
    "current": {"temperature_2m": 21, "relative_humidity_2m": 80, "dew_point_2m": 17, "wind_direction_10m": 135,
                "wind_speed_10m": 9, "uv_index": 2, "weather_code": 3},
    "hourly": {"time": [], "temperature_2m": []},
    "daily": {"time": [], "sunrise": [], "sunset": []},
}


@pytest.fixture
def canned(monkeypatch):
    monkeypatch.setattr(server, "get_open_meteo_data", lambda *a, **k: WEATHER)
    monkeypatch.setattr(server, "get_air_forecast", lambda *a, **k: {})
    monkeypatch.setattr(server, "get_smoke_data", lambda *a, **k: False)   # the real one returns a bool
    monkeypatch.setattr(server, "get_pollen_data", lambda *a, **k: [])
    monkeypatch.setattr(server, "get_pollen_days", lambda *a, **k: {"today": [], "tomorrow": []})
    monkeypatch.setattr(server, "history_points", lambda *a, **k: [])


@pytest.fixture
def client(canned):
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c
