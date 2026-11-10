"""The summary card's rules: which readings lead, what to do and when, the profiles row and the day chart's data.
Also AirGradient's PM2.5 correction (corrected_pm), which the neighbors and the demo's public monitors share.

Pure functions, no network or Flask: server.py and tools/replay.py gather the inputs and call build_summary.
Spec: internal/specs/summary-redesign-spec.md.
"""
import math
from datetime import datetime, timedelta

import phrases
from config import APPLIANCES as _APPLIANCES, DEFAULT_LIMITS, bearing_in

LIMITS = dict(DEFAULT_LIMITS)   # the server fills these from the config at import
APPLIANCES = set(_APPLIANCES)   # what dries a damp room here ([home] appliances); the server fills it from the config
OUTLOOK_HOURS = 8                  # hours of PM2.5 forecast the items and the runner look ahead
ANCHOR_FADE = timedelta(hours=6)   # how long a gap between the monitor and CAMS takes to fade (anchor_forecast)
MAX_ITEMS = 3                      # items shown on the card; the rest go on the Also line
CALIBRATION_RANGE = (0.1, 3.0)     # bounds on the monitor/CAMS factor, so a few odd hours can't zero or triple the forecast
DRIER_BY_C = 1                     # °C: outside counts as drier when its dew point is this much below the room's
DRY_AIR_LOOKAHEAD_H = 12            # hours to find drier outdoor air for a damp room with no drying appliance
NIGHT = (22, 7)                    # hours: "last night" runs from 10 PM to 7 AM
NIGHT_STALE, NIGHT_ALL = 0.5, 0.9  # share of last night over the CO₂ limit: "stale", and "all last night" (else "most of")
COLD_C = 10                        # °C: "close it after ten minutes" when it gets this cold within COLD_AHEAD
COLD_AHEAD = timedelta(hours=8)
TONIGHT_FROM = 18                  # hour: a chart starting at or after 6 PM is headed "Tonight"

# AirGradient's EPA correction for PM2.5 (the US EPA's correction for Plantower sensors, Barkjohn et al., extended to
# high concentrations), as AirGradient writes it in its firmware (airgradienthq/arduino, src/PMS/PMS.cpp,
# PMSBase::compensate) and its map backend (airgradienthq/airgradient-map, apps/api/src/utils/getEpaCorrectedPM.ts):
#   raw < 30:        0.524·raw − 0.0862·RH + 5.75
#   30 ≤ raw < 50:   blends the slope from 0.524 to 0.786 (f = raw/20 − 3/2)
#   50 ≤ raw < 210:  0.786·raw − 0.0862·RH + 5.75
#   210 ≤ raw < 260: blends to the high form (f = raw/50 − 21/5)
#   raw ≥ 260:       2.966 + 0.69·raw + 8.84e-4·raw²
# never below 0; a raw 0 stays 0. The world list gives the raw pm02; a home's API answer has pm02_corrected. Used for
# the neighbors (server._fetch_nearby) and the demo's public monitors (demo/public.py), so every PM2.5 shares one basis.
EPA_BANDS = (30, 50, 210, 260)   # µg/m³ raw: where the formula's pieces meet
EPA_SLOPE_LOW, EPA_SLOPE_MID, EPA_SLOPE_HIGH = 0.524, 0.786, 0.69   # the raw PM2.5 slope below 30, 50–210, from 260
EPA_RH = 0.0862   # µg/m³ per % relative humidity, subtracted
EPA_OFFSET, EPA_OFFSET_HIGH = 5.75, 2.966   # µg/m³: the constant term below 210, and from 260
EPA_SQUARE = 8.84e-4   # the raw² term from 260


def corrected_pm(pm02, rhum):
    """AirGradient's EPA-corrected PM2.5 (µg/m³, one decimal, as its map shows it) from a raw pm02 and the monitor's
    relative humidity (%); None without both. The formula and its sources are above EPA_BANDS."""
    try:
        raw, rh = float(pm02), min(100.0, max(0.0, float(rhum)))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(raw) and math.isfinite(rh)):
        return None
    if raw == 0:
        return 0.0
    b30, b50, b210, b260 = EPA_BANDS
    if raw < b30:
        value = EPA_SLOPE_LOW * raw - EPA_RH * rh + EPA_OFFSET
    elif raw < b50:
        f = (raw - b30) / (b50 - b30)
        value = (EPA_SLOPE_MID * f + EPA_SLOPE_LOW * (1 - f)) * raw - EPA_RH * rh + EPA_OFFSET
    elif raw < b210:
        value = EPA_SLOPE_MID * raw - EPA_RH * rh + EPA_OFFSET
    elif raw < b260:
        f = (raw - b210) / (b260 - b210)
        value = ((EPA_SLOPE_HIGH * f + EPA_SLOPE_MID * (1 - f)) * raw - EPA_RH * rh * (1 - f) + EPA_OFFSET_HIGH * f
                 + EPA_OFFSET * (1 - f) + EPA_SQUARE * raw ** 2 * f)
    else:
        value = EPA_OFFSET_HIGH + EPA_SLOPE_HIGH * raw + EPA_SQUARE * raw ** 2
    value = round(value, 1)
    return value if value > 0 else 0.0


def clock(t):
    """'4 PM', '4:30 PM'."""
    h = t.hour % 12 or 12
    return f"{h}{'' if t.minute == 0 else f':{t.minute:02d}'} {'PM' if t.hour >= 12 else 'AM'}"


def anchor_forecast(cams, measured_now, cams_now):
    """CAMS works on a 45 km grid and misses a nearby road, so keep its shape but start it from what the backyard
    monitor reads now. Without a measurement (or a CAMS value for now) the raw values are used, flagged False."""
    pts = [(t, v) for t, v in cams if v is not None]
    if measured_now is None or cams_now is None:
        return pts, False
    off = measured_now - cams_now
    t0 = pts[0][0] if pts else None
    # the offset fades to nothing over ANCHOR_FADE: a passing spike (a fire pit, cooking) shouldn't last all night
    fade = lambda t: max(0.0, 1 - (t - t0).total_seconds() / ANCHOR_FADE.total_seconds())
    return [(t, max(0, round(v + off * fade(t), 1))) for t, v in pts], True


def calibrate_forecast(cams, monitor_pts, now, min_hours=6):
    """CAMS runs well above the backyard monitor here (several times higher over a week of replay), so scale it by
    the median of monitor/CAMS over the last 24 hours, hour by hour. The shape stays, the level comes down, and a
    passing spike barely moves a 24-hour median. Returns (future values, factor), or (None, None) with too few
    matching hours (the caller then falls back to anchor_forecast)."""
    hour = lambda t: t.replace(minute=0, second=0, microsecond=0)
    sums = {}
    for t, v in monitor_pts:
        if v is not None and now - timedelta(hours=24) <= t <= now:
            sums.setdefault(hour(t), []).append(v)
    ratios = sorted((sum(vs) / len(vs) + .5) / (c + .5) for t, c in cams
                    if c is not None and t <= now and (vs := sums.get(hour(t))))
    if len(ratios) < min_hours:
        return None, None
    mid = len(ratios) // 2
    k = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    k = min(max(k, CALIBRATION_RANGE[0]), CALIBRATION_RANGE[1])
    return [(t, round(v * k, 1)) for t, v in cams if v is not None and t > now], k


def pm_outlook(pm_now, adjusted, now, hours=OUTLOOK_HOURS):
    """Outdoor PM2.5 now and over the next `hours`: one view shared by the PM2.5 item and the pills."""
    end = now + timedelta(hours=hours)
    fc = [(t, v) for t, v in adjusted if now < t <= end]
    best_v, best_t, forecast = pm_now, None, False
    for t, v in fc:
        if best_v is None or v > best_v:
            best_v, best_t, forecast = v, t, True
    stretches, start, last = [], None, None
    over = lambda v: round(v) > LIMITS["pm"]   # as displayed: 15.3 reads "15", which isn't over 15
    if pm_now is not None and over(pm_now):
        start = now
    for t, v in fc:
        if over(v):
            start = start or t
            last = t
        elif start is not None:
            stretches.append((start, t))
            start = None
    if start is not None:
        stretches.append((start, (last or now) + timedelta(hours=1)))
    return {"now": pm_now, "max": best_v, "max_at": best_t, "forecast": forecast, "over": stretches,
            "high": best_v is not None and round(best_v) > LIMITS["pm_high"], "cause": None}


def _n(v):
    return f"{round(v):,}"


def candidates(r, outlook, pollen_today, night=None):
    """Every reading past its limit, scored by how far past it is, highest first; a measured reading beats a
    forecast one on a tie."""
    out = []
    co2, rh, pm_now = r.get("co2"), r.get("rh"), r.get("pm_now")
    if co2 is not None and co2 > LIMITS["co2"]:
        out.append({"id": "co2", "score": co2 / LIMITS["co2"], "forecast": False, "label": "CO₂ inside", "key": "in",
                    "num": _n(co2), "unit": "ppm", "ctx": f"{round((co2 / LIMITS['co2'] - 1) * 100)}% over the {LIMITS['co2']} limit" + _night_ctx(night),
                    "facts": {"co2": round(co2)}})
    if rh is not None and rh > LIMITS["rh_damp"]:
        out.append({"id": "rh", "score": rh / LIMITS["rh_damp"], "forecast": False, "label": "Humidity inside", "key": None,
                    "num": _n(rh), "unit": "%", "ctx": f"{round(rh - LIMITS['rh_damp'])} points over {LIMITS['rh_damp']}",
                    "facts": {"rh": round(rh), "dry": False, **({"rh_out": round(r["rh_out"])} if r.get("rh_out") is not None else {})}})
    elif rh is not None and rh < LIMITS["rh_dry"]:
        out.append({"id": "rh", "score": LIMITS["rh_dry"] / max(rh, 1), "forecast": False, "label": "Humidity inside", "key": None,
                    "num": _n(rh), "unit": "%", "ctx": f"{round(LIMITS['rh_dry'] - rh)} points under {LIMITS['rh_dry']}",
                    "facts": {"rh": round(rh), "dry": True, **({"rh_out": round(r["rh_out"])} if r.get("rh_out") is not None else {})}})
    m = outlook.get("max")
    if m is not None and round(m) > LIMITS["pm"]:
        fc = outlook["forecast"]
        cause = outlook.get("cause")
        if fc:
            ctx = f"Peak {clock(outlook['max_at'])}" + (f", {cause}" if cause else "") + (f" · now {round(pm_now)}" if pm_now is not None else "")
        else:
            ctx = f"{round((m / LIMITS['pm'] - 1) * 100)}% over the {LIMITS['pm']} limit"
        out.append({"id": "pm", "score": m / LIMITS["pm"], "forecast": fc, "label": "PM2.5 outside", "key": "out",
                    "num": _n(m), "unit": "µg/m³", "ctx": ctx,
                    "facts": {"pm": round(m), **({"pm_now": round(pm_now)} if pm_now is not None else {}),
                              **({"peak_at": clock(outlook["max_at"])} if fc else {}), **({"cause": cause} if cause else {})}})
    if pollen_today and (pollen_today.get("index") or 0) >= LIMITS["pollen"]:
        idx, name = pollen_today["index"], pollen_today.get("name") or "Pollen"
        out.append({"id": "pollen", "score": idx / LIMITS["pollen"], "forecast": False, "label": "Pollen today", "key": None,
                    "num": str(idx), "unit": "of 5", "ctx": f"{name} pollen, high today",
                    "facts": {"pollen_index": idx, "pollen_type": name.lower()}})
    out.sort(key=lambda c: (-round(c["score"], 9), c["forecast"]))
    return out


def _night_ctx(night):
    if not night or not night["stale"]:
        return ""
    return f" · over {LIMITS['co2']} all last night" if night["share"] >= NIGHT_ALL else f" · over {LIMITS['co2']} most of last night"


def last_night(co2_pts, now):
    """Last night's CO2, 10 PM to 7 AM: {peak, share over 800, stale (over 800 at least half the night)}.
    Only from 7 AM to 10 PM: before 7 the night isn't over, after 10 a new one has started and the reading now counts."""
    if not NIGHT[1] <= now.hour < NIGHT[0]:
        return None
    end = now.replace(hour=NIGHT[1], minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=(NIGHT[1] - NIGHT[0]) % 24)
    vals = [v for t, v in co2_pts if v is not None and start <= t < end]
    if not vals:
        return None
    share = sum(v > LIMITS["co2"] for v in vals) / len(vals)
    return {"peak": round(max(vals)), "share": round(share, 2), "stale": share >= NIGHT_STALE}


def select(cands, extra):
    """The top items, and one Also line for the rest: readings past their limit first, then `extra` notes."""
    items = cands[:MAX_ITEMS]
    rest = [f"{c['label']} {c['num']}{'' if c['unit'] == '%' else ' '}{c['unit']}" for c in cands[MAX_ITEMS:]] + list(extra)
    if not rest:
        return items, None
    shown = rest[:2]
    tail = f", and {len(rest) - 2} more" if len(rest) > 2 else ""
    return items, "Also: " + ", ".join(shown) + tail + "."


def fmt_range(a, b):
    """'4–8 PM', '4:30–8 PM', '11 PM–1 AM'."""
    if (a.hour >= 12) == (b.hour >= 12) and a.date() == b.date():
        return clock(a).rsplit(" ", 1)[0] + "–" + clock(b)
    return clock(a) + "–" + clock(b)


def dew_point(t, rh):
    """Magnus formula, °C; None without both readings."""
    if t is None or rh is None or rh <= 0:
        return None
    g = math.log(rh / 100) + 17.62 * t / (243.12 + t)
    return 243.12 * g / (17.62 - g)


def _drier_outside(r):
    d_in, d_out = dew_point(r.get("t_in"), r.get("rh")), dew_point(r.get("t_out"), r.get("rh_out"))
    return d_in is not None and d_out is not None and d_out < d_in - DRIER_BY_C


def _first_over(outlook, now):
    """The first PM2.5-over-15 stretch that hasn't ended."""
    return next(((a, b) for a, b in outlook.get("over") or [] if b > now), None)


AC_DRY = "Run the AC’s dry mode"   # the damp-room action when the AC is the only appliance


def action(item, r, outlook, rush, now, estimate=False, hourly=()):
    """What to do for one item, with its time: text, when, and when_end (ISO, the moment `when` goes stale).
    `estimate`: the outdoor PM2.5 has no reading now (an indoor-only home on the area or the model). Airing before the
    dirty stretch then reads "now, before 8 AM" ("now, before the 8 AM rush" when it starts in a rush with the wind
    toward home), so it doesn't read as a clash with "Windows shut · 8–11 AM".
    `hourly`: weather rows with forecast dew points, to time airing a damp room with no drying appliance."""
    act = lambda text, when=None, end=None: {"text": text, "when": when, "when_end": end.isoformat() if end else None}
    stretch = _first_over(outlook, now)
    kind = item["id"]
    if kind == "co2":
        if outlook.get("high") and stretch and stretch[0] <= now:   # dirty now: wait it out; dirty later: air before
            return act("Air out", f"after {clock(stretch[1])}", stretch[1])
        if stretch and stretch[0] <= now:
            return act("Open a window for 10 min", f"after {clock(stretch[1])}", stretch[1])
        if stretch and stretch[0] - now <= timedelta(hours=2):
            if not estimate:
                return act("Open a window for 10 min", f"before {clock(stretch[0])}", stretch[0])
            in_rush = any(a <= stretch[0] < b and toward for a, b, toward in rush)
            at = f"the {clock(stretch[0])} rush" if in_rush else clock(stretch[0])
            return act("Open a window for 10 min", f"now, before {at}", stretch[0])
        return act("Open a window for 10 min", "now")
    if kind == "rh":
        rh = r.get("rh")
        if rh is not None and rh > LIMITS["rh_damp"]:
            drier_now = _drier_outside(r)
            if drier_now and not stretch:
                return act("Air the room for 10 min", "drier outside")
            if "dehumidifier" in APPLIANCES:
                return act("Run the dehumidifier", f"until under {LIMITS['rh_stop']}%")
            if "ac_dry" in APPLIANCES:
                return act(AC_DRY, f"until under {LIMITS['rh_stop']}%")
            if not APPLIANCES and not drier_now:
                room_dew = dew_point(r.get("t_in"), rh)
                if room_dew is not None:
                    dry_hour = next((h["t"] for h in sorted(hourly, key=lambda h: h["t"])
                                     if now < h["t"] <= now + timedelta(hours=DRY_AIR_LOOKAHEAD_H)
                                     and h.get("dew") is not None and h["dew"] < room_dew - DRIER_BY_C
                                     and not any(a <= h["t"] < b for a, b in outlook.get("over") or [])), None)
                    if dry_hour is not None:
                        return act("Air the room for 10 min", f"after {clock(dry_hour)}", dry_hour)
            return act("Keep the windows shut")   # nothing to lower it: no "until under"
        if _drier_outside(r):
            return act("Keep windows shut", "while it’s this dry outside")
        return act(None)
    if kind == "pm":
        text = "Keep windows shut" if outlook.get("high") else "Windows shut"
        if not stretch:
            return act(text, "now")
        if stretch[0] <= now:
            return act(text, f"until {clock(stretch[1])}", stretch[1])
        return act(text, fmt_range(*stretch), stretch[1])
    if kind == "pollen":
        return act("Keep windows shut", "today")
    return act(None)


def profiles_row(r, outlook, pollen_today, smoke, night, now, indoor=True):
    """Toddler, Sinus & allergy, Runner: ok True (green), False (amber) or None (no reading), a short state, and the facts
    phrases.pill_why turns into the (i) text. Without an indoor monitor (indoor False) the toddler can't be judged
    (CO₂ is the toddler's reading) and the sinus profile runs on pollen alone."""
    co2, rh = r.get("co2"), r.get("rh")
    pol = (pollen_today or {}).get("index")
    stretch = _first_over(outlook, now)

    if not indoor:   # nothing to say about the toddler until an indoor monitor is added, outside air included
        tod = (None, "Needs an indoor monitor")
    elif outlook.get("high"):   # outside first: it applies even with the indoor monitor offline
        tod = (False, "Dirty outside")
    elif co2 is None:
        tod = (None, "No reading")
    elif co2 > LIMITS["co2"]:
        tod = (False, "Stale indoors")
    elif night and night["stale"]:
        tod = (False, "Stale last night")   # until 10 PM: the fix is airing before bed
    else:
        tod = (True, "Fresh indoors")

    damp = rh is not None and rh > LIMITS["rh_damp"]
    dry = rh is not None and rh < LIMITS["rh_dry"]
    pollen_high = pol is not None and pol >= LIMITS["pollen"]
    if rh is None:
        if pollen_high:
            sin = (False, "Pollen high")
        elif not indoor and pol is not None:   # no indoor monitor at all: pollen alone decides
            sin = (True, "Pollen low")
        else:
            sin = (None, "No reading")
    elif damp and pollen_high:
        sin = (False, "Damp + pollen")
    elif damp:
        sin = (False, "Too damp")
    elif dry:
        sin = (False, "Too dry")
    elif pollen_high:
        sin = (False, "Pollen high")
    else:
        sin = (True, "Pollen low" if pol is not None else "All fine")

    if outlook.get("now") is None and outlook.get("max") is None:
        run = (None, "No reading")
    elif outlook.get("high"):
        run = (False, "Skip today")
    elif stretch and stretch[0] <= now:
        run = (False, f"Run after {clock(stretch[1])}")   # the action, with the time the dirty stretch ends
    elif stretch:
        run = (False, f"Avoid {fmt_range(*stretch)}")
    else:
        # no "till 4 PM" from the rush wind or rain: in a week of replay the rush didn't raise PM2.5 at the monitor
        run = (True, "Clean air")

    def profile(pid, name, v, facts):
        return {"id": pid, "name": name, "ok": v[0], "state": v[1], "facts": facts}
    return [
        profile("toddler", "Toddler", tod, {"co2": co2, **({"night_peak": night["peak"]} if night and night["stale"] else {})}),
        profile("sinus", "Sinus & allergy", sin, {"rh": rh, "pollen_index": pol, "pollen_type": (pollen_today or {}).get("name")}),
        profile("runner", "Runner", run, {"pm_now": outlook.get("now"), "smoke": bool(smoke)}),
    ]


# ── The day chart's data, and the whole card ──
CHART_BEFORE = timedelta(hours=3.5)   # how much of the past the day chart shows before now
CHART_SPAN = timedelta(hours=15)      # the day chart's whole width
RAIN_SHOWN = 30                       # %: the chart's 3-hourly row shows rain from this chance of precipitation
STRONG_UV = 6                         # UV index from which the chart marks strong sun (WHO's "high")


def _floor_hour(t):
    return t.replace(minute=0, second=0, microsecond=0)


def _iso(t):
    return t.isoformat()


def timeline(now, co2_pts, rh_pts, pm_past, pm_fc_adj, hourly, sun, show_rh, pm_past_model=False):
    """Everything the chart draws, with ISO times: measured CO₂ (and humidity when it's a damp item), PM2.5 measured
    and forecast, the 3-hourly temperature and rain row, strong-sun stretches, sunrise/sunset and night.
    pm_past_model: the past PM2.5 is the model's hours, not a monitor's (a public monitor without history), and the
    series says so ("source": "model")."""
    t0 = _floor_hour(now - CHART_BEFORE)
    t1 = t0 + CHART_SPAN
    win = lambda ps, a, b: [[_iso(t), round(v, 1)] for t, v in ps if v is not None and a <= t <= b]
    co2 = win(co2_pts, t0, now) or None
    rh = (win(rh_pts, t0, now) or None) if show_rh else None
    by_hour = {_floor_hour(h["t"]): h for h in hourly}
    hours = []
    t = t0 + timedelta(hours=(-t0.hour) % 3)
    while t <= t1:
        h = by_hour.get(t)
        if h is not None:
            near = [x for x in hourly if t - timedelta(hours=1.5) <= x["t"] < t + timedelta(hours=1.5)]
            pop = max((x.get("pop") or 0) for x in near) if near else 0
            mm = round(sum((x.get("mm") or 0) for x in near), 1)
            hours.append({"t": _iso(t), "temp": None if h.get("temp") is None else round(h["temp"]),
                          "pop": pop if pop >= RAIN_SHOWN else None, "mm": mm if pop >= RAIN_SHOWN else None})
        t += timedelta(hours=3)
    uv, start, top = [], None, 0
    for h in sorted(hourly, key=lambda x: x["t"]):
        if not t0 <= h["t"] <= t1:
            continue
        if (h.get("uv") or 0) >= STRONG_UV:
            start = start or h["t"]
            top = max(top, round(h["uv"]))
        elif start is not None:
            uv.append([_iso(start), _iso(h["t"]), top]); start, top = None, 0
    if start is not None:
        uv.append([_iso(start), _iso(t1), top])
    events = sorted(sun, key=lambda e: e["t"])
    night, dark_from = [], None
    prev = [e for e in events if e["t"] <= t0]
    inside = [e for e in events if t0 <= e["t"] <= t1]
    # dark at the start: the last event before was a sunset, or (no earlier event known) the first one is a sunrise
    if (prev and prev[-1]["kind"] == "Sunset") or (not prev and inside and inside[0]["kind"] == "Sunrise"):
        dark_from = t0
    for e in events:
        if not t0 <= e["t"] <= t1:
            continue
        if e["kind"] == "Sunset":
            dark_from = e["t"]
        elif dark_from is not None:
            night.append([_iso(dark_from), _iso(e["t"])]); dark_from = None
    if dark_from is not None:
        night.append([_iso(dark_from), _iso(t1)])
    return {"t0": _iso(t0), "t1": _iso(t1), "now": _iso(now), "co2": co2, "rh": rh,
            "pm": {"past": win(pm_past, t0, now), "fc": [[_iso(t), round(v, 1)] for t, v in pm_fc_adj if now < t <= t1],
                   **({"source": "model"} if pm_past_model else {})},
            "hours": hours, "uv": uv,
            "sun": [{"t": _iso(e["t"]), "kind": e["kind"]} for e in events if t0 <= e["t"] <= t1],
            "night": night, "limits": {"co2": LIMITS["co2"], "pm": LIMITS["pm"], "rh": LIMITS["rh_damp"]}}


def _since(pts, limit, now):
    """When the latest unbroken stretch over `limit` began, as '1:30 PM' or 'yesterday 2:20 PM' (to 10 minutes),
    or None. None too when the whole series is over, since the stretch began before it and its start is unknown."""
    vals = [(t, v) for t, v in pts if v is not None and t <= now]
    if not vals or vals[-1][1] <= limit:
        return None
    i = len(vals) - 1
    while i > 0 and vals[i - 1][1] > limit:
        i -= 1
    if i == 0 and vals[0][0] <= now - timedelta(hours=23):
        return None
    t = vals[i][0]
    t = t.replace(minute=t.minute // 10 * 10, second=0, microsecond=0)
    s = "noon" if (t.hour, t.minute) == (12, 0) else clock(t)
    return f"yesterday {s}" if t.date() < now.date() else s


def build_summary(r, cams, hourly, co2_pts, rh_pts, pm_past, smoke, pollen_today, pollen_tomorrow, rush, sun, now, road=None,
                  pm_past_model=False, monitor_label=None, area_factor=None, source=None, indoor=True):
    """The whole card from the rules: items with actions and explanations, the Also line, the profiles row, the chart.
    `road` is the road's name (None without one); `rush` its rush windows from rush_windows(). With pm_past_model,
    pm_past is the model's past hours: the chart draws it, but it can't calibrate the model against itself.
    `monitor_label` names the outdoor monitor in the PM2.5 item's sentences ("your yard monitor", "this monitor");
    None leaves phrases' default, the home's outdoor monitor. `area_factor`: the public monitors' median ratio to the
    model around a home without an outdoor monitor (server.outdoor_source, "area"); without a monitor's own history to
    calibrate with, it scales the model like calibrate_forecast's factor (fit "area"), the model's past hours too.
    `source`: where a home without an outdoor monitor gets its outdoor PM2.5 ({kind, name, distance_km, area_count,
    fallback: "monitor", "list" or False}, server.outdoor_source's facts), for the PM2.5 item's sentences; None for a home with one.
    `indoor` False: an outdoor-only home. No indoor readings, whatever was passed, and the toddler profile waits for an
    indoor monitor."""
    if not indoor:
        r, co2_pts, rh_pts = {**r, "co2": None, "rh": None, "t_in": None}, [], []
    cams_now = next((v for t, v in cams if _floor_hour(t) == _floor_hour(now) and v is not None), None)
    adjusted, k = calibrate_forecast(cams, [] if pm_past_model else pm_past, now)
    fit = "calibrated" if k is not None else None
    if adjusted is None and area_factor is not None:
        k = min(max(area_factor, CALIBRATION_RANGE[0]), CALIBRATION_RANGE[1])
        adjusted, fit = [(t, round(v * k, 1)) for t, v in cams if v is not None and t > now], "area"
        if pm_past_model:   # the chart's past is the model's: the same scale, so the line doesn't jump at now
            pm_past = [(t, round(v * k, 1)) for t, v in pm_past if v is not None]
    if adjusted is None:   # not enough history to calibrate: anchor to the reading now, fading over 6 hours
        adjusted, anchored = anchor_forecast([(t, v) for t, v in cams if t >= _floor_hour(now)], r.get("pm_now"), cams_now)
        fit = "anchored" if anchored else None
    outlook = pm_outlook(r.get("pm_now"), adjusted, now)
    if outlook["max"] is not None and round(outlook["max"]) > LIMITS["pm"]:
        at_t = outlook["max_at"] or now
        if smoke:
            outlook["cause"] = "smoke"
        elif road and any(a <= at_t < b and toward for a, b, toward in rush):
            outlook["cause"] = f"{road} rush"
    night = last_night(co2_pts, now)

    pollen_ok = pollen_today if pollen_today and (pollen_today.get("index") or 0) >= LIMITS["pollen"] else None
    cands = candidates(r, outlook, pollen_ok, night)
    extra = []
    if pollen_tomorrow and (pollen_tomorrow.get("index") or 0) >= LIMITS["pollen"] and not pollen_ok:
        extra.append(f"pollen high tomorrow ({(pollen_tomorrow.get('name') or 'pollen').lower()}), keep windows shut overnight")
    items, also = select(cands, extra)

    estimate = source is not None and r.get("pm_now") is None   # no outdoor PM2.5 reading now: the area or the model
    # where the outdoor PM2.5 comes from, for its item's sentences (phrases.py words them)
    source_facts = {"source_kind": source["kind"], "source_name": source.get("name"), "source_km": source.get("distance_km"),
                    "area_count": source.get("area_count"), "source_fallback": source.get("fallback") or False} if source else {}
    wind_at = lambda t: next((h.get("wind_dir") for h in hourly if t is not None and _floor_hour(h["t"]) == _floor_hour(t)), None)
    for it in items:
        # whose profile the item is: its chip on the card names that profile and opens its sentence after the item's
        it["profile"] = {"co2": "toddler", "rh": "sinus", "pollen": "sinus"}.get(it["id"], "toddler" if outlook.get("high") and indoor else "runner")
        it["action"] = action(it, r, outlook, rush, now, estimate=estimate, hourly=hourly)
        f = dict(it["facts"])
        when = it["action"]["when"] or ""
        if it["id"] == "co2":
            f["since"] = _since(co2_pts, LIMITS["co2"], now)
            if when.startswith("now, before "):   # an estimate's stretch ahead: rush fumes only when the action says so
                at = when[len("now, before "):]
                f["rush_start" if at.startswith("the ") else "dirty_at"] = at.removeprefix("the ").removesuffix(" rush")
            elif when.startswith("before "):   # the PM2.5 stretch ahead: with a road and rush hours, its rush fumes
                f["rush_start" if road and rush else "dirty_at"] = when[7:]
            elif when.startswith("after "):
                f["clean_at"] = when[6:]
            cold = next((h for h in sorted(hourly, key=lambda x: x["t"])
                         if now < h["t"] <= now + COLD_AHEAD and h.get("temp") is not None and h["temp"] <= COLD_C), None)
            if cold:
                f.update(temp_at=round(cold["temp"]), temp_time=clock(cold["t"]))
        home = {}   # facts for the sentences only, not kept on the item
        if it["id"] == "rh":
            f["drier_out"] = _drier_outside(r)
            if when.startswith("after "):
                f["dry_at"] = when[6:]
            if f["drier_out"] and not it["action"]["text"].startswith("Air"):
                f["drier_out"] = None   # drier outside, but the air there is dirty soon: say nothing about airing
            # the AC as a second option, unless it is the action; "stop at" only when something is running
            home = {"ac_too": "ac_dry" in APPLIANCES and it["action"]["text"] != AC_DRY, "appliance": bool(APPLIANCES),
                    "no_appliance": not APPLIANCES and it["action"]["text"] == "Keep the windows shut"}
        if it["id"] == "pm":
            f.update(wind_dir=wind_at(outlook["max_at"] or now), smoke=bool(smoke))
            # how the forecast was fitted, and to which monitor: its timing sentence says so
            home = {"forecast_fit": fit, **({"monitor_label": monitor_label} if monitor_label else {}), **source_facts}
        it["why"] = phrases.why(it["id"], {**f, **home})
        it["facts"] = f

    profiles = profiles_row(r, outlook, pollen_today, smoke, night, now, indoor)
    # the appliances pick the damp-room words, and the home's monitors the words for a missing one; like `home` above,
    # not kept as facts
    words = {**{a: True for a in APPLIANCES}, **({"source_kind": source["kind"]} if source else {}),
             **({} if indoor else {"no_indoor": True})}
    for n in profiles:
        n["why"] = phrases.pill_why(n["id"], {**n["facts"], **words}, n["ok"], n["state"])
    show_rh = any(i["id"] == "rh" and not i["facts"].get("dry") for i in items)
    tl = timeline(now, co2_pts, rh_pts, pm_past, adjusted, hourly, sun, show_rh, pm_past_model)
    t0 = datetime.fromisoformat(tl["t0"])
    return {"label": "Tonight" if t0.hour >= TONIGHT_FROM else "Today", "clock": clock(now), "items": items, "also": also,
            "profiles": profiles, "all_clear": not items, "timeline": tl}



def rush_windows(hourly, now, windows, toward):
    """Today's and tomorrow's rush windows of the road as (start, end, wind_toward): toward when at least half the
    window's forecast hours blow from the arc `toward` (lo, hi) in degrees, which can cross north (lo > hi)."""
    out = []
    for d in (0, 1):
        day = (now + timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
        for start, end, _name in windows:
            a, b = day + timedelta(hours=start), day + timedelta(hours=end)
            winds = [h["wind_dir"] for h in hourly if a <= h["t"] < b and h.get("wind_dir") is not None]
            n = sum(1 for w in winds if bearing_in(w, toward))
            out.append((a, b, bool(winds) and n * 2 >= len(winds)))
    return out
