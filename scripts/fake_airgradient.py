"""AirGradient stand-in for screenshots and tests only; all readings are made up.

    python3 scripts/fake_airgradient.py <port> [--empty]

Accepts only TEST_TOKEN. Serves current and past readings from setup_monitors.json;
--empty represents a connected account with no monitors. Binds to loopback only.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TEST_TOKEN = "setup-screenshot-test-token"  # Public, made-up credential; never an AirGradient key.
MONITORS = Path(__file__).with_name("setup_monitors.json")
STEP = timedelta(minutes=5)  # AirGradient's past readings are spaced five minutes apart.
DEFAULT_RANGE = timedelta(hours=24)  # History range when from/to are omitted.
API_PATH = "/public/api/v1/locations"


def reading(monitor, at):
    return {**monitor, "timestamp": at.strftime("%Y-%m-%dT%H:%M:%S.000Z")}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if query.get("token") != [TEST_TOKEN]:
            return self.send(401, {"message": "Unauthorized"})
        now = datetime.now(timezone.utc).replace(microsecond=0)
        if url.path == f"{API_PATH}/measures/current":
            return self.send(200, [reading(m, now) for m in self.server.monitors])
        parts = url.path.split("/")
        if url.path.startswith(API_PATH + "/") and len(parts) == 8 and parts[-2:] == ["measures", "past"]:
            monitor = next((m for m in self.server.monitors if str(m["locationId"]) == parts[-3]), None)
            if monitor is None:
                return self.send(404, {"message": "Location not found"})
            end = datetime.fromisoformat(query["to"][0]) if query.get("to") else now
            at = datetime.fromisoformat(query["from"][0]) if query.get("from") else end - DEFAULT_RANGE
            rows = []
            while at <= min(end, now):
                rows.append(reading(monitor, at))
                at += STEP
            return self.send(200, rows)
        return self.send(404, {"message": "Not found"})

    def send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def make_server(port, *, empty=False):
    server = HTTPServer(("127.0.0.1", port), Handler)
    server.monitors = [] if empty else json.loads(MONITORS.read_text(encoding="utf-8"))
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int)
    parser.add_argument("--empty", action="store_true")
    args = parser.parse_args()
    with make_server(args.port, empty=args.empty) as server:
        server.serve_forever()
