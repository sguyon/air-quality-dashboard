#!/usr/bin/env bash
# The README's pictures, all from the demo (made-up data, never real readings):
#   docs/hero-light.png, docs/hero-dark.png  a laptop (Morning rush) and a phone (All clear), each on the page's
#                                             first screen, transparent background (≤ 1600 px wide)
#   docs/screenshot.png                       the whole desktop page, light theme (1440 px wide)
#
#   scripts/screenshot.sh                                   starts the demo on port 5556, stops it after
#   URL=http://127.0.0.1:5556/ scripts/screenshot.sh        uses a demo that is already running
#   PY=/path/to/python scripts/screenshot.sh               the Python that runs the demo
#
# Needs Google Chrome, Node.js and ImageMagick (magick). Chrome runs headless with its software renderer,
# so the WebGL map draws. The page's ?shot mode gives the light theme (?shot=dark the dark one) without the
# sky, the dev line or the demo's top area, without touching any saved settings. The laptop and the full page show the
# "rush" moment, the phone "clear".
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
case "$URL" in *\?*) Q="&";; *) Q="?";; esac
PAGE="${URL}${Q}moment=rush&shot"     # the laptop and the full page: the morning rush, with things to do
CLEAR="${URL}${Q}moment=clear&shot"   # the phone: all clear

HERO_DPR="${HERO_DPR:-1.8}"   # the hero is drawn at 920 × 640 CSS px; 1.8 keeps the trimmed image under 1600 px wide

shoot() { node "$ROOT/scripts/screenshot.mjs" "$CHROME" "$1" "$2" "$TMP/profile-$RANDOM" "${@:3}" >/dev/null; }   # one Chrome at a time

for theme in light dark; do
  shoot "$PAGE" "$TMP/desk-$theme.png" --viewport 1440x900 --dpr 2 --first-screen --theme "$theme"
  shoot "$CLEAR" "$TMP/phone-$theme.png" --viewport 390x844 --dpr 3 --first-screen --theme "$theme"
  bg="#$(magick "$TMP/phone-$theme.png" -format '%[hex:p{6,6}]' info: | cut -c1-6)"   # the page's background, behind the phone's status bar
  hero="file://$ROOT/scripts/hero.html?theme=$theme&bg=${bg/\#/%23}&desk=file://$TMP/desk-$theme.png&phone=file://$TMP/phone-$theme.png"
  shoot "$hero" "$TMP/hero-$theme.png" --viewport 920x640 --dpr "$HERO_DPR" --first-screen --transparent
  # trim to the last pixel with any alpha at all (the shadows fade out inside hero.html's margin), then 2 px of nothing
  box="$(magick "$TMP/hero-$theme.png" -alpha extract -threshold 0 -format '%@' info:)"
  magick "$TMP/hero-$theme.png" -crop "$box" +repage -bordercolor none -border 2 "$TMP/hero-$theme-cut.png"
  w="$(magick identify -format '%w' "$TMP/hero-$theme-cut.png")"
  [ "$w" -le 1600 ] || echo "  note: the hero is $w px wide, resized to 1600 (lower HERO_DPR to keep it sharp)" >&2
  magick "$TMP/hero-$theme-cut.png" -resize '1600x>' -strip -define png:compression-level=9 "$ROOT/docs/hero-$theme.png"
  # every pixel of the outer 2 px must be fully transparent, or GitHub shows the shadow's cut edge
  edge="$(magick "$ROOT/docs/hero-$theme.png" -alpha extract -fill black -draw "rectangle 2,2 %[fx:w-3],%[fx:h-3]" -alpha off -format '%[max]' info:)"
  [ "$edge" = "0" ] || { echo "docs/hero-$theme.png: the edge is not fully transparent (max alpha $edge)"; exit 1; }
  echo "Saved docs/hero-$theme.png ($(magick identify -format '%wx%h' "$ROOT/docs/hero-$theme.png"))"
done

shoot "$PAGE" "$TMP/page.png" --viewport 1440x900 --dpr 1 --theme light
magick "$TMP/page.png" -strip -define png:compression-level=9 "$ROOT/docs/screenshot.png"
echo "Saved docs/screenshot.png ($(magick identify -format '%wx%h' "$ROOT/docs/screenshot.png"))"
