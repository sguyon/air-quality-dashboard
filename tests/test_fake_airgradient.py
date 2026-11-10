"""Exercise real HTTP requests through the stand-in, without binding a port."""
from functools import partial
from http.server import HTTPServer
from io import BytesIO
import json

import pytest

from scripts import fake_airgradient as fake


@pytest.fixture
def get(monkeypatch):
    monkeypatch.setattr(fake, "HTTPServer", partial(HTTPServer, bind_and_activate=False))

    def request(path="measures/current", token=fake.TEST_TOKEN, empty=False):
        class Connection:
            response = b""

            def makefile(self, *args):
                return BytesIO(f"GET {fake.API_PATH}/{path}?token={token} HTTP/1.0\r\n\r\n".encode())

            def sendall(self, data):
                self.response += data

        connection = Connection()
        with fake.make_server(0, empty=empty) as server:
            fake.Handler(connection, ("127.0.0.1", 0), server)
        headers, body = connection.response.split(b"\r\n\r\n", 1)
        return int(headers.split()[1]), json.loads(body)

    return request


def test_right_token_returns_monitors_and_past_rows(get):
    status, rows = get()
    assert status == 200
    assert [(r["locationName"], r["locationType"]) for r in rows] == [
        ("Bedroom", "indoor"), ("Balcony", "outdoor"),
    ]
    status, past = get(f"{rows[0]['locationId']}/measures/past")
    assert status == 200
    assert past and past[0]["locationName"] == "Bedroom" and "timestamp" in past[0]


@pytest.mark.parametrize("token", ["", "wrong-token"])
def test_wrong_or_missing_token_is_unauthorized(get, token):
    status, _ = get(token=token)
    assert status == 401


def test_empty_account_has_no_monitors(get):
    assert get(empty=True) == (200, [])
