from pathlib import Path
"""Local first-run token entry; all credentials and files here are made up."""
import logging
from html import unescape
import os
import re
import stat
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

import server
import sources

TOKEN = "made-up-airgradient-token"
BASE = "http://localhost:5555"


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setattr(sources, "runtime", server)
    monkeypatch.setattr(server, "TOKEN", "")
    monkeypatch.setattr(server, "MODE", "no_token")
    monkeypatch.setattr(server, "env_path", tmp_path / ".env")
    monkeypatch.setenv("AIRGRADIENT_TOKEN", "")
    # Explicit literals keep the test independent of the production allow/deny lists.
    for marker in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "VERCEL", "RENDER", "FLY_APP_NAME", "K_SERVICE", "DYNO",
                   "KUBERNETES_SERVICE_HOST", "KOYEB_APP_NAME", "WEBSITE_INSTANCE_ID"):
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.setattr(server.token_setup, "DOCKER_MARKER", tmp_path / "no-container")
    monkeypatch.setattr(server.token_setup, "PODMAN_MARKER", tmp_path / "no-podman")
    monkeypatch.setattr(server, "token_state", server.token_setup.TokenState())
    server.app.config["TESTING"] = True
    def get(url, **kwargs):
        assert url == sources.API_BASE + "/locations/measures/current"
        assert kwargs["params"] == {"token": TOKEN}
        return Reply()
    monkeypatch.setattr(sources.requests, "get", get)
    with server.app.test_client() as client:
        yield client
    sources._cache.clear()


class Reply:
    status_code = 200
    def raise_for_status(self):
        pass
    def json(self):
        return [{"locationId": 1, "model": "I-9PSL", "pm02": 3}]


def page(client, **kwargs):
    # Redeem the startup link as a browser would; ordinary page requests never grant entry.
    if server.token_state.code and not client.get_cookie(server.token_setup.COOKIE_NAME):
        client.get("/?setup=" + server.token_state.code, base_url=BASE)
    return client.get("/", base_url=BASE, **kwargs)


def nonce(response):
    match = re.search(r'name="setup_nonce" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "the local page must include a one-use form value"
    return match[1]


def submit(client, value=None, **kwargs):
    value = value or nonce(page(client))
    return client.post("/api/token", base_url=BASE, data={"setup_nonce": value, "token": TOKEN},
                       headers=kwargs.pop("headers", {"Origin": BASE, "Referer": BASE + "/"}), **kwargs)


def test_local_form_is_visible_and_private(local):
    response = page(local)
    text = response.get_data(as_text=True)
    assert 'id="no-token" hidden' not in text
    assert 'type="password"' in text and 'autocomplete="off"' in text
    assert 'action="/api/token"' in text
    assert "Connect your AirGradient account" in text and "data-1p-ignore" in text
    # "Show me where": closed by default, the picture is in the repo and described for screen readers
    assert '<details class="token-help">' in text and "Picture of AirGradient" in text and 'src="/static/airgradient-api-access.png"' in text and "alt=" in text
    assert (Path(server.__file__).parent / "static" / "airgradient-api-access.png").exists()
    assert "https://app.airgradient.com/settings/place?tab=4" in text
    assert "Your agent never sees it" in text and "Landed on the dashboard" in text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    nonce(response)


@pytest.mark.parametrize("base,remote", [("http://127.0.0.1:5555", "127.0.0.1"), ("http://[::1]:5555", "::1")])
def test_loopback_addresses_work(local, base, remote):
    local.get("/?setup=" + server.token_state.code, base_url=base, environ_overrides={"REMOTE_ADDR": remote})
    response = local.get("/", base_url=base, environ_overrides={"REMOTE_ADDR": remote})
    value = nonce(response)
    response = local.post("/api/token", base_url=base, environ_overrides={"REMOTE_ADDR": remote},
                          headers={"Origin": base}, data={"setup_nonce": value, "token": TOKEN})
    assert response.status_code == 303


def test_nonlocal_requests_never_get_or_submit_form(local):
    value = nonce(page(local))
    kwargs = {"environ_overrides": {"REMOTE_ADDR": "192.168.1.8"}}
    assert 'type="password"' not in page(local, **kwargs).get_data(as_text=True)
    assert submit(local, value, **kwargs).status_code == 403
    assert not server.env_path.exists()


def test_proxy_and_host_guesses_are_unneeded_with_the_code(local):
    headers = {"Host": "custom.local:5555", "X-Forwarded-For": "127.0.0.1", "Via": "proxy"}
    response = local.get("/?setup=" + server.token_state.code, base_url=BASE, headers=headers)
    assert response.status_code == 303
    response = local.get("/", base_url=BASE, headers=headers)
    assert 'type="password"' in response.get_data(as_text=True)


def test_network_instructions(local):
    text = page(local, environ_overrides={"REMOTE_ADDR": "192.168.1.8"}).get_data(as_text=True)
    assert "link the app printed" in text


@pytest.mark.parametrize("marker", ["RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "VERCEL", "RENDER", "FLY_APP_NAME", "K_SERVICE", "DYNO",
                                  "KUBERNETES_SERVICE_HOST", "KOYEB_APP_NAME", "WEBSITE_INSTANCE_ID"])
def test_hosted_copies_block_entry_even_with_empty_marker(local, monkeypatch, marker):
    value = nonce(page(local))
    monkeypatch.setenv(marker, "")
    text = page(local).get_data(as_text=True)
    assert 'type="password"' not in text
    if marker.startswith("RAILWAY"):
        assert "Add AIRGRADIENT_TOKEN in your Railway project → Variables, then redeploy." in text
    else:
        assert ".env" in text and ".env" in text
    assert submit(local, value).status_code == 403


@pytest.mark.parametrize("marker", ["DOCKER_MARKER", "PODMAN_MARKER"])
def test_container_instructions_and_guard(local, marker):
    value = nonce(page(local))
    getattr(server.token_setup, marker).touch()
    text = page(local).get_data(as_text=True)
    assert 'type="password"' not in text
    assert "docker-compose.yml" in text and "docker compose restart" in text
    assert submit(local, value).status_code == 403


def test_unwritable_folder_instructions_and_guard(local):
    value = nonce(page(local))
    folder = server.env_path.parent
    folder.chmod(0o500)
    try:
        text = page(local).get_data(as_text=True)
        assert 'type="password"' not in text
        assert ".env" in text
        assert submit(local, value).status_code == 403
    finally:
        folder.chmod(0o700)


@pytest.mark.parametrize("where", ["runtime", "environment", "file"])
def test_existing_token_cannot_be_replaced(local, monkeypatch, where):
    value = nonce(page(local))
    if where == "runtime":
        monkeypatch.setattr(server, "TOKEN", "already-set")
    elif where == "environment":
        monkeypatch.setenv("AIRGRADIENT_TOKEN", "already-set")
    else:
        server.env_path.write_text("AIRGRADIENT_TOKEN=already-set\n")
    assert 'type="password"' not in page(local).get_data(as_text=True)
    assert submit(local, value).status_code == 303
    assert server.TOKEN != TOKEN


@pytest.mark.parametrize("headers", [{}, {"Origin": "null"}, {"Origin": "null", "Referer": BASE + "/"}, {"Origin": "http://evil.example"},
    {"Origin": "http://localhost:5556"}, {"Origin": "https://localhost:5555"},
    {"Referer": BASE + ".evil.example/"}, {"Origin": BASE, "Referer": "http://evil.example/"}])
def test_cross_origin_and_missing_origin_are_refused(local, headers):
    assert submit(local, headers=headers).status_code == 403
    assert not server.env_path.exists()


def test_same_origin_referer_fallback(local):
    assert submit(local, headers={"Referer": BASE + "/"}).status_code == 303


def test_nonce_is_one_use_and_bound_to_browser_and_origin(local):
    value = nonce(page(local))
    with server.app.test_client() as stranger:
        assert submit(stranger, value).status_code == 403
    assert submit(local, "wrong-value").status_code == 403
    assert submit(local, value, headers={"Origin": BASE, "Host": "127.0.0.1:5555"}).status_code == 403
    assert submit(local, value).status_code == 303
    assert submit(local, value).status_code == 303


def test_wrong_token_is_not_saved_or_logged_and_nonce_is_consumed(local, monkeypatch, caplog, capsys):
    class Wrong(Reply):
        status_code = 401
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Wrong())
    value = nonce(page(local))
    caplog.set_level(logging.DEBUG)
    response = submit(local, value)
    assert response.status_code == 400
    assert response.headers["Cache-Control"] == "no-store"
    assert "AirGradient refused this token" in unescape(response.get_data(as_text=True))
    assert TOKEN not in response.get_data(as_text=True) + caplog.text + str(capsys.readouterr())
    assert not server.env_path.exists() and server.TOKEN == ""
    assert submit(local, value).status_code == 403
    nonce(response)  # retry uses a fresh form value, and an empty password field


def test_failed_attempts_are_limited_even_across_pages(local, monkeypatch):
    class Wrong(Reply):
        status_code = 403
    calls = []
    def wrong(*a, **k):
        calls.append(1)
        return Wrong()
    monkeypatch.setattr(sources.requests, "get", wrong)
    for _ in range(5):
        assert submit(local).status_code == 400
    response = submit(local)
    assert response.status_code == 429 and len(calls) == 5
    assert "Retry-After" in response.headers
    now = server.token_setup.time.monotonic()
    monkeypatch.setattr(server.token_setup.time, "monotonic", lambda: now + 301)
    assert submit(local).status_code == 400


def test_save_preserves_other_lines_is_private_and_switches_running_server(local, monkeypatch, caplog, capsys):
    server.env_path.write_text("# private settings\nOTHER=keep\nAIRGRADIENT_TOKEN=your_token_here\n")
    server.env_path.chmod(0o644)
    response = submit(local)
    assert response.status_code == 303 and response.headers["Location"] == "/"
    assert response.headers["Cache-Control"] == "no-store"
    assert server.env_path.read_text() == f"# private settings\nOTHER=keep\nAIRGRADIENT_TOKEN={TOKEN}\n"
    assert stat.S_IMODE(server.env_path.stat().st_mode) == 0o600
    assert list(server.env_path.parent.iterdir()) == [server.env_path]
    assert server.TOKEN == TOKEN and os.environ["AIRGRADIENT_TOKEN"] == TOKEN and server.MODE == "live"
    sources._cache.clear()
    assert local.get("/api/current").get_json()[0]["locationId"] == 1
    assert local.get("/health").get_json()["airgradient_token_set"] is True
    assert "no_token" not in page(local).get_data(as_text=True)
    assert TOKEN not in response.get_data(as_text=True) + page(local).get_data(as_text=True) + caplog.text + str(capsys.readouterr())


@pytest.mark.parametrize("failure", [requests.ConnectionError("secret=" + TOKEN), ValueError(TOKEN)])
def test_upstream_failures_are_plain_and_save_nothing(local, monkeypatch, failure, caplog):
    def fail(*a, **k):
        raise failure
    monkeypatch.setattr(sources.requests, "get", fail)
    response = submit(local)
    assert response.status_code == 502
    assert TOKEN not in response.get_data(as_text=True) + caplog.text
    assert not server.env_path.exists()


def test_disk_failure_does_not_install_token(local, monkeypatch, caplog):
    def fail(*a, **k):
        raise OSError(TOKEN)
    monkeypatch.setattr(server, "write_env_key", fail)
    response = submit(local)
    assert response.status_code == 500
    assert TOKEN not in response.get_data(as_text=True) + caplog.text
    assert server.TOKEN == "" and server.MODE == "no_token"


def test_demo_has_no_token_form_or_endpoint(local, monkeypatch):
    monkeypatch.setattr(server, "MODE", "demo")
    assert 'type="password"' not in page(local).get_data(as_text=True)
    assert submit(local, "anything").status_code == 403


@pytest.mark.parametrize("token", ["", "your_token_here", "two words", "bad\nOTHER=value", "'quoted'", "x" * 4097])
def test_malformed_tokens_never_call_airgradient(local, monkeypatch, token):
    def unexpected(*a, **k):
        pytest.fail("Malformed tokens must not reach the network")
    monkeypatch.setattr(sources.requests, "get", unexpected)
    response = local.post("/api/token", base_url=BASE, headers={"Origin": BASE},
                          data={"setup_nonce": nonce(page(local)), "token": token})
    assert response.status_code == 400
    assert not server.env_path.exists()


def test_missing_and_expired_form_values_are_refused(local, monkeypatch):
    assert local.post("/api/token", base_url=BASE, headers={"Origin": BASE}, data={"token": TOKEN}).status_code == 403
    value = nonce(page(local))
    now = server.token_setup.time.monotonic()
    monkeypatch.setattr(server.token_setup.time, "monotonic", lambda: now + 601)
    assert submit(local, value).status_code == 403


def test_post_body_size_is_bounded(local):
    response = local.post("/api/token", base_url=BASE, headers={"Origin": BASE},
                          data={"setup_nonce": nonce(page(local)), "token": "x" * 10000})
    assert response.status_code == 413 and not server.env_path.exists()


def test_env_symlink_does_not_expose_entry(local, tmp_path):
    target = tmp_path / "other-file"
    target.write_text("OTHER=keep\n")
    server.env_path.symlink_to(target)
    assert 'type="password"' not in page(local).get_data(as_text=True)
    assert submit(local, "anything").status_code == 403
    assert target.read_text() == "OTHER=keep\n"


def test_another_writer_winning_during_validation_is_not_overwritten(local, monkeypatch):
    def other_writer(*a, **k):
        server.env_path.write_text("AIRGRADIENT_TOKEN=from-terminal\n")
        return Reply()
    monkeypatch.setattr(sources.requests, "get", other_writer)
    assert submit(local).status_code == 303
    assert server.env_path.read_text() == "AIRGRADIENT_TOKEN=from-terminal\n"
    assert server.TOKEN == ""


def test_failed_atomic_replace_keeps_original_and_cleans_temp_files(local, monkeypatch):
    import config
    server.env_path.write_text("OTHER=keep\n")
    def fail(*a):
        raise OSError("disk failure")
    monkeypatch.setattr(config.os, "replace", fail)
    assert submit(local).status_code == 500
    assert server.env_path.read_text() == "OTHER=keep\n"
    assert list(server.env_path.parent.iterdir()) == [server.env_path]


def test_empty_account_is_a_valid_token(local, monkeypatch):
    class Empty(Reply):
        def json(self):
            return []
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Empty())
    assert submit(local).status_code == 303


def test_fresh_copy_with_an_empty_account_says_to_add_a_monitor(local, monkeypatch):
    from dataclasses import replace
    class Empty(Reply):
        def json(self):
            return []
    monkeypatch.setattr(server, "CFG", replace(server.CFG, demo=True))
    monkeypatch.setattr(server, "MODE", "demo")
    monkeypatch.delenv("DEMO", raising=False)
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Empty())
    assert submit(local).status_code == 303
    text = local.get("/", base_url=BASE).get_data(as_text=True)
    assert "Connected to AirGradient" in text and "No monitors with readings yet" in text and 'class="plist token-found"' not in text


def test_fresh_copy_card_lists_the_account_monitors(local, monkeypatch):
    from dataclasses import replace
    class Many(Reply):
        def json(self):
            return [{"locationId": i, "locationName": f"Room <{i}>"} for i in range(6)]
    monkeypatch.setattr(server, "CFG", replace(server.CFG, demo=True))
    monkeypatch.setattr(server, "MODE", "demo")
    monkeypatch.delenv("DEMO", raising=False)
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Many())
    assert submit(local).status_code == 303
    text = local.get("/", base_url=BASE).get_data(as_text=True)
    assert "6 monitors on your account" in text and "and 2 more" in text and "<li>Room <" not in text   # names are escaped


def test_upstream_debug_urls_cannot_log_candidate_token(local, monkeypatch, caplog):
    def debug_response(*a, **k):
        logging.getLogger("urllib3.connectionpool").debug('"GET /current?token=%s HTTP/1.1" 200', TOKEN)
        return Reply()
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(sources.requests, "get", debug_response)
    assert submit(local).status_code == 303
    assert TOKEN not in caplog.text and "token=***" in caplog.text


@pytest.mark.parametrize("status", [400, 401, 403])
def test_rejected_credentials_get_the_same_plain_error(local, monkeypatch, status):
    class Rejected(Reply):
        status_code = status
        def raise_for_status(self):
            raise requests.HTTPError("token=" + TOKEN)
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Rejected())
    response = submit(local)
    assert response.status_code == 400
    assert "AirGradient refused this token" in unescape(response.get_data(as_text=True))
    assert not server.env_path.exists()


def test_validation_makes_one_call_and_does_not_follow_redirects(local, monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs.get("allow_redirects") is False
        return Reply()
    monkeypatch.setattr(sources.requests, "get", get)
    assert submit(local).status_code == 303
    assert len(calls) == 1


def test_redirects_are_not_accepted_as_verified_credentials(local, monkeypatch):
    class Redirect(Reply):
        status_code = 302
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Redirect())
    assert submit(local).status_code == 502
    assert not server.env_path.exists()


@pytest.mark.parametrize("mode", ["no_token", "live", "demo"])
def test_all_app_pages_allow_same_origin_referrers(local, monkeypatch, mode):
    monkeypatch.setattr(server, "MODE", mode)
    assert page(local).headers["Referrer-Policy"] == "same-origin"


@pytest.mark.parametrize("headers", [{"Origin": BASE}, {"Origin": BASE, "Referer": BASE + "/"}])
def test_browser_same_origin_post_saves_token(local, headers):
    assert submit(local, headers=headers).status_code == 303


@pytest.mark.parametrize("token_set", [False, True])
@pytest.mark.parametrize("kwargs", [
    {"environ_overrides": {"REMOTE_ADDR": "192.168.1.8"}},
    {"headers": {"Origin": "http://evil.example"}},
    {"headers": {"Origin": "null"}},
    {"headers": {}},
])
def test_disallowed_callers_cannot_discover_token_state(local, monkeypatch, token_set, kwargs):
    value = nonce(page(local))
    if token_set:
        monkeypatch.setattr(server, "TOKEN", "already-set")
        monkeypatch.setattr(server, "MODE", "live")
    response = submit(local, value, **kwargs)
    assert response.status_code == 403
    assert response.get_json() == {"error": "Token entry is only available on this computer's local page."}


@pytest.mark.parametrize("cookie", ["é", "☃"])
def test_non_ascii_browser_cookie_is_refused(local, cookie):
    value = nonce(page(local))
    local.set_cookie(server.token_setup.COOKIE_NAME, cookie)
    assert submit(local, value).status_code == 403
    assert not server.env_path.exists()


@pytest.mark.parametrize("cookie", ["attacker-chosen", "é"])
def test_unknown_cookie_never_grants_a_form(local, cookie):
    local.set_cookie(server.token_setup.COOKIE_NAME, cookie)
    original = local.get_cookie(server.token_setup.COOKIE_NAME).value
    response = local.get("/", base_url=BASE)
    assert 'type="password"' not in response.get_data(as_text=True)
    assert local.get_cookie(server.token_setup.COOKIE_NAME).value == original


def test_validation_does_not_block_local_page_or_allow_a_second_save(local, monkeypatch):
    value = nonce(page(local))
    winner = "another-made-up-token"
    with ThreadPoolExecutor(max_workers=1) as pool:
        def validate(*a, **k):
            def another_browser():
                with server.app.test_client() as other:
                    return other.post("/api/token", base_url=BASE,
                                      headers={"Origin": BASE, "Referer": BASE + "/"},
                                      data={"setup_nonce": nonce(page(other)), "token": winner}).status_code
            # A second browser can load the form and win the save during this validation.
            # Recursive validation is replaced only after this first call begins.
            monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Reply())
            assert pool.submit(another_browser).result(timeout=5) == 303
            return Reply()
        monkeypatch.setattr(sources.requests, "get", validate)
        assert submit(local, value).status_code == 303
    assert server.TOKEN == winner


@pytest.mark.parametrize("code", [None, "wrong-code", "é"])
def test_startup_code_is_required(local, code):
    url = "/" if code is None else "/?setup=" + code
    response = local.get(url, base_url=BASE, follow_redirects=True)
    assert 'type="password"' not in response.get_data(as_text=True)
    assert not local.get_cookie(server.token_setup.COOKIE_NAME)
    assert "link the app printed" in response.get_data(as_text=True)
    assert local.post("/api/token", base_url=BASE, headers={"Origin": BASE},
                      data={"setup_nonce": "wrong", "token": TOKEN}).status_code == 403


def test_setup_redirect_strips_code_and_sets_private_cookie(local, caplog):
    code = server.token_state.code
    response = local.get("/?setup=" + code, base_url=BASE)
    assert response.status_code == 303 and response.headers["Location"] == "/"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert local.get_cookie(server.token_setup.COOKIE_NAME).value == code
    clean = local.get(response.headers["Location"], base_url=BASE)
    assert clean.request.query_string == b""
    assert code not in clean.get_data(as_text=True) + caplog.text
    assert submit(local, nonce(clean)).status_code == 303


def test_startup_codes_change_and_print_only_without_token(local, monkeypatch, capsys):
    first = server.token_state.code
    state = server.token_setup.TokenState()
    assert state.code != first
    monkeypatch.setattr(server, "token_state", state)
    server.print_setup_link(5600)
    assert capsys.readouterr().out == f"Paste your AirGradient token here: http://localhost:5600/?setup={state.code}\n"
    monkeypatch.setattr(server, "TOKEN", TOKEN)
    server.print_setup_link(5600)
    assert capsys.readouterr().out == ""
    assert server.token_setup.TokenState(TOKEN).code is None


def test_old_startup_cookie_is_refused_after_restart(local, monkeypatch):
    value = nonce(page(local))
    monkeypatch.setattr(server, "token_state", server.token_setup.TokenState())
    assert submit(local, value).status_code == 403


def test_fresh_copy_can_collect_token_before_home_config(local, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(server, "CFG", replace(server.CFG, demo=True))
    monkeypatch.setattr(server, "MODE", "demo")
    monkeypatch.delenv("DEMO", raising=False)
    assert submit(local).status_code == 303
    # Remain in the demo until setup writes a home and the agent restarts the app.
    assert server.MODE == "demo"
    # The page then says the token is saved and sends the user back to the agent, never the demo's made-up home.
    text = local.get("/", base_url=BASE).get_data(as_text=True)
    assert "Connected to AirGradient" in text and "1 monitor on your account" in text and "Unnamed monitor" in text and 'class="no-token fresh-copy"' in text and '"state": "no_token"' in text
    assert 'action="/api/token"' not in text and '"now":' not in text


def test_werkzeug_logs_only_the_first_request_with_the_setup_code(local):
    from werkzeug.serving import WSGIRequestHandler
    handler = object.__new__(WSGIRequestHandler)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    lines = []
    handler.log = lambda level, fmt, *args: lines.append(fmt % args)
    code = server.token_state.code
    handler.path = "/?setup=" + code
    response = local.get(handler.path, base_url=BASE)
    handler.log_request(response.status_code)
    handler.path = response.headers["Location"]
    response = local.get(handler.path, base_url=BASE)
    handler.log_request(response.status_code)
    assert code in lines[0]  # Werkzeug's initial request line includes the query string.
    assert code not in lines[1] and "GET / HTTP/1.1" in lines[1]


def test_connected_card_names_each_monitor_indoor_or_outdoor_and_sends_the_user_back(local, monkeypatch):
    from dataclasses import replace
    class Two(Reply):
        def json(self):
            return [{"locationId": 1, "locationName": "Living room", "locationType": "indoor", "model": "I-9PSL"},
                    {"locationId": 2, "locationName": "Back porch", "model": "O-1PST"}]
    monkeypatch.setattr(server, "CFG", replace(server.CFG, demo=True))
    monkeypatch.setattr(server, "MODE", "demo")
    monkeypatch.delenv("DEMO", raising=False)
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Two())
    assert submit(local).status_code == 303
    text = unescape(local.get("/", base_url=BASE).get_data(as_text=True))
    assert "<b>Living room</b><em>Indoor monitor</em>" in text and "<b>Back porch</b><em>Outdoor monitor</em>" in text
    assert "go back to your agent" in text and "You can close this tab" in text
    assert "<button" not in text.split("token-found", 1)[1].split("token-next", 1)[0]   # the monitors are a list, not controls


def test_a_malformed_token_is_told_apart_from_a_refused_one(local, monkeypatch):
    called = []
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: called.append(1) or Reply())
    response = local.post("/api/token", base_url=BASE, data={"setup_nonce": nonce(page(local)), "token": "has spaces in it"},
                          headers={"Origin": BASE, "Referer": BASE + "/"})
    assert response.status_code == 400 and not called   # never sent to AirGradient
    assert "doesn't look like an AirGradient token" in unescape(response.get_data(as_text=True))


def test_an_expired_form_is_a_page_with_a_way_forward_never_raw_json(local):
    page(local)
    response = submit(local, "a-form-value-from-an-old-tab")
    assert response.status_code == 403 and response.mimetype == "text/html"
    text = unescape(response.get_data(as_text=True))
    assert "nothing was sent" in text and 'name="setup_nonce"' in text   # a fresh form, ready for the token
    local.delete_cookie(server.token_setup.COOKIE_NAME)   # as after a restart: the old link no longer counts
    response = submit(local, "a-form-value-from-an-old-tab")
    assert response.status_code == 403 and response.mimetype == "text/html"
    assert "Ask your agent for the new setup link" in unescape(response.get_data(as_text=True))

