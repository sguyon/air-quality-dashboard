#!/usr/bin/env bash
# The demo's link-preview images (what a link shows on LinkedIn, X, Slack, iMessage, Reddit), all from the demo (made-up data):
#   og-large.png          1200 × 630: the name, the tagline, four cards and the phone (scripts/preview.html)
#   og-large-popout.png   1200 × 630: the other large one, a bigger phone with parts of the page lifted out of it
#   og-square.png         1200 × 1200: the name, a short tagline and the summary card with its chart (a variant of scripts/preview.html)
#
#   scripts/preview.sh                          renders the three into a new temporary folder and prints where
#   scripts/preview.sh --out <dir>              renders them into <dir>
#   scripts/preview.sh --only large|popout|square   renders just that one (faster while changing a word)
#   scripts/preview.sh --write                  also saves static/og-demo.png (the large one) and static/og-demo-square.png
#   scripts/preview.sh --write --variant popout saves the popout one as static/og-demo.png instead
#   URL=http://127.0.0.1:5568/ scripts/preview.sh   uses a demo that is already running (a plain one: DEMO=1 flask)
#   PY=/path/to/python scripts/preview.sh       the Python that runs the demo (default: one with flask, else uv's)
#
# Every word, the demo moment, the cards and what the phone hides live in scripts/preview.json: change it and run this again.
# The phone is the demo page shot on a 390 px phone with preview.json's CSS added, then cut into parts
# (screenshot.mjs --css and --rects) that preview.html puts back together around the Dynamic Island.
# Needs Google Chrome, Node.js and ImageMagick (magick), like scripts/screenshot.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
CONFIG="$ROOT/scripts/preview.json"
OUT=""; WRITE=""; VARIANT="cards"; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2;;
    --write) WRITE=1; shift;;
    --variant) VARIANT="$2"; shift 2;;
    --only) ONLY="$2"; shift 2;;
    *) echo "Unknown option $1 (see the top of $0)"; exit 2;;
  esac
done
case "$VARIANT" in cards|popout) ;; *) echo "--variant is cards or popout"; exit 2;; esac
case "$ONLY" in ""|large|popout|square) ;; *) echo "--only is large, popout or square"; exit 2;; esac
[ -n "$WRITE" ] && [ -n "$ONLY" ] && { echo "--write renders everything: leave out --only"; exit 2; }

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
[ -n "$OUT" ] || OUT="$(mktemp -d)"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"

if [ -z "${URL:-}" ]; then
  RUN=("${PY:-}")
  if [ -z "${PY:-}" ]; then   # no Python with flask: uv runs one with the app's requirements
    command -v uv >/dev/null || { echo "No Python with flask found: install requirements.txt or uv, or set PY=/path/to/python"; exit 1; }
    RUN=(uv run -q --with-requirements requirements.txt python)
  fi
  PORT="${PREVIEW_PORT:-5568}"
  URL="http://127.0.0.1:$PORT/"
  curl -sf -o /dev/null --max-time 2 "$URL" && { echo "Something already answers at $URL: stop it, set PREVIEW_PORT, or pass it as URL."; exit 1; }
  # never the real page: the demo serves made-up data and needs no config or token
  (cd "$ROOT" && DEMO=1 exec "${RUN[@]}" -m flask --app server run --port "$PORT") >"$TMP/server.log" 2>&1 &
  SERVER=$!
  for _ in $(seq 1 40); do curl -sf -o /dev/null --max-time 2 "$URL" && break; sleep 0.5; done
fi
curl -sf -o /dev/null --max-time 10 "$URL" || { echo "The demo isn't answering at $URL."; [ -f "$TMP/server.log" ] && tail -5 "$TMP/server.log"; exit 1; }
if curl -sf --max-time 10 "$URL" | grep -q '/_dev/'; then
  echo "$URL adds local dev tools to the page. Use a plain demo: run this script without URL, or start DEMO=1 flask on a free port."; exit 1
fi
case "$URL" in *\?*) Q="&";; *) Q="?";; esac

shoot() { node "$ROOT/scripts/screenshot.mjs" "$CHROME" "$1" "$2" "$TMP/profile-$RANDOM" "${@:3}" >/dev/null; }   # one Chrome at a time

# the CSS to add to the phone's page and the selectors to measure, from preview.json
node -e '
  const c = require(process.argv[1]), fs = require("fs");
  const css = c.phone.hide.join(",\n") + " { display: none !important; }\n" + c.phone.css.join("\n") + "\n";
  fs.writeFileSync(process.argv[2], css);
  fs.writeFileSync(process.argv[3], css + ".sx-items { display: none !important; }\n");   // the popout'"'"'s phone: no rows, the chart moves up
  fs.writeFileSync(process.argv[4], Object.values(c.phone.parts).join(";"));
  fs.writeFileSync(process.argv[5], Object.entries(c.phone.parts).filter(([k]) => k !== "row").map(([, s]) => s).join(";"));
  fs.writeFileSync(process.argv[6], c.moment);
' "$CONFIG" "$TMP/phone.css" "$TMP/phone2.css" "$TMP/parts.txt" "$TMP/parts2.txt" "$TMP/moment.txt"
shoot "${URL}${Q}moment=$(cat "$TMP/moment.txt")&shot" "$TMP/phone.png" --viewport 390x1500 --dpr 3 --first-screen --theme light \
  --css "$TMP/phone.css" --rects "$(cat "$TMP/parts.txt")"
shoot "${URL}${Q}moment=$(cat "$TMP/moment.txt")&shot" "$TMP/phone2.png" --viewport 390x1500 --dpr 3 --first-screen --theme light \
  --css "$TMP/phone2.css" --rects "$(cat "$TMP/parts2.txt")"
# what the composition pages read: the settings, the phone shots and where each part is in them (by its name in preview.json)
node -e '
  const c = require(process.argv[1]), fs = require("fs");
  const shot = (png, boxesFile, bg, skip) => {
    const boxes = require(boxesFile);
    const parts = Object.fromEntries(Object.entries(c.phone.parts).filter(([k]) => k !== skip).map(([k, s]) => [k, boxes[s]]));
    const missing = Object.keys(parts).filter(k => !parts[k]);
    if (missing.length) { console.error("Not on the page: " + missing.map(k => k + " (" + c.phone.parts[k] + ")").join(", ")); process.exit(1); }
    return { src: "file://" + png, width: 390, bg, parts };
  };
  fs.writeFileSync(process.argv[2], "window.PREVIEW = " + JSON.stringify(c) + ";\nwindow.SHOT = " + JSON.stringify(shot(process.argv[3], process.argv[4], process.argv[5])) + ";\nwindow.SHOT2 = " + JSON.stringify(shot(process.argv[6], process.argv[7], process.argv[5], "row")) + ";\n");
' "$CONFIG" "$TMP/data.js" "$TMP/phone.png" "$TMP/phone.json" "#$(magick "$TMP/phone.png" -format '%[hex:p{6,6}]' info: | cut -c1-6)" "$TMP/phone2.png" "$TMP/phone2.json"

render() {   # <page> <query> <W>x<H> <out name>
  shoot "file://$ROOT/scripts/$1?$2&data=file://$TMP/data.js" "$TMP/$4" --viewport "$3" --dpr 1 --first-screen --marks
  cp "$TMP/${4%.png}.layout.json" "$OUT/${4%.png}.layout.json"
  magick "$TMP/$4" -strip -define png:compression-level=9 "$OUT/$4"
  echo "Saved $OUT/$4 ($(magick identify -format '%wx%h' "$OUT/$4"))"
}
{ [ -z "$ONLY" ] || [ "$ONLY" = large ]; } && render preview.html variant=cards 1200x630 og-large.png
{ [ -z "$ONLY" ] || [ "$ONLY" = popout ]; } && render preview.html variant=popout 1200x630 og-large-popout.png
{ [ -z "$ONLY" ] || [ "$ONLY" = square ]; } && render preview.html variant=square 1200x1200 og-square.png

if [ -n "$WRITE" ]; then
  large="og-large.png"; [ "$VARIANT" = popout ] && large="og-large-popout.png"
  dest_l="$(node -p 'require(process.argv[1]).out.large' "$CONFIG")"; dest_s="$(node -p 'require(process.argv[1]).out.square' "$CONFIG")"
  cp "$OUT/$large" "$ROOT/static/$dest_l"; cp "$OUT/og-square.png" "$ROOT/static/$dest_s"
  echo "Wrote static/$dest_l ($VARIANT) and static/$dest_s"
fi
