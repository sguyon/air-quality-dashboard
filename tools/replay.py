"""Replay the summary card on a week of real data, to review it before the page switches.

    python3 tools/replay.py [days=7]

Writes internal/replay/<date>-<HHMM>.json (one card per snapshot: 8:00 AM, 3:40 PM, 9:30 PM) and
internal/replay/gallery.html. internal/ is gitignored: these are the household's real readings, and the repo is
public, so they never go into git. The AirGradient token comes from .env through server.py and is never printed.

Caveats, shown in the gallery header:
- the "forecast" part is Open-Meteo's own recent analysis (past_days), not the forecast as it was at the time;
- NOAA smoke and Google pollen only exist for today, so past snapshots have neither.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import requests  # noqa: E402

import server  # noqa: E402  (loads .env and the config; gives api_get, the limits, the home and the road)
import summary  # noqa: E402

OUT = os.path.join(ROOT, "internal", "replay")
SNAPSHOTS = [(8, 0), (15, 40), (21, 30)]


def pick(row, *keys):
    for k in keys:
        if row.get(k) is not None:
            return row[k]
    return None


def monitors():
    """{"indoor": id, "outdoor": id} from the current readings (the page tells them apart by locationType)."""
    rows = server.api_get("/locations/measures/current") or []
    out = {}
    for r in rows:
        if r.get("locationType") in ("indoor", "outdoor") and r.get("locationType") not in out:
            out[r["locationType"]] = r["locationId"]
    return out


def history(location_id, start, end, tz):
    rows = []
    t = start
    while t < end:   # the API caps one request, so ask a day at a time
        u = min(t + timedelta(days=1), end)
        part = server.api_get(f"/locations/{int(location_id)}/measures/past", {
            "from": t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": u.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}) or []
        rows += part
        t = u
    out = []
    for r in rows:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).astimezone(tz)
        except (KeyError, ValueError, AttributeError):
            continue
        out.append((ts, r))
    return sorted(out, key=lambda p: p[0])


def open_meteo(days, tz):
    w = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": server.HOME_LAT, "longitude": server.HOME_LON, "past_days": days + 1, "forecast_days": 2,
        "hourly": "temperature_2m,precipitation_probability,precipitation,uv_index,wind_direction_10m",
        "daily": "sunrise,sunset", "timezone": server.CFG.place.timezone}, timeout=20).json()
    a = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
        "latitude": server.HOME_LAT, "longitude": server.HOME_LON, "past_days": days + 1, "forecast_days": 2,
        "hourly": "pm2_5", "timezone": server.CFG.place.timezone}, timeout=20).json()
    loc = lambda s: datetime.fromisoformat(s).replace(tzinfo=tz)
    hw = w.get("hourly") or {}
    hourly = [{"t": loc(t), "temp": hw["temperature_2m"][k], "pop": hw["precipitation_probability"][k],
               "mm": hw["precipitation"][k], "uv": hw["uv_index"][k], "wind_dir": hw["wind_direction_10m"][k]}
              for k, t in enumerate(hw.get("time") or [])]
    ah = a.get("hourly") or {}
    cams = [(loc(t), v) for t, v in zip(ah.get("time") or [], ah.get("pm2_5") or [])]
    d = w.get("daily") or {}
    sun = [{"t": loc(t), "kind": kind} for key, kind in (("sunrise", "Sunrise"), ("sunset", "Sunset")) for t in d.get(key) or [] if t]
    return hourly, cams, sun


def snapshot(now, ins, outs, hourly, cams, sun):
    last = lambda rows: next((r for t, r in reversed(rows) if t <= now), {})
    day_ago = now - timedelta(hours=24)
    win = lambda rows, f: [(t, f(r)) for t, r in rows if day_ago <= t <= now and f(r) is not None]
    ri, ro = last(ins), last(outs)
    r = {"co2": pick(ri, "rco2_corrected", "rco2"), "rh": pick(ri, "rhum_corrected", "rhum"), "t_in": pick(ri, "atmp_corrected", "atmp"),
         "pm_now": pick(ro, "pm02_corrected", "pm02"), "rh_out": pick(ro, "rhum_corrected", "rhum"), "t_out": pick(ro, "atmp_corrected", "atmp")}
    hr = [h for h in hourly if now - timedelta(hours=4) <= h["t"] <= now + timedelta(hours=24)]
    return summary.build_summary(
        r=r, cams=[(t, v) for t, v in cams if now - timedelta(hours=24) <= t <= now + timedelta(hours=24)], hourly=hr,
        co2_pts=win(ins, lambda x: pick(x, "rco2_corrected", "rco2")), rh_pts=win(ins, lambda x: pick(x, "rhum_corrected", "rhum")),
        pm_past=win(outs, lambda x: pick(x, "pm02_corrected", "pm02")), smoke=False, pollen_today=None, pollen_tomorrow=None,
        rush=server.rush_windows(hr, now), road=server.ROAD.name if server.ROAD else None, sun=sun, now=now)


GALLERY = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Summary replay</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../../static/app.css"><link rel="stylesheet" href="../../static/summary.css">
<style>body{padding:20px;background:var(--bg)}h1{font:600 18px Inter;color:var(--ink);margin:0 0 4px}p.n{font:14px Inter;color:var(--muted);margin:0 0 18px;max-width:900px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:18px}.wide .grid{grid-template-columns:1fr}
.cell h2{font:600 13px Inter;color:var(--soft);margin:0 0 6px}.box{background:var(--card);border-radius:20px;border:1px solid var(--line)}</style>
</head><body><h1>Summary replay: __N__ snapshots</h1>
<p class="n">Real readings from both monitors. The "forecast" after each snapshot is Open-Meteo's recent analysis, not the forecast as it was then. No smoke or pollen for past days. Add <code>?wide</code> for the desktop layout.</p>
<div class="grid" id="g"></div>
<script src="replay-data.js"></script><script src="../../static/summary.js"></script>
<script>if (location.search.includes('wide')) document.body.classList.add('wide');
for (const [name, s] of REPLAY) { const c = document.createElement('div'); c.className = 'cell';
  c.innerHTML = `<h2>${name}</h2><div class="box"><div class="sx"></div></div>`; document.getElementById('g').appendChild(c);
  SummaryCard.renderSummary(c.querySelector('.sx'), s, new Date(s.timeline.now)); }</script></body></html>"""


def main(days=7):
    os.makedirs(OUT, exist_ok=True)
    tz = server.local_now().tzinfo
    today = server.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    ids = monitors()
    start, end = today - timedelta(days=days + 1), today
    ins, outs = history(ids["indoor"], start, end, tz), history(ids["outdoor"], start, end, tz)
    hourly, cams, sun = open_meteo(days, tz)
    cards = []
    for d in range(days, 0, -1):
        for h, m in SNAPSHOTS:
            now = (today - timedelta(days=d)).replace(hour=h, minute=m)
            s = snapshot(now, ins, outs, hourly, cams, sun)
            name = now.strftime("%a %-d %b, %-I:%M %p")
            with open(os.path.join(OUT, now.strftime("%Y-%m-%d-%H%M") + ".json"), "w") as f:
                json.dump(s, f, default=str, indent=1)
            cards.append([name, s])
    with open(os.path.join(OUT, "replay-data.js"), "w") as f:
        f.write("window.REPLAY = " + json.dumps(cards, default=str) + ";")
    with open(os.path.join(OUT, "gallery.html"), "w") as f:
        f.write(GALLERY.replace("__N__", str(len(cards))))
    print(f"{len(cards)} snapshots written to internal/replay/")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
