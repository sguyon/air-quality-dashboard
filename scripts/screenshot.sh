#!/usr/bin/env bash
# Capture the whole dashboard page for the README: docs/screenshot.png (1440 px wide, light theme, no sky).
#
#   scripts/screenshot.sh
#   URL=https://air-quality-dashboard-dev.up.railway.app/ scripts/screenshot.sh
#
# Needs Google Chrome, Node.js and ImageMagick (magick). The page must be running (default http://127.0.0.1:5555).
# Chrome runs headless with its software renderer, so the WebGL map draws. The page's ?shot mode
# gives the light theme without the sky and hides the dev line, without touching any saved settings.
set -euo pipefail

URL="${URL:-http://127.0.0.1:5555/}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/docs/screenshot.png"

[ -x "$CHROME" ] || { echo "Chrome not found at $CHROME (set CHROME=...)"; exit 1; }
command -v magick >/dev/null || { echo "ImageMagick (magick) is needed: brew install imagemagick"; exit 1; }
curl -sf -o /dev/null --max-time 10 "$URL" || { echo "The page isn't answering at $URL. Start the server first."; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
case "$URL" in *\?*) SHOT="$URL&shot";; *) SHOT="$URL?shot";; esac

# headless Chrome driven by scripts/screenshot.mjs: waits until the summary, the map and the intro are done
command -v node >/dev/null || { echo "Node.js is needed (it drives Chrome)"; exit 1; }
node "$(dirname "$0")/screenshot.mjs" "$CHROME" "$SHOT" "$TMP/page.png" "$TMP/profile" >/dev/null

magick "$TMP/page.png" "$OUT"
echo "Saved $OUT ($(magick identify -format '%wx%h' "$OUT"))"
