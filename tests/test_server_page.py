"""The page gets the home from the server: GET / carries window.APP, built from the config (tests use Sacha's)."""
import json
import re
from pathlib import Path

import server
from config import public_view


def app_config(html):
    m = re.search(r"<script>window\.APP = (.*?);</script>", html)
    assert m, "no window.APP in the page"
    return json.loads(m.group(1))


def test_index_carries_app_config(client):
    html = client.get("/").get_data(as_text=True)
    assert "window.APP = " in html
    app = app_config(html)
    assert app["place"]["timezone"] == "America/New_York"
    assert app["place"]["name"] == "Greenpoint"
    assert app["road"]["name"] == "BQE" and app["road"]["toward"] == [80, 200]
    assert app["road"]["rush"] == [[7, 10, "morning"], [16, 20, "evening"]]
    assert [s["name"] for s in app["pollen_seasons"]] == ["Tree", "Grass", "Weed"]
    # before the page's own scripts, so they can read it
    assert html.index("window.APP = ") < html.index('<script src="/static/home.js')


def test_links_are_built_from_the_place(client):
    links = app_config(client.get("/").get_data(as_text=True))["links"]
    assert links["forecast"] == "https://forecast.weather.gov/MapClick.php?lat=40.73&lon=-73.95"
    assert links["pollen"] == "https://www.pollen.com/forecast/current/pollen/11222"
    assert links["traffic"] == "https://www.google.com/maps/@40.73,-73.95,14z/data=!5m1!1e1"
    assert "lat=40.73" in links["map_home"] and "long=-73.95" in links["map_home"] and "zoom=15" in links["map_home"]
    assert "zoom=12" in links["map_area"]


def test_road_distance_comes_from_the_route():
    # Sacha's home is about 1.1 km from the nearest point of static/bqe.json
    assert public_view(server.CFG)["road"]["distance_km"] == 1


def test_app_config_cannot_close_the_script(monkeypatch, client):
    for name in ("</script><b>x", "<!--<script>"):
        view = dict(server.APP_VIEW, place={**server.APP_VIEW["place"], "name": name})
        monkeypatch.setattr(server, "APP_VIEW", view)
        html = client.get("/").get_data(as_text=True)
        assert name not in html
        assert app_config(html)["place"]["name"] == name


def test_road_route_is_served(client):
    r = client.get("/api/road/route")
    assert r.status_code == 200
    points = r.get_json()
    assert len(points) > 10 and all(len(p) == 2 for p in points)


def test_no_road_no_route(monkeypatch, client):
    monkeypatch.setattr(server, "ROAD", None)
    assert client.get("/api/road/route").status_code == 404


def test_region_is_optional_text(tmp_path):
    from config import ConfigError, load_config
    import pytest
    example = (Path(__file__).resolve().parent.parent / "config.example.toml").read_text(encoding="utf-8")
    assert public_view(server.CFG)["place"]["region"] == "New York"   # Sacha's fixture
    assert public_view(load_config({"CONFIG_TOML": example}))["place"]["region"] is None
    with_region = example.replace('pollen_zip = "19103"', 'pollen_zip = "19103"\nregion = "Philadelphia"')
    assert public_view(load_config({"CONFIG_TOML": with_region}))["place"]["region"] == "Philadelphia"
    with pytest.raises(ConfigError, match="place.region"):
        load_config({"CONFIG_TOML": example.replace('pollen_zip = "19103"', 'pollen_zip = "19103"\nregion = 5')})


def test_a_real_home_has_no_demo_clock(client):
    """Sacha's page: no fixed clock, no long CDN cache, and its data is never cached as a demo's."""
    resp = client.get("/")
    assert "now" not in app_config(resp.get_data(as_text=True))
    assert "s-maxage" not in resp.headers.get("Cache-Control", "")
    assert server.MODE in ("live", "no_token")
    assert client.get("/api/context").headers["Cache-Control"] == "no-cache"
