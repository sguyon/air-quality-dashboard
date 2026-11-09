"""The summary card's rules: which readings lead, what to do and when, the needs row and the day chart's data.

Pure functions, no network or Flask: server.py and tools/replay.py gather the inputs and call build_summary.
Spec: internal/specs/summary-redesign-spec.md.
"""
import math
from datetime import datetime, timedelta

import phrases
from config import DEFAULT_LIMITS, bearing_in

LIMITS = dict(DEFAULT_LIMITS)   # the server fills these from the config at import
HOUSEHOLD = {"equipment": {"dehumidifier", "ac_dry"}}   # Sacha, 8 Nov 2026: no humidifier, no purifier
OUTLOOK_HOURS = 8
ANCHOR_FADE = timedelta(hours=6)
MAX_ITEMS = 3


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
    k = min(max(k, 0.1), 3.0)
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
    return f" · over {LIMITS['co2']} all last night" if night["share"] >= 0.9 else f" · over {LIMITS['co2']} most of last night"


def last_night(co2_pts, now):
    """Last night's CO2, 10 PM to 7 AM: {peak, share over 800, stale (over 800 at least half the night)}.
    Only from 7 AM to 10 PM: before 7 the night isn't over, after 10 a new one has started and the reading now counts."""
    if not 7 <= now.hour < 22:
        return None
    end = now.replace(hour=7, minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=9)
    vals = [v for t, v in co2_pts if v is not None and start <= t < end]
    if not vals:
        return None
    share = sum(v > LIMITS["co2"] for v in vals) / len(vals)
    return {"peak": round(max(vals)), "share": round(share, 2), "stale": share >= 0.5}


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
    return d_in is not None and d_out is not None and d_out < d_in - 1


def _first_over(outlook, now):
    """The first PM2.5-over-15 stretch that hasn't ended."""
    return next(((a, b) for a, b in outlook.get("over") or [] if b > now), None)


def action(item, r, outlook, rush, now):
    """What to do for one item, with its time: text, when, and when_end (ISO, the moment `when` goes stale)."""
    act = lambda text, when=None, end=None: {"text": text, "when": when, "when_end": end.isoformat() if end else None}
    stretch = _first_over(outlook, now)
    kind = item["id"]
    if kind == "co2":
        if outlook.get("high") and stretch and stretch[0] <= now:   # dirty now: wait it out; dirty later: air before
            return act("Air out", f"after {clock(stretch[1])}", stretch[1])
        if stretch and stretch[0] <= now:
            return act("Open a window for 10 min", f"after {clock(stretch[1])}", stretch[1])
        if stretch and stretch[0] - now <= timedelta(hours=2):
            return act("Open a window for 10 min", f"before {clock(stretch[0])}", stretch[0])
        return act("Open a window for 10 min", "now")
    if kind == "rh":
        rh = r.get("rh")
        if rh is not None and rh > LIMITS["rh_damp"]:
            if _drier_outside(r) and not stretch:
                return act("Air the room for 10 min", "drier outside")
            if "dehumidifier" in HOUSEHOLD["equipment"]:
                return act("Run the dehumidifier", f"until under {LIMITS['rh_stop']}%")
            return act("Close the windows", f"until under {LIMITS['rh_stop']}%")
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


def needs_row(r, outlook, pollen_today, smoke, night, now):
    """Toddler, Sinus & allergy, Runner: ok True (green), False (amber) or None (no reading), a short state, and the facts
    phrases.pill_why turns into the (i) text."""
    co2, rh = r.get("co2"), r.get("rh")
    pol = (pollen_today or {}).get("index")
    stretch = _first_over(outlook, now)

    if outlook.get("high"):   # outside first: it applies even with the indoor monitor offline
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
        sin = (False, "Pollen high") if pollen_high else (None, "No reading")
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
        run = (False, "Not clean now")
    elif stretch:
        run = (False, f"Avoid {fmt_range(*stretch)}")
    else:
        # no "till 4 PM" from the rush wind or rain: in a week of replay the rush didn't raise PM2.5 at the monitor
        run = (True, "Clean air")

    def need(nid, name, v, facts):
        return {"id": nid, "name": name, "ok": v[0], "state": v[1], "facts": facts}
    return [
        need("toddler", "Toddler", tod, {"co2": co2, **({"night_peak": night["peak"]} if night and night["stale"] else {})}),
        need("sinus", "Sinus & allergy", sin, {"rh": rh, "pollen_index": pol, "pollen_type": (pollen_today or {}).get("name")}),
        need("runner", "Runner", run, {"pm_now": outlook.get("now"), "smoke": bool(smoke)}),
    ]


# ── The day chart's data, and the whole card ──
CHART_BEFORE = timedelta(hours=3.5)
CHART_SPAN = timedelta(hours=15)


def _floor_hour(t):
    return t.replace(minute=0, second=0, microsecond=0)


def _iso(t):
    return t.isoformat()


def timeline(now, co2_pts, rh_pts, pm_past, pm_fc_adj, hourly, sun, show_rh):
    """Everything the chart draws, with ISO times: measured CO₂ (and humidity when it's a damp item), PM2.5 measured
    and forecast, the 3-hourly temperature and rain row, strong-sun stretches, sunrise/sunset and night."""
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
                          "pop": pop if pop >= 30 else None, "mm": mm if pop >= 30 else None})
        t += timedelta(hours=3)
    uv, start, top = [], None, 0
    for h in sorted(hourly, key=lambda x: x["t"]):
        if not t0 <= h["t"] <= t1:
            continue
        if (h.get("uv") or 0) >= 6:
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
            "pm": {"past": win(pm_past, t0, now), "fc": [[_iso(t), round(v, 1)] for t, v in pm_fc_adj if now < t <= t1]},
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


def build_summary(r, cams, hourly, co2_pts, rh_pts, pm_past, smoke, pollen_today, pollen_tomorrow, rush, sun, now, road=None):
    """The whole card from the rules: items with actions and explanations, the Also line, the needs row, the chart.
    `road` is the road's name (None without one); `rush` its rush windows from rush_windows()."""
    cams_now = next((v for t, v in cams if _floor_hour(t) == _floor_hour(now) and v is not None), None)
    adjusted, _k = calibrate_forecast(cams, pm_past, now)
    if adjusted is None:   # not enough history to calibrate: anchor to the reading now, fading over 6 hours
        adjusted, _anchored = anchor_forecast([(t, v) for t, v in cams if t >= _floor_hour(now)], r.get("pm_now"), cams_now)
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

    wind_at = lambda t: next((h.get("wind_dir") for h in hourly if t is not None and _floor_hour(h["t"]) == _floor_hour(t)), None)
    for it in items:
        # whose need the item is: its chip on the card names that need and opens its sentence after the item's
        it["need"] = {"co2": "toddler", "rh": "sinus", "pollen": "sinus"}.get(it["id"], "toddler" if outlook.get("high") else "runner")
        it["action"] = action(it, r, outlook, rush, now)
        f = dict(it["facts"])
        when = it["action"]["when"] or ""
        if it["id"] == "co2":
            f["since"] = _since(co2_pts, LIMITS["co2"], now)
            if when.startswith("before "):   # the PM2.5 stretch ahead: with a road and rush hours, its rush fumes
                f["rush_start" if road and rush else "dirty_at"] = when[7:]
            elif when.startswith("after "):
                f["clean_at"] = when[6:]
            cold = next((h for h in sorted(hourly, key=lambda x: x["t"])
                         if now < h["t"] <= now + timedelta(hours=8) and h.get("temp") is not None and h["temp"] <= 10), None)
            if cold:
                f.update(temp_at=round(cold["temp"]), temp_time=clock(cold["t"]))
        if it["id"] == "rh":
            f["drier_out"] = _drier_outside(r)
            if f["drier_out"] and not it["action"]["text"].startswith("Air"):
                f["drier_out"] = None   # drier outside, but the air there is dirty soon: say nothing about airing
        if it["id"] == "pm":
            f.update(wind_dir=wind_at(outlook["max_at"] or now), smoke=bool(smoke))
        it["why"] = phrases.why(it["id"], f)
        it["facts"] = f

    needs = needs_row(r, outlook, pollen_today, smoke, night, now)
    for n in needs:
        n["why"] = phrases.pill_why(n["id"], n["facts"], n["ok"], n["state"])
    show_rh = any(i["id"] == "rh" and not i["facts"].get("dry") for i in items)
    tl = timeline(now, co2_pts, rh_pts, pm_past, adjusted, hourly, sun, show_rh)
    t0 = datetime.fromisoformat(tl["t0"])
    return {"label": "Tonight" if t0.hour >= 18 else "Today", "clock": clock(now), "items": items, "also": also,
            "needs": needs, "all_clear": not items, "timeline": tl}



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
