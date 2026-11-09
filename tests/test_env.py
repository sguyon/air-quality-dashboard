"""Which deployment this is comes from APP_ENV, never from an address."""
import dataclasses
import re

import server


def page(client, host="localhost"):
    return client.get("/", headers={"Host": host})


def app_env(html):
    m = re.search(r'"env": (null|"\w+")', html)
    return m.group(1) if m else None


def test_unknown_host_is_production(client, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    html = page(client, "someone.up.railway.app").get_data(as_text=True)
    assert "PREVIEW" not in html and "DEV ·" not in html
    assert app_env(html) == "null"


def test_dev_looking_address_is_not_special(client, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    html = page(client, "someone-dev.up.railway.app").get_data(as_text=True)
    assert "PREVIEW" not in html


def test_app_env_preview(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    html = page(client, "someone.up.railway.app").get_data(as_text=True)
    assert "<title>PREVIEW · Home Air Quality</title>" in html
    assert app_env(html) == '"preview"'


def test_app_env_dev_and_junk(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    assert app_env(page(client, "x.example.com").get_data(as_text=True)) == '"dev"'
    monkeypatch.setenv("APP_ENV", "staging")
    assert app_env(page(client, "x.example.com").get_data(as_text=True)) == "null"


def test_local_address_is_dev(client, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    for host in ("localhost:5555", "127.0.0.1", "192.168.1.5", "10.0.0.2", "172.20.1.1"):
        assert app_env(page(client, host).get_data(as_text=True)) == '"dev"', host


def test_noindex_unless_demo(client, monkeypatch):
    r = client.get("/health")
    assert r.headers["X-Robots-Tag"] == "noindex"
    assert client.get("/").headers["X-Robots-Tag"] == "noindex"
    monkeypatch.setattr(server, "CFG", dataclasses.replace(server.CFG, demo=True))
    assert "X-Robots-Tag" not in client.get("/health").headers


def test_build_info_from_env(monkeypatch):
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    assert server.get_build_info().startswith("v2 · abcdef1 · ")
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA")
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "1234567890abcdef")
    assert server.get_build_info().startswith("v2 · 1234567 · ")
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA")
    monkeypatch.setenv("GIT_COMMIT_SHA", "fedcba0987654321")   # the Docker image's, from the GIT_SHA build arg
    assert server.get_build_info().startswith("v2 · fedcba0 · ")


def test_build_time_label_follows_the_home_timezone(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    assert re.search(r"\d\d:\d\d:\d\d [A-Z]{2,4}$", server.get_build_info())
