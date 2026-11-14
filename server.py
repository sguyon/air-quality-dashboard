"""Home Air Quality: the Flask app, page, routes, config loading and startup."""

import base64
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, g, jsonify, request, send_file, make_response, redirect, render_template

import phrases
import token_setup
import summary as summary_rules
from config import (parse_dotenv, APPLIANCES, DEFAULT_LIMITS, ConfigError, env_key, load_config, public_view,
                    real_value, route_path, write_env_key)

# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for key, val in parse_dotenv(env_path.read_text()).items():
        os.environ.setdefault(key, val)

# Reloading server has always reset its cache, pools, and demo replacements.
# Reset the moved state too, before applying this startup's config and mode.
for module_name in ("sources", "air_read"):
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
import sources
import air_read

sources.runtime = air_read.runtime = sys.modules[__name__]

_CONTEXT_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="context")   # /api/context fan-out; separate from the pollen deadline pool
TOKEN = env_key("AIRGRADIENT_TOKEN")   # .env.example's placeholder counts as no token
# what the server prints when it stops for want of a config (a token but no home: it won't guess one)
NO_CONFIG_MESSAGE = "No config: copy config.example.toml to config.toml (or set CONFIG_TOML)"
APP_LOAD_ERROR = 4   # gunicorn's exit code for "the app can't load": the master stops instead of respawning forever
ENV_LABEL = {"dev": "DEV", "preview": "PREVIEW"}   # the tag on the page title and app name on dev and preview
# Addresses that only reach this machine or the home's own network (for the DEV tag): private IPv4 ranges, Tailscale's
# 100.64.0.0/10 range, and names that never resolve on the internet: bare machine names, Bonjour's .local, Tailscale's ts.net
LOCAL_HOST = re.compile(r"^(localhost|0\.0\.0\.0|127\.[\d.]+|10\.[\d.]+|192\.168\.[\d.]+|172\.(1[6-9]|2\d|3[01])\.[\d.]+"
                        r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.[\d.]+|[a-z0-9-]+|[a-z0-9.-]+\.(local|ts\.net))$")
# The weather card's words. Dew point (°C) under DEW_DRY_C dries sinuses (the Open-Meteo source note says so), under
# DEW_SEVERE_DRY_C badly. Visibility (m) under each line reads very low, reduced, moderate; above the last, clear.
DEW_SEVERE_DRY_C, DEW_DRY_C = 5, 10
VISIBILITY_VERY_LOW_M, VISIBILITY_REDUCED_M, VISIBILITY_MODERATE_M = 2000, 5000, 10000
# digits: the longest ?monitor= read as an id (AirGradient's are 5-6 digits today); a longer one is junk, and past
# about 4,300 digits Python's int() raises instead of reading it
MONITOR_ID_MAX_DIGITS = 12
APP_VERSION = "v0.1"   # the release shown on the page's build line (and the dev bar)
SAVED_NAMES_SHOWN = 4   # monitor names listed on the "connected" card; more become "and N more"


def _note_cache(info):
    try:
        g.cache_state, g.cache_age = info["state"], int(info["age"])
    except RuntimeError:
        pass


app = Flask(__name__)
token_state = token_setup.TokenState(TOKEN)


def use_config(cfg):
    """Point the server at a config (config.py): the home, its clock, the road and the limits. Runs once at import;
    tests run it again with another config. With None (no config) there is no home: Task 10 decides what happens then.
    The config rounds the home to ~1 km on purpose (public repo): weather, pollen, smoke and the 15 km radius don't
    need more. tzdata (requirements.txt) gives every host the timezone database."""
    global CFG, APP_VIEW, HOME_LAT, HOME_LON, HOME_TZ, ROAD, RUSH_WINDOWS, LIMITS, PM_FINE, PM_HIGH, CO2_OPEN, RH_LOW, RH_DAMP
    CFG = cfg
    APP_VIEW = public_view(cfg) if cfg else {}   # what the page gets as window.APP
    place = cfg.place if cfg else None
    HOME_LAT, HOME_LON = (place.lat, place.lon) if place else (None, None)
    HOME_TZ = ZoneInfo(place.timezone) if place else None
    ROAD = cfg.road if cfg else None
    RUSH_WINDOWS = list(ROAD.rush) if ROAD else []   # [start, end) hours, and the rush's name
    # the TOML reads every limit as a float; whole numbers stay whole so the page says "800", not "800.0"
    LIMITS = {k: int(v) if float(v).is_integer() else v for k, v in (cfg.limits if cfg else DEFAULT_LIMITS).items()}
    PM_FINE, PM_HIGH, CO2_OPEN = LIMITS["pm"], LIMITS["pm_high"], LIMITS["co2"]
    RH_LOW, RH_DAMP = LIMITS["rh_dry"], LIMITS["rh_damp"]
    summary_rules.LIMITS.update(LIMITS)
    summary_rules.APPLIANCES.clear()
    summary_rules.APPLIANCES.update(cfg.appliances if cfg else APPLIANCES)
    phrases.LIMIT_FACTS.update(phrases.PLACE_DEFAULTS)   # a config without a monitor doesn't keep the last one's name
    phrases.LIMIT_FACTS.update(co2_limit=LIMITS["co2"], rh_damp=LIMITS["rh_damp"], rh_dry=LIMITS["rh_dry"],
                               rh_stop=LIMITS["rh_stop"], pm_limit=LIMITS["pm"], pm_high=LIMITS["pm_high"],
                               **({k: v for k, v in (("indoor", place.indoor), ("outdoor", place.outdoor)) if v} if place else {}))


def startup_config(env=os.environ, root=None):
    """The config to run with: DEMO=1, CONFIG_TOML, CONFIG_FILE or config.toml (config.load_config). With none of them and no
    AIRGRADIENT_TOKEN either (a fresh copy), the demo's."""
    kw = {} if root is None else {"root": root}
    cfg = load_config(env, **kw)
    if cfg is None and not real_value(env.get("AIRGRADIENT_TOKEN")):
        cfg = load_config({"DEMO": "1"}, **kw)
    return cfg


def _stop(message):
    print(message, file=sys.stderr, flush=True)
    sys.exit(APP_LOAD_ERROR)


def boot_config(env=os.environ, root=None):
    """startup_config for the server's start: stops with a plain message instead of a traceback when the config is
    invalid (the ConfigError's text names where) or when there is a token but no config (it won't guess a home)."""
    try:
        cfg = startup_config(env, root)
    except ConfigError as e:
        _stop(str(e))
    if cfg is None:
        _stop(NO_CONFIG_MESSAGE)
    return cfg


def server_mode(cfg, token):
    """"demo" (made-up data, demo/), "live" (a config and a token) or "no_token" (a config, no token yet)."""
    if cfg is not None and cfg.demo:
        return "demo"
    return "live" if real_value(token) else "no_token"


use_config(boot_config())


MODE = server_mode(CFG, TOKEN)   # "demo", "live" or "no_token"; local token entry switches to live


def get_build_info():
    """The commit and the time of this page, in the home's timezone. The commit comes from the host's deploy
    variables when it sets them (Railway, Vercel), or from the Docker image's (GIT_COMMIT_SHA, the GIT_SHA build arg),
    else from git."""
    commit = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("VERCEL_GIT_COMMIT_SHA")
              or os.environ.get("GIT_COMMIT_SHA") or "").strip()[:7]
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).parent, stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
        except Exception:
            commit = "no-git"
    return f"{APP_VERSION} · {commit} · {sources.local_now().strftime('%H:%M:%S %Z')}"


def asset_version(rel_path):
    """Short content hash of a file in static/, so a changed file gets a new URL and no cache serves the old one."""
    path = Path(__file__).parent / rel_path.lstrip("/")
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()[:10]
    except OSError:
        return "0"


def version_assets(html):
    """Add ?v=<hash> to the page's CSS, JS, icons and manifest, so a changed file gets a new URL. Safari keeps
    home-screen icons per URL, so a new icon needs a new URL to show."""
    return re.sub(r'"(/static/[\w./-]+\.(?:css|js|png|svg)|/manifest\.json)"', lambda m: f'"{m.group(1)}?v={asset_version(m.group(1))}"', html)


@app.after_request
def api_headers(resp):
    """No browser HTTP caching of live data (the server cache does that); say how fresh the answer is."""
    if request.path.startswith("/api/"):
        # never kept: the token form, and the setup state the Connected card polls while setup restarts the app
        resp.headers["Cache-Control"] = "no-store" if request.path in ("/api/token", "/api/setup") else "no-cache"
        if getattr(g, "cache_state", None):
            resp.headers["X-Cache"] = g.cache_state
            resp.headers["X-Data-Age"] = str(g.cache_age)
    if (MODE == "demo" and request.method == "GET" and resp.status_code == 200 and (request.path == "/" or request.path.startswith("/api/"))
            and resp.headers.get("Cache-Control") != "no-store"):
        # a page that must not be kept (a fresh copy's setup card) stays so: a kept card would come back after setup
        if request_monitor() is not None or request.path == "/api/monitors":
            # a public monitor is live: a CDN keeps it as long as its data stays fresh in the cache (demo/public.py)
            resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
        else:
            # the demo's story is fixed: a CDN keeps each URL (each ?moment=) for a day, so a busy day barely runs the server
            resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400"
    if MODE == "demo" and monitor_missing():
        # a public monitor that can't be shown (unknown id, or the map didn't answer): no one keeps this answer
        resp.headers["Cache-Control"] = "no-store"
    # only the demo is for search engines; someone's home is not, nor a public monitor's page or the picker's list
    # (they carry the owners' names)
    if not (CFG is not None and CFG.demo) or "monitor" in request.args or request.path == "/api/monitors":
        resp.headers["X-Robots-Tag"] = "noindex"
    return resp


def icon_env():
    """"dev" or "preview" or None (a normal deployment). The reloading dev server (`flask run --reload`) at a local
    address is "dev"; otherwise a deployment names itself with APP_ENV, never by its address: a home that runs the app
    on its own network (a laptop, a small home server at 192.168.…) is a normal deployment."""
    host = (request.host or "").split(":")[0].lower()
    if LOCAL_HOST.match(host) and sources._dev_server():
        return "dev"
    env = os.environ.get("APP_ENV", "").strip().lower()
    return env if env in ENV_LABEL else None


def tag_env(html):
    """DEV / PREVIEW icons, tab title and home-screen name, so the environments can't be mixed up."""
    env = icon_env()
    if not env:
        return html
    html = re.sub(r'(<link rel="(?:icon|apple-touch-icon)"[^>]*href=")/static/icons/', rf'\1/static/icons/{env}/', html)
    html = html.replace("<title>Home Air Quality</title>", f"<title>{ENV_LABEL[env]} · Home Air Quality</title>", 1)
    html = html.replace('<meta name="apple-mobile-web-app-title" content="Air Quality">', f'<meta name="apple-mobile-web-app-title" content="AQ {ENV_LABEL[env]}">', 1)
    return html


def inline_touch_icon(html):
    """Put the 180 px home-screen icon in the page itself. Safari's Add to Home Screen sheet loads icons on its own
    and can fail on a network URL, which leaves a letter tile."""
    m = re.search(r'(<link rel="apple-touch-icon"[^>]*href=")(/static/icons/[\w./-]+\.png)(?:\?v=\w+)?"', html)
    if not m:
        return html
    try:
        data = base64.b64encode((Path(__file__).parent / m.group(2).lstrip("/")).read_bytes()).decode()
    except OSError:
        return html
    return html[:m.start()] + f'{m.group(1)}data:image/png;base64,{data}"' + html[m.end():]


@app.route("/")
def index():
    if "setup" in request.args:
        response = redirect("/", code=303)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        if (setup_mode() and token_setup.local_entry(request, env_path)
                and not token_setup.has_token(env_path, TOKEN)
                and token_state.authorized(request.args["setup"])):
            response.set_cookie(token_setup.COOKIE_NAME, token_state.code, httponly=True,
                                samesite="Strict", secure=request.is_secure)
        return response
    return render_page()


def setup_mode():
    # A fresh copy opens the demo; its startup link must collect the token before setup can discover monitors.
    return MODE == "no_token" or (MODE == "demo" and CFG.demo and os.environ.get("DEMO") != "1")


def print_setup_link(port):
    if not real_value(TOKEN) and token_state.code:
        print(f"Paste your AirGradient token here: http://localhost:{port}/?setup={token_state.code}", flush=True)


TOKEN_FORMAT_ERROR = ("This doesn't look like an AirGradient token. Press the copy button next to API Access "
                      "(not \"Renew API token\"), then paste it here.")
TOKEN_REFUSED_ERROR = ("AirGradient refused this token. Check that API Access is turned on for the place that shows your monitor, "
                       "then copy the token again.")
FORM_EXPIRED_ERROR = "This form had expired, so nothing was sent. Paste the token again."
LINK_EXPIRED_ERROR = ("This page is from before the app restarted, so it can't connect. Ask your agent for the new setup link, "
                      "or restart the app to get one.")


def render_page(error=None, status=200, card=False):
    """The missing-token card works without JavaScript; no credential is ever embedded in the page.
    card: show the token card even without a valid setup cookie (an expired link explains itself instead of showing the demo)."""
    html_path = Path(__file__).parent / "index.html"
    html = inline_touch_icon(tag_env(version_assets(html_path.read_text())))
    browser = None
    # A fresh copy (the demo, no home yet) shows only the card: the token box with its link, then "saved" until setup restarts it.
    saved = setup_mode() and MODE == "demo" and token_state.saved
    show_setup = MODE == "no_token" or saved or (setup_mode() and (card or token_state.authorized(request.cookies.get(token_setup.COOKIE_NAME, ""))))
    html = inject_app(html, setup_page=show_setup)
    if show_setup:
        entry = (token_setup.allowed(request, env_path, TOKEN, "no_token")
                 and token_state.authorized(request.cookies.get(token_setup.COOKIE_NAME, "")))
        value, browser = token_state.issue(request) if entry else (None, None)
        card = render_template("token_card.html", entry=entry and not saved, saved=saved,
                               found=token_state.saved["monitors"] if saved else [], shown=SAVED_NAMES_SHOWN, nonce=value, error=error,
                               instructions=token_setup.instructions(request), max_length=token_setup.TOKEN_MAX_LENGTH)
        html = html.replace('id="no-token" hidden', 'id="no-token"')
        html = html.replace("<!-- token-setup -->", card)

    # Inject build info into a data attribute on the body
    build_info = get_build_info()
    html = html.replace(
        '<body>',
        f'<body data-build="{build_info}">'
    )

    if show_setup:
        # fresh-copy: no home yet, so the header has no home menu to show
        html = html.replace('<body data-build=', '<body class="no-token%s" data-build=' % (" fresh-copy" if MODE == "demo" else ""), 1)
    response = make_response(html, status)
    response.headers["Referrer-Policy"] = "same-origin"
    if show_setup:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        response.headers["X-Frame-Options"] = "DENY"
    if browser:
        response.set_cookie(token_setup.COOKIE_NAME, browser, httponly=True, samesite="Strict", secure=request.is_secure)
    return response


@app.route("/api/token", methods=["POST"])
def save_token():
    """First-run local setup only. Validate unlocked, then serialize the final check and save."""
    global TOKEN, MODE
    with token_state.lock:
        if (MODE == "demo" and not setup_mode()) or not token_setup.local_entry(request, env_path) or not token_setup.same_origin(request):
            return jsonify(error="Token entry is only available on this computer's local page."), 403
        if token_setup.has_token(env_path, TOKEN):
            return redirect("/", code=303)   # sent twice, or from an old tab: the page shows where things stand
        if not setup_mode():
            return jsonify(error="Token entry is only available on this computer's local page."), 403
        request.max_content_length = token_setup.TOKEN_POST_MAX_BYTES
        if not token_state.consume(request, request.form.get("setup_nonce", "")):
            # A page, never raw JSON: a fresh form when this browser still holds the setup link, else what to do.
            if token_state.authorized(request.cookies.get(token_setup.COOKIE_NAME, "")):
                return render_page(FORM_EXPIRED_ERROR, 403)
            return render_page(LINK_EXPIRED_ERROR, 403, card=True)
        retry = token_state.retry_after()
        if retry:
            response = render_page("Too many attempts. Wait five minutes, then try again.", 429)
            response.headers["Retry-After"] = str(retry)
            return response
        candidate = request.form.get("token", "").strip()
        if (not candidate or len(candidate) > token_setup.TOKEN_MAX_LENGTH
                or not token_setup.TOKEN_CHARACTERS.fullmatch(candidate) or not real_value(candidate)):
            token_state.failed()
            return render_page(TOKEN_FORMAT_ERROR, 400)
    try:
        accepted = sources.validate_token(candidate)
    except (sources.requests.RequestException, ValueError):
        with token_state.lock:
            token_state.failed()
            return render_page("AirGradient didn't answer. Try again shortly.", 502)

    with token_state.lock:
        if accepted is None:
            token_state.failed()
            return render_page(TOKEN_REFUSED_ERROR, 400)
        # Recheck for a token written while the validation call was waiting.
        if token_setup.has_token(env_path, TOKEN):
            return redirect("/", code=303)   # another tab or the terminal won: keep theirs, show the page
        try:
            write_env_key(env_path, "AIRGRADIENT_TOKEN", candidate)
        except (OSError, UnicodeError, ValueError):
            return render_page("Couldn't save the token. Check that the app's folder is writable.", 500)
        os.environ["AIRGRADIENT_TOKEN"] = candidate
        TOKEN, MODE = candidate, server_mode(CFG, candidate)
        token_state.code = None
        token_state.saved = {"monitors": accepted}   # the account's monitors and their kinds, for the "connected" card
        token_state.nonces.clear()
        token_state.failures.clear()
        response = redirect("/", code=303)
        response.headers["Cache-Control"] = "no-store"
        response.delete_cookie(token_setup.COOKIE_NAME)
        return response


def page_view():
    """window.APP's config part: the home's (config.public_view). demo/data.py gives a public monitor's instead."""
    return APP_VIEW


def page_clock():
    """The demo's fixed clock for the page (window.APP.now: the moment's time, its key, the moments to switch to),
    or None: a real home runs on the real clock. demo/data.py replaces it."""
    return None


def inject_app(html, setup_page=False):
    """The home's config for the page's scripts (config.public_view), as window.APP before the first of them.
    Every "<" is escaped (\\u003c, still the same JSON) so no config value can close the script or open a comment."""
    now = None if setup_page else page_clock()   # the token card never shows the demo's moments
    data = json.dumps({**page_view(), "env": icon_env(), **({"now": now} if now else {}), **({"state": "no_token"} if MODE == "no_token" or setup_page else {})}, ensure_ascii=False).replace("<", "\\u003c")
    return html.replace("<script src=", f"<script>window.APP = {data};</script>\n<script src=", 1)


@app.route("/api/setup")
def setup_state():
    """Whether the app still waits for setup. The Connected card asks every few seconds and opens the home once setup has
    restarted the app with it, so nobody has to reload the tab."""
    return jsonify({"setup": setup_mode()})


@app.route("/api/road/route")
def road_route():
    """The road's route ([lon, lat] points) for the map. 404 without a road."""
    if not ROAD:
        return jsonify({"error": "no road"}), 404
    try:
        return jsonify(json.loads(route_path(ROAD.route).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return jsonify({"error": "road route unreadable"}), 404


@app.route("/manifest.json")
def manifest():
    path = Path(__file__).parent / "manifest.json"
    env = icon_env()
    data = json.loads(path.read_text())
    if env:   # the installed app gets the DEV / PREVIEW icons and name too
        data["name"] = f'{data.get("name", "Home Air Quality")} ({ENV_LABEL[env]})'
        data["short_name"] = f"AQ {ENV_LABEL[env]}"
    for ic in data.get("icons", []):
        src = str(ic.get("src", ""))
        if src.startswith("/static/icons/"):
            ic["src"] = (src.replace("/static/icons/", f"/static/icons/{env}/", 1) if env else src) + f"?v={asset_version(src)}"
    resp = jsonify(data)
    resp.headers["Content-Type"] = "application/manifest+json"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
@app.route("/apple-touch-icon-180x180.png")
@app.route("/apple-touch-icon-180x180-precomposed.png")
@app.route("/favicon.ico")
def root_icon():
    """The icons iOS and browsers ask for at the root, whatever the page declares; with the DEV / PREVIEW set where it applies."""
    env = icon_env()
    name = "favicon-32.png" if request.path == "/favicon.ico" else "apple-touch-icon.png"
    path = Path(__file__).parent / "static" / "icons" / (f"{env}/" if env else "") / name
    resp = send_file(path, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/sw.js")
def service_worker():
    return send_file(Path(__file__).parent / "sw.js", mimetype="application/javascript")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "airgradient_token_set": bool(TOKEN),
    })


@app.route("/api/current")
def current():
    if MODE == "no_token":   # a config but no token yet: the page says so; an expired token is a 502 below
        return jsonify({"state": "no_token"})
    try:
        value, info = sources.cached("ag:current", lambda: sources.api_get("/locations/measures/current"), ttl=30, keep=900, force=sources._force())
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    _note_cache(info)
    value = sources.place_rows(value)
    src = sources.outdoor_source(with_history=False) if isinstance(value, list) else None
    if src is not None:   # an indoor-only home: its outdoor source stands as the outdoor monitor (a copy: the cache keeps its list)
        value = value + [sources.source_monitor(src)]
    return jsonify(value)


@app.route("/api/history/<int:location_id>")
def history(location_id):
    chart_keep = sources.HIST_KEEP   # PM2.5, CO2 and humidity: the three History charts
    try:
        frm, to = sources._iso(request.args["from"]), sources._iso(request.args["to"])
        hours = round((to - frm).total_seconds() / 3600)
        standard = hours in sources.HIST_TTL and abs((datetime.now(timezone.utc) - to).total_seconds()) < 120
    except (KeyError, ValueError):
        standard = False
    of = sources.outdoor_from()
    if isinstance(of, int) and location_id == of:   # an indoor-only home's public monitor: its history from the map
        utc = lambda t: t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        try:
            frm = utc(sources._iso(request.args["from"])) if request.args.get("from") else datetime.now(timezone.utc) - timedelta(days=1)
            to = utc(sources._iso(request.args["to"])) if request.args.get("to") else datetime.now(timezone.utc)
        except ValueError:
            return jsonify({"error": "from and to must be ISO times"}), 400
        rows = sources.source_history_rows(location_id, frm, to)
        return jsonify([{k: r.get(k) for k in chart_keep if r.get(k) is not None} for r in rows])
    try:
        if standard:   # the page's ranges ending now: served from the cache, cut to the asked start
            rows, info = sources.history_rows(location_id, hours, force=sources._force())
            _note_cache(info)
            cut = frm.strftime("%Y-%m-%dT%H:%M:%S")
            rows = [r for r in rows if str(r.get("timestamp", ""))[:19] >= cut]
        else:
            params = {k: request.args[k] for k in ("from", "to") if request.args.get(k)}
            rows = sources.api_get(f"/locations/{location_id}/measures/past", params)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify([{k: r.get(k) for k in chart_keep if r.get(k) is not None} for r in rows or [] if isinstance(r, dict)])


@app.route("/api/neighborhood")
def neighborhood():
    if not sources.source_on("nearby"):
        return jsonify([])
    try:
        world, info = sources.cached("ag:world", sources._fetch_world, force=sources._force(), **sources.WORLD_CACHE)
        value = sources._fetch_nearby(world)
    except Exception as e:
        return jsonify({"error": sources._redact(f"Neighborhood data unavailable: {e}")}), 502
    _note_cache(info)
    return jsonify(value)


@app.route("/api/context")
def context():
    """Return external data sources (weather, pollen, the road, smoke) as structured JSON."""
    # Fetch independents in parallel; pollen has its own hard deadline inside get_pollen_data.
    weather_fut = _CONTEXT_POOL.submit(sources.get_open_meteo_data)
    smoke_fut = _CONTEXT_POOL.submit(sources.smoke_status) if sources.source_on("smoke") else None
    pollen_fut = _CONTEXT_POOL.submit(sources.get_pollen_days) if sources.pollen_live() else None
    air_fut = _CONTEXT_POOL.submit(sources.get_air_forecast)

    try:
        weather = weather_fut.result(timeout=12)
    except Exception:
        weather = {"current": {}}
    smoke = sources.no_smoke()
    pollen_days = {"today": [], "tomorrow": []}
    if smoke_fut:
        try:
            smoke = smoke_fut.result(timeout=12)
        except Exception:
            pass
    if pollen_fut:
        try:
            pollen_days = pollen_fut.result(timeout=6)
        except Exception:
            pass
    pollen, pollen_tomorrow = pollen_days["today"], pollen_days["tomorrow"]
    try:
        air = air_fut.result(timeout=12)
    except Exception:
        air = {}

    cur = weather.get("current", {})
    wind_speed = cur.get("wind_speed_10m")
    wind_direction = cur.get("wind_direction_10m")
    visibility = cur.get("visibility")
    uv_index = cur.get("uv_index")
    dew_point = cur.get("dew_point_2m")
    temperature = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m")

    wind_dir = air_read.get_wind_cardinal(wind_direction)

    # Dew point sinus risk
    if dew_point is not None and dew_point < DEW_SEVERE_DRY_C:
        dew_point_risk = "Severe dryness"
    elif dew_point is not None and dew_point < DEW_DRY_C:
        dew_point_risk = "Moderate dryness"
    else:
        dew_point_risk = "Comfortable"

    # Visibility interpretation
    if visibility is not None:
        if visibility < VISIBILITY_VERY_LOW_M:
            visibility_status = "Very low — high particulate"
        elif visibility < VISIBILITY_REDUCED_M:
            visibility_status = "Reduced"
        elif visibility < VISIBILITY_MODERATE_M:
            visibility_status = "Moderate"
        else:
            visibility_status = "Clear"
    else:
        visibility_status = "Unknown"

    forecast = air_read.hourly_forecast(weather, air)

    # the road's traffic, and whether the wind blows its exhaust here
    current_hour = sources.local_now().hour
    road = air_read.road_traffic(current_hour, wind_direction)
    road_cfg = air_read.active_road()
    if road_cfg:   # "bqe" is the shape the page reads today; "road" carries the flag (the page moves to it later)
        extra = {"bqe": {"traffic": road["traffic"], "wind_impact": road["wind_impact"],
                         "pollution_pressure": road["pollution_pressure"], "current_hour": current_hour},
                 "road": {"name": road_cfg.name, "toward": road["toward"]}}
    else:
        extra = {}

    # per source: ok, off (config), not_set_up (key missing) or error (on, but it didn't answer)
    pollen_s = sources.pollen_state()
    status = {
        "pollen": ("ok" if pollen else "error") if pollen_s == "ok" else pollen_s,
        "smoke": ("ok" if smoke.get("checked") else "error") if sources.source_on("smoke") else "off",
        "road": "ok" if road_cfg else "off",
        "nearby": "ok" if sources.source_on("nearby") else "off",
    }

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
            "humidity": humidity,
            "cloud_cover": cur.get("cloud_cover"),
            "weather_code": cur.get("weather_code")
        },
        **extra,
        "smoke": smoke,
        "pollen": pollen,
        "pollen_tomorrow": pollen_tomorrow,
        "forecast": forecast,
        "status": status,
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """The page's air summary as one JSON object. Only "format": "read" is served."""
    data = request.get_json(silent=True) or {}
    if data.get("format") == "read":
        return jsonify(air_read.build_air_read(data))
    return jsonify({"error": 'POST {"format": "read", ...}'}), 400


def request_moment():
    """The demo moment this request asked for (?sample=1|2|3 or ?moment=<key>), or the default one."""
    from demo.moments import moment_for
    try:
        return moment_for(request.args.get("moment"), request.args.get("sample"))
    except RuntimeError:   # outside a request
        return moment_for(None)


def monitor_missing():
    """True when this request asked for a public monitor that can't be shown. Demo only: demo/data.py answers it."""
    return False


def request_monitor():
    """The public monitor this request asked for (?monitor=, a positive whole number), or None."""
    try:
        raw = request.args.get("monitor", "")
    except RuntimeError:   # outside a request
        return None
    ok = raw.isascii() and raw.isdigit() and len(raw) <= MONITOR_ID_MAX_DIGITS
    return int(raw) if ok and int(raw) > 0 else None


@app.route("/api/monitors")
def monitors():
    """The demo's monitor picker: the public outdoor monitors nearest ?lat=&lon= (rounded again to 2 decimals, about
    1 km), or nearest New York without them. Demo only."""
    if MODE != "demo":
        return jsonify({"error": "not found"}), 404
    import publicmap
    from demo import public
    lat, lon = request.args.get("lat"), request.args.get("lon")
    if lat is None and lon is None:
        near, lat, lon = public.DEFAULT_LIST
    else:
        try:
            lat, lon = round(float(lat), 2), round(float(lon), 2)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "lat and lon must be a place's coordinates"}), 400
        near = "you"
    try:
        world = demo_data.world_list()
    except demo_data.WORLD_ERRORS:
        return jsonify({"error": public.WORLD_DOWN}), 502
    return jsonify({"near": near, "monitors": publicmap.nearest(world, lat, lon)})


if MODE == "demo":   # every outside source becomes made-up data, generated per request (demo/data.py)
    from demo import data as demo_data
    demo_data.install(sys.modules[__name__], request_moment)

# Compatibility for tools/replay.py and the unchanged golden test.
from sources import api_get, local_now
from air_read import road_traffic, rush_windows


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5555))
    host = os.environ.get("HOST", "127.0.0.1")   # HOST=0.0.0.0 to open it from a phone on the same network
    print(f"Home Air Quality → http://localhost:{port}")
    print_setup_link(port)
    app.run(host=host, port=port, debug=False)
