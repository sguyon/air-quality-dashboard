"""AirGradient errors reach the page as text: the token (it rides in the request URL) must never be in it."""
import pytest
import requests

import server
import sources


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setattr(server, "TOKEN", "SECRET123")
    monkeypatch.setattr(server, "MODE", "live")
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def _get(c, url="/api/current"):
    sources._cache.clear() if hasattr(sources, "_cache") else None
    return c.get(url + ("&" if "?" in url else "?") + "force=1")


def test_unreachable_has_no_url_or_token(secret, monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("HTTPSConnectionPool(host='api.airgradient.com'): Max retries exceeded with url: /public/api/v1/locations/measures/current?token=SECRET123")
    monkeypatch.setattr(sources.requests, "get", boom)
    for url in ("/api/current", "/api/history/1?from=2026-01-01T00:00:00Z&to=2026-01-01T01:00:00Z"):
        r = _get(secret, url)
        assert r.status_code == 502 and "SECRET123" not in r.get_data(as_text=True)
    assert "unreachable (ConnectionError)" in _get(secret).get_json()["error"]


def test_http_error_body_is_redacted(secret, monkeypatch):
    class Resp:
        status_code = 401
        text = "bad token SECRET123"
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("401", response=self)
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Resp())
    r = _get(secret)
    assert r.status_code == 502 and "SECRET123" not in r.get_data(as_text=True) and "***" in r.get_data(as_text=True)
