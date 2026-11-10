#!/usr/bin/env bash
# Setup cards with made-up accounts only: 6 states × 2 widths × 2 themes.
#   scripts/setup_shots.sh
#   PY=/path/to/python CHROME=/path/to/chrome scripts/setup_shots.sh
# Needs the app's Python requirements, Node.js and Chrome (same lookup as screenshot.sh).
# Copies tracked working files, so before/after runs include uncommitted page changes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if [ -z "${PY:-}" ]; then
  for p in "$ROOT/.venv/bin/python" "$(command -v python3 || true)"; do
    [ -x "$p" ] && "$p" -c 'import flask, requests' 2>/dev/null && { PY="$p"; break; }
  done
fi
[ -n "${PY:-}" ] || { echo "No Python with the app's requirements found (set PY=...)."; exit 1; }
PY="$("$PY" -c 'import sys; print(sys.executable)')"
[ -x "$CHROME" ] || { echo "Chrome not found at $CHROME (set CHROME=...)."; exit 1; }
command -v node >/dev/null || { echo "Node.js is needed (it drives Chrome)."; exit 1; }

TMP="$(mktemp -d)"
APP_PID=""; FAKE_PID=""
stop_servers() {
  for pid in "$APP_PID" "$FAKE_PID"; do
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  done
  APP_PID=""; FAKE_PID=""
}
cleanup() { stop_servers; rm -rf "$TMP"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Readiness and real browser actions live ONLY in the disposable copy.
# Native form submission supplies the session cookie, one-use nonce and Origin.
cat > "$TMP/hook.js" <<'JS'
const card = document.getElementById('no-token');
const form = card?.querySelector('form');
if (state === 'help') card.querySelector('details.token-help').open = true;
if (form && ['refused', 'connected', 'no-monitors'].includes(state) && !sessionStorage.getItem('submitted')) {
  sessionStorage.setItem('submitted', '1');
  form.elements.token.value = state === 'refused' ? 'wrong-screenshot-token' : testToken;
  form.requestSubmit();
}
window.__shotReady = () => {
  if (!card || card.hidden || document.fonts.status !== 'loaded') return false;
  const text = card.textContent;
  // page markers, not wording: rewording the page must not break the screenshots
  if (state === 'refused') return !!card.querySelector('.token-error');
  if (state === 'connected') return card.querySelectorAll('.token-found li').length === 2;
  if (state === 'no-monitors') return !!card.querySelector('.token-ok') && !card.querySelector('.token-found');
  if (state === 'plain') return !form && !card.querySelector('.token-ok');
  if (state === 'help') {
    const image = card.querySelector('.token-help img');
    return !!form && card.querySelector('.token-help').open && image.complete && image.naturalWidth > 0;
  }
  return !!form && !card.querySelector('.token-help').open;
};
JS

fresh_app() {
  local name="$1"
  APP_DIR="$TMP/$name"
  "$PY" - "$ROOT" "$APP_DIR" <<'PY'
import shutil
import subprocess
import sys
from pathlib import Path

root, dest = map(Path, sys.argv[1:])
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
for name in filter(None, files):
    relative = Path(name)
    if any(p.startswith('.env') for p in relative.parts) or name == 'config.toml':
        continue
    source = root / relative
    if source.is_file():
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
page = dest / 'index.html'
page.write_text(page.read_text().replace('</body>', '<script type="module" src="/static/setup-shot.js"></script></body>'))
PY
}

free_port() {
  "$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    print(sock.getsockname()[1])
PY
}

start_servers() {
  local mode="$1"
  local fake_port app_port
  fake_port="$(free_port)"
  if [ "$mode" = empty ]; then
    "$PY" "$ROOT/scripts/fake_airgradient.py" "$fake_port" --empty >"$TMP/fake.log" 2>&1 &
  else
    "$PY" "$ROOT/scripts/fake_airgradient.py" "$fake_port" >"$TMP/fake.log" 2>&1 &
  fi
  FAKE_PID=$!
  for _ in {1..40}; do
    curl --noproxy '*' -s -o /dev/null --max-time 1 "http://127.0.0.1:$fake_port/" && break
    sleep 0.25
  done
  curl --noproxy '*' -s -o /dev/null --max-time 1 "http://127.0.0.1:$fake_port/" || { cat "$TMP/fake.log"; return 1; }
  app_port="$(free_port)"
  # An allowlist prevents inherited tokens, CONFIG_TOML, DEMO or host markers from changing the setup.
  (cd "$APP_DIR" && exec env -i PATH="$PATH" HOME="$HOME" LANG="${LANG:-en_US.UTF-8}" \
    PORT="$app_port" HOST=127.0.0.1 AIRGRADIENT_API_BASE="http://127.0.0.1:$fake_port/public/api/v1" \
    "$PY" server.py) >"$TMP/app.log" 2>&1 &
  APP_PID=$!
  BASE="http://localhost:$app_port/"
  for _ in {1..40}; do
    curl --noproxy '*' -sf -o /dev/null --max-time 1 "$BASE" && break
    sleep 0.25
  done
  curl --noproxy '*' -sf -o /dev/null --max-time 1 "$BASE" || { cat "$TMP/app.log"; return 1; }
  LINK="$("$PY" - "$TMP/app.log" <<'PY'
import re
import sys
from pathlib import Path
match = re.search(r'http://localhost:\d+/\?setup=[A-Za-z0-9_-]+', Path(sys.argv[1]).read_text())
if not match:
    sys.exit('No setup link in the temporary app output.')
print(match[0])
PY
)"
}

shoot_state() {
  local state="$1" url="$LINK" height
  [ "$state" != plain ] || url="$BASE"
  "$PY" - "$ROOT/scripts/fake_airgradient.py" "$state" > "$APP_DIR/static/setup-shot.js" <<'PY'
import json
import runpy
import sys
print('const state = ' + json.dumps(sys.argv[2]) + ';')
print('const testToken = ' + json.dumps(runpy.run_path(sys.argv[1])['TEST_TOKEN']) + ';')
PY
  cat "$TMP/hook.js" >> "$APP_DIR/static/setup-shot.js"
  for width in 1440 390; do
    height=900; [ "$width" != 390 ] || height=844
    for theme in light dark; do
      echo "Capturing $state · $width · $theme"
      # A new profile redeems the link and follows the system theme on every capture.
      # Use the full page so help and error lines remain visible on phones.
      node "$ROOT/scripts/screenshot.mjs" "$CHROME" "$url" \
        "$ROOT/docs/setup-shots/$state-$width-$theme.png" "$TMP/profile-$state-$width-$theme" \
        --viewport "${width}x${height}" --theme "$theme" \
        || { echo "FAILED: $state · $width · $theme (the page never reached this state)" >&2; exit 1; }
    done
  done
}

mkdir -p "$ROOT/docs/setup-shots"
fresh_app account
start_servers account
for state in form help refused connected; do shoot_state "$state"; done
stop_servers
fresh_app empty
start_servers empty
shoot_state no-monitors
stop_servers
fresh_app plain
# A made-up home config exercises the ordinary missing-token card, without redeeming the link.
cp "$APP_DIR/demo/config.toml" "$APP_DIR/config.toml"
start_servers account
shoot_state plain
echo "Setup screenshots: $ROOT/docs/setup-shots/"
