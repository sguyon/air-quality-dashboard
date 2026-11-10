"""Local first-run entry: request guards and short-lived, browser-bound form values."""
import os
import re
import secrets
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from config import env_key, parse_dotenv, real_value

# Hosting environment markers: any one (even empty) means keys belong in the host's settings.
HOSTED_MARKERS = ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "VERCEL", "RENDER", "FLY_APP_NAME", "K_SERVICE", "DYNO",
                  "KUBERNETES_SERVICE_HOST", "KOYEB_APP_NAME", "WEBSITE_INSTANCE_ID")
DOCKER_MARKER = Path("/.dockerenv")  # Docker creates this file inside its containers.
PODMAN_MARKER = Path("/run/.containerenv")  # Podman creates this file inside its containers.
# Proxy headers disqualify local entry; X-Forwarded-* is also rejected, including unknown suffixes.
PROXY_HEADERS = ("forwarded", "via", "x-real-ip", "x-original-host", "x-original-url", "x-forwarded",
                 "cf-connecting-ip", "true-client-ip", "x-client-ip", "fastly-client-ip")
LOCAL_ADDRESSES = ("127.0.0.1", "::1")  # Only exact loopback addresses, never a network or forwarded address.
LOCAL_HOST = re.compile(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]+)?", re.I)
TOKEN_CHARACTERS = re.compile(r"[A-Za-z0-9._~+=/-]+")  # Plain API credentials; excludes whitespace and dotenv quotes.
TOKEN_MAX_LENGTH = 4096  # characters: enough for an API credential, while bounding malformed input.
TOKEN_POST_MAX_BYTES = 8192  # bytes: bounds the token plus form encoding and the one-use value.
FAILED_ATTEMPT_LIMIT = 5  # failures per local server per window; IPv4 and IPv6 share the same budget.
FAILED_ATTEMPT_WINDOW = 300  # seconds: retry after five minutes rather than locking out a new setup.
NONCE_LIFETIME = 600  # seconds: a form expires after ten minutes; reload makes another.
NONCE_LIMIT = 32  # outstanding forms: bounds memory even if pages are repeatedly opened.
NONCE_BYTES = 32  # random bytes for form values and browser cookies (256 bits).
COOKIE_NAME = "aq_token_setup"  # HttpOnly session cookie; never contains the AirGradient token.


def local_request(req):
    """Use the socket peer and raw Host, never trust a proxy's account of either."""
    return (req.remote_addr in LOCAL_ADDRESSES
            and LOCAL_HOST.fullmatch(req.headers.get("Host", "")) is not None
            and not any(name.lower() in PROXY_HEADERS or name.lower().startswith("x-forwarded-")
                        for name in req.headers.keys()))


def hosted(env=os.environ):
    return any(marker in env for marker in HOSTED_MARKERS)


def has_token(path, token):
    """Check both sources again, including a file changed since startup; never return its value."""
    if real_value(token) or env_key("AIRGRADIENT_TOKEN"):
        return True
    try:
        return bool(env_key("AIRGRADIENT_TOKEN", parse_dotenv(path.read_text(encoding="utf-8"))))
    except FileNotFoundError:
        return False
    except (OSError, UnicodeError):
        return True  # an unreadable file cannot safely be treated as empty


def writable_folder(path):
    """Atomic replacement needs write and search access to the parent. Browser setup won't follow symlinks."""
    try:
        return (not path.is_symlink() and bool(path.parent.stat().st_mode & 0o222)
                and os.access(path.parent, os.W_OK | os.X_OK))
    except OSError:
        return False


def local_entry(req, path):
    """Check the local environment before revealing whether a token already exists."""
    return (local_request(req) and not hosted() and not DOCKER_MARKER.exists()
            and not PODMAN_MARKER.exists() and writable_folder(path))


def allowed(req, path, token, mode):
    return mode == "no_token" and local_entry(req, path) and not has_token(path, token)


def instructions(req):
    """Hosting instructions take precedence over the address used to reach a deployed copy."""
    if "RAILWAY_ENVIRONMENT" in os.environ or "RAILWAY_PROJECT_ID" in os.environ:
        return "railway"
    if DOCKER_MARKER.exists() or PODMAN_MARKER.exists():
        return "docker"
    if not hosted() and not local_request(req):
        return "network"
    return "file"


def origin(req):
    return f"{req.scheme}://{req.host.lower()}"


def same_origin(req):
    """Require Origin or Referer. If both are present, both must match, including scheme and port."""
    expected = origin(req)
    values = []
    for name in ("Origin", "Referer"):
        if name not in req.headers:
            continue
        value = req.headers[name]
        try:
            parsed = urlsplit(value)
            if parsed.username is not None or parsed.password is not None or parsed.fragment:
                return False
            if name == "Origin" and (parsed.path or parsed.query):
                return False
            values.append(f"{parsed.scheme}://{parsed.netloc.lower()}" == expected)
        except ValueError:
            return False
    return bool(values) and all(values)


class TokenState:
    """Single local process: serialize saves, consume forms once and share the failed-attempt budget."""

    def __init__(self):
        self.lock = threading.RLock()
        self.nonces = {}
        self.failures = deque()

    def issue(self, req):
        with self.lock:
            now = time.monotonic()
            self.nonces = {key: value for key, value in self.nonces.items() if value[2] > now}
            while len(self.nonces) >= NONCE_LIMIT:
                self.nonces.pop(next(iter(self.nonces)))
            browser = req.cookies.get(COOKIE_NAME)
            if not browser or not any(entry[0] == browser for entry in self.nonces.values()):
                browser = secrets.token_urlsafe(NONCE_BYTES)
            value = secrets.token_urlsafe(NONCE_BYTES)
            self.nonces[value] = (browser, origin(req), now + NONCE_LIFETIME)
            return value, browser

    def consume(self, req, value):
        with self.lock:
            entry = self.nonces.get(value)
            if entry is None:
                return False
            browser, source, expiry = entry
            if (expiry <= time.monotonic() or source != origin(req)
                    or not secrets.compare_digest(browser.encode(), req.cookies.get(COOKIE_NAME, "").encode())):
                return False
            del self.nonces[value]
            return True

    def retry_after(self):
        now = time.monotonic()
        while self.failures and self.failures[0] <= now - FAILED_ATTEMPT_WINDOW:
            self.failures.popleft()
        if len(self.failures) >= FAILED_ATTEMPT_LIMIT:
            return max(1, int(self.failures[0] + FAILED_ATTEMPT_WINDOW - now) + 1)
        return 0

    def failed(self):
        self.failures.append(time.monotonic())
