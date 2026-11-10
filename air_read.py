"""Build the page's air read, profiles, and inputs to the summary rules."""

import math
from datetime import timedelta

import sources
import summary as summary_rules
from config import bearing_in

# Startup passes server as runtime: the one owner of config, page_view, and app.

# the ones the read's outdoor_source and the summary's PM2.5 sentences use
SUMMARY_SOURCE_FACTS = ("kind", "name", "distance_km", "area_count", "fallback")
# The road card's "pressure" is these two weights multiplied: an estimate shown as text, not a measurement.
# Traffic by hour: the first rush window, the others, the hour either side of a rush, and the rest of the day.
TRAFFIC_WEIGHT = {"first_rush": 1.5, "rush": 1.4, "shoulder": 1.2, "low": 0.7}
# Wind: blowing the exhaust toward home, away from it, across, or no direction known.
WIND_WEIGHT = {"toward": 1.3, "away": 0.5, "cross": 1.0, "unknown": 1.0}
# ── Air summary (the new page) ──────────────────────────────────────────
# Rules decide every verdict and every sentence.

# RUSH_WINDOWS, PM_FINE (any hour, though WHO's 15 is a 24-hour average), PM_HIGH, CO2_OPEN, RH_LOW and RH_DAMP
# come from the config (use_config). The rest are the rules' own lines, not a household's:
CO2_VERY_HIGH = 1500   # ppm: over it, airing the room is urgent ("bad" tone), not just due ("warn")
RUN_NIGHT = (21, 5)    # hours [from, to): the run verdict speaks of tonight and the early morning
SLEEP_HOURS = (17, 7)  # hours [from, to): the toddler's line is about the air before sleep
MOISTURE_MARGIN_C = 1  # °C: outside air adds moisture when its dew point is this much above the room's


def get_wind_cardinal(degrees):
    """Convert wind direction degrees to cardinal direction."""
    if degrees is None:
        return "variable"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(degrees / 22.5) % 16]


def hourly_forecast(weather, air):
    """The next 12 hours (13 entries from the current local hour), for Coming up and the model's LATER facts:
    rain, temperature, dew point, UV, the model's outdoor PM2.5, and whether the wind carries the road's exhaust here."""
    hourly = weather.get("hourly") or {}
    times = hourly.get("time") or []
    now_key = sources.local_now().strftime("%Y-%m-%dT%H:00")
    start = next((k for k, t in enumerate(times) if t >= now_key), len(times))
    def col(name, k):
        vals = hourly.get(name) or []
        return vals[k] if k < len(vals) else None
    return [{
        "time": times[k],
        "pop": col("precipitation_probability", k),
        "precip": col("precipitation", k),
        "code": col("weather_code", k),
        "temp": col("temperature_2m", k),
        "dew": col("dew_point_2m", k),
        "wind_dir": col("wind_direction_10m", k),
        "uv": col("uv_index", k),
        "pm25": air.get(times[k]),   # the air-quality model's outdoor PM2.5 for that hour
        # whether that hour's wind carries the road's exhaust here (None without a wind direction; False without a road)
        "bqe_toward": None if col("wind_direction_10m", k) is None else
        road_traffic(int(times[k][11:13]), col("wind_direction_10m", k))["toward"],
    } for k in range(start, min(start + 13, len(times)))]


def active_road():
    """The road /api/context reports: the home's, or None. demo/data.py turns it off for a public monitor."""
    return runtime.ROAD


def road_traffic(hour, wind_direction):
    """How much the road's traffic weighs on home at this hour: its rush, and whether the wind carries its exhaust here.

    Peak inside a rush window, shoulders an hour either side. The road's `toward` arc (config) holds the wind
    directions that carry its exhaust toward home (the reference home's BQE: from about 80-200°, E through S, so the road lies
    east through south within 2 km); the opposite arc carries it away; anything else is a crosswind.
    `toward` is the flag to test; wind_impact is display text. Without a road: toward False and nothing else.
    """
    if runtime.ROAD is None:
        return {"toward": False, "traffic": None, "wind_impact": None, "pollution_pressure": None}
    hour_int = int(hour)

    # Traffic intensity by hour
    peak = next(((i, name) for i, (a, b, name) in enumerate(runtime.RUSH_WINDOWS) if a <= hour_int < b), None)
    if peak:
        traffic_intensity = f"PEAK ({peak[1]} rush)"
        multiplier = TRAFFIC_WEIGHT["first_rush"] if peak[0] == 0 else TRAFFIC_WEIGHT["rush"]
    elif any(a - 1 <= hour_int <= b for a, b, _ in runtime.RUSH_WINDOWS):
        traffic_intensity = "HIGH (rush shoulders)"
        multiplier = TRAFFIC_WEIGHT["shoulder"]
    else:
        traffic_intensity = "LOW"
        multiplier = TRAFFIC_WEIGHT["low"]

    # Wind direction impact (wind_direction is where the wind comes FROM, in degrees)
    lo, hi = runtime.ROAD.toward
    toward = wind_direction is not None and bearing_in(wind_direction, runtime.ROAD.toward)
    if wind_direction is None:
        wind_impact = "Unknown"
        wind_multiplier = WIND_WEIGHT["unknown"]
    elif toward:
        wind_impact = f"Blowing toward {runtime.CFG.place.name}"
        wind_multiplier = WIND_WEIGHT["toward"]
    elif bearing_in(wind_direction, ((lo + 180) % 360, (hi + 180) % 360)):
        wind_impact = "Blowing away"
        wind_multiplier = WIND_WEIGHT["away"]
    else:
        wind_impact = "Crosswind"
        wind_multiplier = WIND_WEIGHT["cross"]

    pollution_pressure = multiplier * wind_multiplier

    return {
        "toward": toward,
        "traffic": traffic_intensity,
        "wind_impact": wind_impact,
        "pollution_pressure": round(pollution_pressure, 1)
    }


def fmt_num(value, digits=1):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}" if digits else f"{round(value)}"


def fmt_hour(hour):
    hour %= 24
    return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"


def dew_point_c(temp_c, rh):
    if temp_c is None or rh is None or rh <= 0:
        return None
    a, b = 17.62, 243.12
    g = math.log(rh / 100) + a * temp_c / (b + temp_c)
    return b * g / (a - g)


def rush_hours():
    """The rush windows of the road in use (active_road()): the home's, or none without a road (a public monitor)."""
    return runtime.RUSH_WINDOWS if active_road() else []


def rush_state(hour):
    windows = rush_hours()
    if not windows:   # no road
        return {"in_rush": False, "name": None, "start": None, "end": None, "tomorrow": True}
    for start, end, name in windows:
        if start <= hour < end:
            return {"in_rush": True, "name": name, "start": start, "end": end}
    later = [w for w in windows if w[0] > hour]
    start, end, name = later[0] if later else windows[0]
    return {"in_rush": False, "name": name, "start": start, "end": end, "tomorrow": not later}


def verdict(word, tone, text, action=None):
    """action is the short imperative used in the lead when this verdict needs doing."""
    return {"word": word, "tone": tone, "text": text, "action": action}


def rule_run(outdoor_pm, smoke, rush, wind_toward, hour):
    if outdoor_pm is None:
        return verdict("No reading", "muted", "The outdoor monitor has not reported, so there is no run answer.")
    pm = fmt_num(outdoor_pm)
    if outdoor_pm > runtime.PM_HIGH:
        return verdict("Skip it", "bad", f"Outdoor PM2.5 is {pm} µg/m³, over {runtime.PM_HIGH}. Skip the run, and keep the toddler in.")
    if outdoor_pm > runtime.PM_FINE or smoke:
        why = f"Outdoor PM2.5 is {pm} µg/m³, over {runtime.PM_FINE}" if outdoor_pm > runtime.PM_FINE else "NOAA reports wildfire smoke over the region"
        return verdict("Keep it short", "warn", f"{why}. Keep a run short and easy.")
    base = f"Outdoor PM2.5 is {pm} µg/m³, under {runtime.PM_FINE}."
    if rush["in_rush"] and wind_toward:
        return verdict(f"After {fmt_hour(rush['end'])}", "warn",
                       f"{base} The {runtime.ROAD.name} {rush['name']} rush runs until {fmt_hour(rush['end'])} with the wind toward {runtime.CFG.place.name}, so run after that.")
    if hour >= RUN_NIGHT[0] or hour < RUN_NIGHT[1]:
        windows = rush_hours()
        return verdict("Fine", "good", f"{base} Tonight is fine, and so is the morning before the {fmt_hour(windows[0][0])} rush."
                       if windows else f"{base} Tonight is fine.")
    if not rush["in_rush"] and not rush.get("tomorrow") and wind_toward:
        return verdict(f"Fine until {fmt_hour(rush['start'])}", "good",
                       f"{base} Fine for a run, and for the toddler outside, until {fmt_hour(rush['start'])}. Then the {runtime.ROAD.name} rush starts, with the wind toward {runtime.CFG.place.name}.")
    return verdict("Fine", "good", f"{base} Fine for a run, and for the toddler outside.")


def clock_label(ts, now_local):
    label = ts.strftime("%-I:%M %p")
    return label if ts.date() == now_local.date() else label + " yesterday"


def stretch(points, key, is_off, now_local, hours=24):
    """The unbroken stretch where is_off holds, running up to the latest reading: {"label": "all day" or "since 3:10 PM"}."""
    vals = [(t, key(r)) for t, r in points]
    vals = [(t, v) for t, v in vals if v is not None]
    if not vals or not is_off(vals[-1][1]):
        return None
    i = len(vals) - 1
    while i > 0 and is_off(vals[i - 1][1]):
        i -= 1
    start = vals[i][0]
    whole = i == 0 and (start - (now_local - timedelta(hours=hours))).total_seconds() < 3600
    return {"label": "all day" if whole else "since " + clock_label(start, now_local)}


def co2_of(r):
    return sources.fnum(r.get("rco2_corrected", r.get("rco2")))


def rh_in_of(r):
    return sources.fnum(r.get("rhum", r.get("rhum_corrected")))


def build_profiles(co2, rh, pm_out, adds_moisture, pollen, top_pollen, actions, run_item, co2_run, now):
    """One line per profile, in the header pill's order: Toddler, Sinus & allergy, Runner.
    Each profile is paired with the card that holds its evidence (metric)."""
    keyed = {a["key"]: a for a in actions}
    evening = now.hour >= SLEEP_HOURS[0] or now.hour < SLEEP_HOURS[1]

    # Toddler: the indoor air (CO2), unless the outside air keeps them in.
    if pm_out is not None and pm_out > runtime.PM_HIGH:
        tod = ("bad", "Keep the toddler inside", f"Outdoor PM2.5 is {fmt_num(pm_out)}, over {runtime.PM_HIGH}.")
    elif co2 is not None and co2 > runtime.CO2_OPEN:
        since = co2_run["label"] if co2_run else ""
        tod = ("bad" if co2 > CO2_VERY_HIGH else "warn", "Open a window before sleep" if evening else "Air the room",
               f"CO₂ has been over {runtime.CO2_OPEN} {since}." if since and since != "all day" else f"CO₂ is {co2:.0f} ppm, over {runtime.CO2_OPEN}.")
    elif co2 is not None:
        tod = ("good", "Fresh air for sleep" if evening else "Fresh air indoors", f"CO₂ is {co2:.0f} ppm, under {runtime.CO2_OPEN}.")
    else:
        tod = ("muted", "No indoor reading", "The indoor monitor has not reported.")

    # Sinus & allergy: humidity first, then pollen.
    pol = (top_pollen.get("index") or 0) if top_pollen else None
    if "humidity" in keyed:
        a = keyed["humidity"]
        sin = ("warn", a["text"], a["why"])
    elif "pollen" in keyed:
        sin = ("warn", "Limit time outside", keyed["pollen"]["why"])
    elif rh is not None:
        sin = ("good", "Nothing to do", f"Humidity is {rh:.0f}%" + (f" and pollen is {pol} of 5." if pol is not None else "."))
    else:
        sin = ("muted", "No indoor reading", "The indoor monitor has not reported humidity.")

    # Runner: the run verdict from the rules.
    run = keyed.get("run") or run_item
    rn = (run["tone"], run["text"], run["why"]) if run else ("muted", "No outdoor reading", "The outdoor monitor has not reported.")

    def profile(pid, name, metric, v):
        return {"id": pid, "name": name, "metric": metric, "tone": v[0], "action": v[1], "why": v[2]}
    out = [profile("toddler", "Toddler", "co2", tod), profile("sinus", "Sinus & allergy", "humidity", sin), profile("runner", "Runner", "pm", rn)]
    out[1]["pollen"] = [{"name": q.get("name"), "index": q.get("index") or 0, "in_season": bool(q.get("in_season"))} for q in (pollen or [])]
    return out


def summary_inputs(payload, co2, rh, rh_out, t_in, t_out, pm_out, pts_in, pts_out, now, source=None):
    """Gather what summary.build_summary needs from the caches the page already fills. Without an own outdoor
    monitor's history (a public monitor's page, or an indoor-only home: `source`, outdoor_source's), the chart's past
    PM2.5 is the model's; an area source's ratio to the model scales it (area_factor)."""
    tz = now.tzinfo
    weather = sources.get_open_meteo_data()
    hw, daily = weather.get("hourly") or {}, weather.get("daily") or {}
    col = lambda name, k: (hw.get(name) or [None] * (k + 1))[k] if k < len(hw.get(name) or []) else None
    hourly = [{"t": sources._local(t, tz), "temp": col("temperature_2m", k), "dew": col("dew_point_2m", k),
               "pop": col("precipitation_probability", k),
               "mm": col("precipitation", k), "uv": col("uv_index", k), "wind_dir": col("wind_direction_10m", k)}
              for k, t in enumerate(hw.get("time") or [])]
    cams = sources.model_hours(now)
    pm_past = [(t, sources.pm_of(x)) for t, x in pts_out]
    model_past = [(t, v) for t, v in cams if t <= now and v is not None]
    # no own outdoor history: a public monitor (outdoor_row) or an indoor-only home (source). A home whose own outdoor
    # monitor's history is missing (AirGradient failed) keeps an empty past
    no_own_outdoor = outdoor_row() is not None or source is not None
    pm_past_model = no_own_outdoor and not pm_past and bool(model_past)
    if pm_past_model:
        pm_past = model_past
    road = active_road()
    sun = [{"t": sources._local(t, tz), "kind": kind} for key, kind in (("sunrise", "Sunrise"), ("sunset", "Sunset"))
           for t in daily.get(key) or [] if t]
    days = sources.get_pollen_days() if sources.pollen_live() else {"today": [], "tomorrow": []}
    top = lambda types: max(types, key=lambda q: q.get("index") or 0) if types else None
    return {"r": {"co2": co2, "rh": rh, "rh_out": rh_out, "t_in": t_in, "t_out": t_out, "pm_now": pm_out},
            "cams": cams, "hourly": hourly,
            "co2_pts": [(t, co2_of(x)) for t, x in pts_in], "rh_pts": [(t, rh_in_of(x)) for t, x in pts_in],
            "pm_past": pm_past, "smoke": sources.get_smoke_data() if sources.source_on("smoke") else False,
            "pollen_today": top(days.get("today")), "pollen_tomorrow": top(days.get("tomorrow")),
            "rush": rush_windows(hourly, now), "road": road.name if road else None, "sun": sun, "now": now,
            # whose reading the PM2.5 forecast is fitted to, in its sentence: a public monitor's page says "this monitor";
            # a home's own outdoor monitor is phrases.py's default, and a home without one names its source
            **({"monitor_label": "this monitor"} if outdoor_row() is not None else {}),
            **({"source": {k: source[k] for k in SUMMARY_SOURCE_FACTS}} if source else {}),
            **({} if indoor_monitor() else {"indoor": False}),
            **({"pm_past_model": True} if pm_past_model else {}),
            **({"area_factor": source["area_factor"]} if source and source.get("area_factor") is not None else {})}


def rush_windows(hourly, now):
    """Today's and tomorrow's rush windows of the road, each with whether the forecast wind blows its exhaust here."""
    road = active_road()
    return summary_rules.rush_windows(hourly, now, rush_hours(), road.toward) if road else []


def profiles_on(profiles):
    """Only the profiles the page's view turns on: the home's config, or a public monitor's (runner only, demo/public.py)."""
    on = runtime.page_view().get("profiles") or {}
    return [n for n in profiles if on.get(n["id"], True)]


def indoor_monitor():
    """Whether the home has an indoor monitor: an outdoor-only home's summary reads nothing indoors and its toddler
    profile waits for one. A seam demo/data.py can replace."""
    return runtime.CFG is None or runtime.CFG.place is None or runtime.CFG.place.indoor is not None


def outdoor_row():
    """The outdoor monitor's latest row as AirGradient lists it (timestamp, offline), when the server holds it: None
    for a home, whose page posts its reading. demo/data.py gives a public monitor's."""
    return None


def safe_summary(inputs):
    """The new card, or None (logged) if the rules fail on odd data: the page then keeps its previous card."""
    try:
        s = summary_rules.build_summary(**inputs)
        s["profiles"] = profiles_on(s["profiles"])
        return s
    except Exception as e:  # never let the card take the whole read down
        runtime.app.logger.warning("summary failed: %s: %s", type(e).__name__, e)
        return None


def build_air_read(payload):
    now = sources.local_now()
    if not indoor_monitor():   # an outdoor-only home: nothing the page posts for an indoor monitor counts
        payload = {**payload, "indoor_co2": None, "indoor_humidity": None, "indoor_temp_c": None, "indoor_pm25": None,
                   "indoor_location_id": None}
    co2 = sources.fnum(payload.get("indoor_co2"))
    rh = sources.fnum(payload.get("indoor_humidity"))
    t_in = sources.fnum(payload.get("indoor_temp_c"))
    pm_out = sources.fnum(payload.get("outdoor_pm25"))
    rh_out = sources.fnum(payload.get("outdoor_humidity"))
    t_out = sources.fnum(payload.get("outdoor_temp_c"))
    if not sources.outdoor_current(outdoor_row(), now):   # offline or stale: the model speaks for PM2.5 now, not an old reading
        pm_out = rh_out = t_out = None

    weather = sources.get_open_meteo_data().get("current", {})
    source = sources.outdoor_source(now)   # None with an own outdoor monitor
    if source is not None:   # indoor-only: the server's source, not what the page posted for its outdoor entry
        row = source["row"] or {}
        pm_out = sources.pm_of(row) if row else None   # a public monitor's reading; an estimate has no "now" of its own
        # a public monitor's own temperature and humidity; else Open-Meteo's (the damp and dry rules keep working)
        rh_out = sources.fnum(row.get("rhum")) if row else sources.fnum(weather.get("relative_humidity_2m"))
        # the world list gives atmp as measured, with no compensated temperature (checked 2026-11-09): kept as it is
        t_out = sources.fnum(row.get("atmp")) if row else sources.fnum(weather.get("temperature_2m"))
    wind_direction = weather.get("wind_direction_10m")
    wind_toward = road_traffic(now.hour, wind_direction)["toward"]
    smoke = sources.get_smoke_data() if sources.source_on("smoke") else False
    pollen = sources.get_pollen_data(runtime.HOME_LAT, runtime.HOME_LON) if sources.pollen_live() else []
    rush = rush_state(now.hour)

    in_dp, out_dp = dew_point_c(t_in, rh), dew_point_c(t_out, rh_out)
    if out_dp is None:
        out_dp = sources.fnum(weather.get("dew_point_2m"))
    adds_moisture = in_dp is not None and out_dp is not None and out_dp - in_dp > MOISTURE_MARGIN_C
    pts_in = sources.history_points(payload.get("indoor_location_id"), now)
    if source is None:
        pts_out = sources.history_points(payload.get("outdoor_location_id"), now)
    else:   # a public monitor's history calibrates the forecast exactly as an own monitor's; an estimate has none
        pts_out = sources._row_points(source["history"], now) if source["kind"] == "monitor" else []

    co2_run = stretch(pts_in, co2_of, lambda v: v > runtime.CO2_OPEN, now)

    # ── Actions, ranked by the rules ──
    actions = []  # each: {"key", "text", "why", "tone"}
    if co2 is not None and co2 > runtime.CO2_OPEN:
        since = co2_run["label"] if co2_run else ""
        if pm_out is not None and pm_out > runtime.PM_HIGH:
            actions.append({"key": "window", "tone": "warn", "text": "Keep windows shut for now",
                            "why": f"CO₂ is {co2:.0f}, but the air outside is not clean ({fmt_num(pm_out)})."})
        else:
            short = adds_moisture and rh is not None and rh > runtime.RH_DAMP
            actions.append({"key": "window", "tone": "bad" if co2 > CO2_VERY_HIGH else "warn",
                            "text": "Open a window for a few minutes" if short else "Open a window",
                            "why": f"CO₂ has been over the {runtime.CO2_OPEN} limit {since}." if since and since != "all day"
                                   else f"CO₂ is {co2:.0f}, over the {runtime.CO2_OPEN} limit."})
    if rh is not None and rh > runtime.RH_DAMP:
        window_too = any(a["key"] == "window" for a in actions)
        actions.append({"key": "humidity", "tone": "warn",
                        "text": "Air the room briefly, then dry it" if window_too and adds_moisture else "Dry the indoor air",
                        "why": f"The room is too damp ({rh:.0f}%)" + (", and the air outside holds more water." if adds_moisture else ".")})
    elif rh is not None and rh < runtime.RH_LOW:
        actions.append({"key": "humidity", "tone": "warn", "text": "Add moisture to the air",
                        "why": f"The air is dry ({rh:.0f}%), which irritates sinuses."})
    run_v = rule_run(pm_out, smoke, rush, wind_toward, now.hour)
    run_item = None
    w = run_v["word"]
    if w == "Skip it":
        actions.append({"key": "run", "tone": "bad", "text": "Skip the run", "why": f"Outdoor PM2.5 is {fmt_num(pm_out)}, over {runtime.PM_HIGH}."})
    elif w == "Keep it short":
        actions.append({"key": "run", "tone": "warn", "text": "Keep a run short and easy", "why": run_v["text"].split(". ")[0] + "."})
    elif w.startswith("After"):
        actions.append({"key": "run", "tone": "warn", "text": "Run " + w.lower(), "why": f"The {runtime.ROAD.name} rush runs until {w[6:]}, with the wind toward {runtime.CFG.place.name}."})
    elif w.startswith("Fine until"):
        run_item = {"key": "run", "tone": "good", "text": "Run before " + w[11:], "why": f"The air outside is clean; the {w[11:]} rush blows this way."}
    elif w == "Fine":
        night = now.hour >= RUN_NIGHT[0] or now.hour < RUN_NIGHT[1]
        windows = rush_hours()
        run_item = {"key": "run", "tone": "good", "text": f"Run tonight or before {fmt_hour(windows[0][0])}" if night and windows else "Fine to run",
                    "why": "The air outside is clean" + (f"; the {fmt_hour(windows[0][0])} rush blows this way." if night and wind_toward and windows else ".")}
    top_pollen = max(pollen, key=lambda q: q.get("index") or 0) if pollen else None
    if top_pollen and (top_pollen.get("index") or 0) >= runtime.LIMITS["pollen"]:
        actions.append({"key": "pollen", "tone": "warn", "text": "Limit time outside", "why": f"{top_pollen['name']} pollen is {top_pollen['index']} of 5."})
    profiles = profiles_on(build_profiles(co2, rh, pm_out, adds_moisture, pollen, top_pollen, actions, run_item, co2_run, now))
    order = {"window": 0, "humidity": 1, "run": 2, "pollen": 3}
    actions.sort(key=lambda a: ({"bad": 0, "warn": 1}.get(a["tone"], 2), order[a["key"]]))

    if actions:
        head, also = actions[0], actions[1:] + ([run_item] if run_item else [])
        tone, why = head["tone"], head["why"]
    else:
        also, tone = [], "good"
        if run_item and run_item["text"].startswith("Run before"):
            why = f"The air outside is clean, and the {runtime.ROAD.name} {rush['name']} rush starts at {fmt_hour(rush['start'])}."
        elif run_item:
            why = run_item["why"]
        else:
            why = "Every reading is inside its limit."

    result = {
        "generated_at": now.isoformat(), "clock": now.strftime("%-I:%M %p"), "status": tone, "why": why,
        "also": [{"text": a["text"], "why": a["why"], "tone": a["tone"]} for a in also],
        "profiles": profiles,
    }
    # the new card: items, profiles and the day chart, all from the rules (summary.py)
    summary_in = summary_inputs(payload, co2, rh, rh_out, t_in, t_out, pm_out, pts_in, pts_out, now, source)
    result["summary"] = safe_summary(summary_in)
    if source is not None:   # the facts the explanations name the source with (phrases.py and the page word them)
        result["outdoor_source"] = {k: source[k] for k in SUMMARY_SOURCE_FACTS}

    return result
