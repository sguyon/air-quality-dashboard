#!/usr/bin/env bash
# The README's pictures, all from the demo (made-up data, never real readings):
#   docs/hero-light.png, docs/hero-dark.png  a laptop and a phone showing the page's first screen (≤ 1600 px wide)
#   docs/screenshot.png                       the whole desktop page, light theme (1440 px wide)
#
#   scripts/screenshot.sh                                   starts the demo on port 5556, stops it after
#   URL=http://127.0.0.1:5556/ scripts/screenshot.sh        uses a demo that is already running
#   PY=/path/to/python scripts/screenshot.sh               the Python that runs the demo
#
# Needs Google Chrome, Node.js and ImageMagick (magick). Chrome runs headless with its software renderer,
# so the WebGL map draws. The page's ?shot mode gives the light theme (?shot=dark the dark one) without the
# sky, the dev line or the demo banner, without touching any saved settings. The story moment is "rush".
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
# for the demo server: $PY, else the first of .venv's Python and python3 that has the app's requirements
if [ -z "${PY:-}" ]; then
  for p in "$ROOT/.venv/bin/python" "$(command -v python3 || true)"; do
    [ -x "$p" ] && "$p" -c 'import flask' 2>/dev/null && { PY="$p"; break; }
  done
fi

[ -x "$CHROME" ] || { echo "Chrome not found at $CHROME (set CHROME=...)"; exit 1; }
command -v magick >/dev/null || { echo "ImageMagick (magick) is needed: brew install imagemagick"; exit 1; }
command -v node >/dev/null || { echo "Node.js is needed (it drives Chrome)"; exit 1; }

TMP="$(mktemp -d)"; SERVER=""
cleanup() { [ -n "$SERVER" ] && kill "$SERVER" 2>/dev/null; rm -rf "$TMP"; }
trap cleanup EXIT

if [ -z "${URL:-}" ]; then
  [ -n "${PY:-}" ] || { echo "No Python with flask found: install requirements.txt, or set PY=/path/to/python"; exit 1; }
  URL="http://127.0.0.1:5556/"
  # never the real page: the demo serves made-up data and needs no config or token
  (cd "$ROOT" && DEMO=1 exec "$PY" -m flask --app server run --port 5556) >"$TMP/server.log" 2>&1 &
  SERVER=$!
  for _ in $(seq 1 40); do curl -sf -o /dev/null --max-time 2 "$URL" && break; sleep 0.5; done
fi
curl -sf -o /dev/null --max-time 10 "$URL" || { echo "The demo isn't answering at $URL."; [ -f "$TMP/server.log" ] && tail -5 "$TMP/server.log"; exit 1; }
case "$URL" in *\?*) PAGE="$URL&moment=rush&shot";; *) PAGE="$URL?moment=rush&shot";; esac

shoot() { node "$ROOT/scripts/screenshot.mjs" "$CHROME" "$1" "$2" "$TMP/profile-$RANDOM" "${@:3}" >/dev/null; }   # one Chrome at a time

for theme in light dark; do
  shoot "$PAGE" "$TMP/desk-$theme.png" --viewport 1440x900 --dpr 2 --first-screen --theme "$theme"
  shoot "$PAGE" "$TMP/phone-$theme.png" --viewport 390x844 --dpr 3 --first-screen --theme "$theme"
  bg="#$(magick "$TMP/phone-$theme.png" -format '%[hex:p{6,6}]' info: | cut -c1-6)"   # the page's background, behind the phone's status bar
  hero="file://$ROOT/scripts/hero.html?theme=$theme&bg=${bg/\#/%23}&desk=file://$TMP/desk-$theme.png&phone=file://$TMP/phone-$theme.png"
  shoot "$hero" "$TMP/hero-$theme.png" --viewport 856x540 --dpr 1.94 --first-screen --transparent   # 1.94: the trimmed hero lands just under 1600 px
  box="$(magick "$TMP/hero-$theme.png" -alpha extract -threshold 2% -format '%@' info:)"   # the devices and their visible shadow
  magick "$TMP/hero-$theme.png" -crop "$box" +repage -resize '1600x>' -strip -define png:compression-level=9 "$ROOT/docs/hero-$theme.png"
  echo "Saved docs/hero-$theme.png ($(magick identify -format '%wx%h' "$ROOT/docs/hero-$theme.png"))"
done

shoot "$PAGE" "$TMP/page.png" --viewport 1440x900 --dpr 1 --theme light
magick "$TMP/page.png" -strip -define png:compression-level=9 "$ROOT/docs/screenshot.png"
echo "Saved docs/screenshot.png ($(magick identify -format '%wx%h' "$ROOT/docs/screenshot.png"))"
