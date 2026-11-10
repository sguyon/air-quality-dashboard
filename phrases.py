"""The sentence library behind each (i) on the summary card. Written by hand, no model.

Each item's explanation is up to three sentences, one per part:
  effect: what the reading does to people (fixed knowledge)
  now:    why it's happening now (facts from the readings and forecasts)
  timing: why this time (from the action's time)
For each part, the first template whose {slots} are all in the facts is used; a part with none that fits is
skipped, so no sentence ever prints an empty slot. Every number comes from the facts or from the limits below.
"""
import re

from config import DEFAULT_LIMITS as _L

# the server fills the limits and the monitor labels from the config at import. co2_outdoor is the usual outdoor CO₂
# in ppm (the global average is about 420), the floor a short airing brings a room toward. PLACE_DEFAULTS: the monitor
# labels when the config names none (the server puts them back before each config, so a dropped monitor's name goes).
PLACE_DEFAULTS = {"indoor": "home", "outdoor": "outdoor"}
LIMIT_FACTS = {"co2_limit": _L["co2"], "co2_outdoor": 420, "rh_damp": _L["rh_damp"], "rh_dry": _L["rh_dry"],
               "rh_stop": _L["rh_stop"], "pm_limit": _L["pm"], "pm_high": _L["pm_high"], **PLACE_DEFAULTS}

# each item's (i): its effect, now and timing sentences, as described at the top
LIBRARY = {
    "co2": {
        "effect": ["Above {co2_limit} the air feels stale, and focus and sleep can suffer."],
        "now": ["It’s been over {co2_limit} since {since}.",
                "Outdoor air is about {co2_outdoor}, so a short airing brings it down."],
        "timing": ["Do it before {rush_start}, when the rush fumes arrive.",
                   "Do it before {dirty_at}, when the air outside gets dirtier.",
                   "Wait until {clean_at}, when the air outside is clean again.",
                   "Close it after ten minutes: it’s {temp_at}° by {temp_time}."],
    },
    "rh_damp": {
        "effect": ["Above {rh_damp}%, mold and dust mites grow, which is hard on sinuses."],
        "now": ["{drier_on}The air outside is drier, so ten minutes of airing helps.",
                "{wetter_on}Outside is wetter ({rh_out}%), so a window won’t dry the room."],
        "timing": ["Outside gets drier at {dry_at}, so ten minutes of airing helps.",
                   "{ac_too_on}The AC’s dry mode works too. Stop at {rh_stop}%.",
                   "{appliance_on}Stop at {rh_stop}%.",
                   "{no_appliance_on}Run the bathroom or kitchen fan after showers and cooking, and dry laundry outside the room."],
    },
    "rh_dry": {
        "effect": ["Under {rh_dry}%, dry air irritates the nose and throat."],
        "now": ["{drier_on}Outside is drier still ({rh_out}%), so airing makes it worse."],
        "timing": [],
    },
    "pm": {
        "effect": ["Fine particles reach deep into the lungs. The line is {pm_limit}, WHO’s guideline for a 24-hour average, used here for any hour."],
        "now": ["The {rush_wind} wind carries {road} rush-hour fumes onto the block.",
                "{smoke_on}NOAA reports wildfire smoke over the region.",
                "The forecast peaks at {pm} around {peak_at}, from {pm_now} now."],
        # how the forecast was fitted to the monitor (summary.build_summary): scaled by a day of its readings, or started
        # from its reading now; with neither (no reading, no model hour for now) it's the raw model and says nothing here.
        # A home without an outdoor monitor names its source instead (server.outdoor_source): a nearby public monitor,
        # the area's public monitors, or the model alone; {fallback_lead} says why the chosen monitor's reading isn't used
        "timing": ["{calibrated_on}The forecast is Open-Meteo’s prediction for the wider area, scaled to what {monitor_label} measured over the last day.",
                   "{anchored_on}The forecast is Open-Meteo’s prediction for the wider area, started from {monitor_label}’s reading now.",
                   "{public_calibrated_on}The forecast is Open-Meteo’s prediction for the wider area, scaled to what the public monitor at {source_name}, {source_km} km away, measured over the last day.",
                   "{public_calibrated_on}The forecast is Open-Meteo’s prediction for the wider area, scaled to what {source_label} measured over the last day.",
                   "{public_anchored_on}The forecast is Open-Meteo’s prediction for the wider area, started from what the public monitor at {source_name}, {source_km} km away, reads now.",
                   "{public_anchored_on}The forecast is Open-Meteo’s prediction for the wider area, started from what {source_label} reads now.",
                   "{area_on}{fallback_lead}The forecast is Open-Meteo’s prediction for the wider area, scaled to what {area_count} public monitors near you measured over the last day.",
                   "{model_on}{fallback_lead}The forecast is Open-Meteo’s prediction for the wider area: an estimate, with no monitor outside to check it against."],
    },
    "pollen": {
        "effect": ["{pollen_type_cap} pollen sets off sneezing and a stuffy nose for allergic sinuses."],
        "now": ["Today it’s {pollen_index} of 5."],
        "timing": ["Keep the windows shut and shower after time outside."],
    },
}

# the profiles: one short sentence per profile, shown when its icon or an item's profile is tapped. A key is the state
# (checked first) or ok True/False/None; a value is a template or a list of them, the first that fills is used.
PILLS = {
    "toddler": {"Stale indoors": ["Stale air can make sleep lighter. Last night it stayed over {co2_limit}, peaking at {night_peak_s}, so air before bed too.",
                                  "Stale air can make sleep lighter: air the {indoor} before the next nap."],
                "Stale last night": "CO₂ stayed over {co2_limit} most of last night, peaking at {night_peak_s}. Air the {indoor} before bed, or leave a window open a crack.",
                "Dirty outside": "PM2.5 outside is over {pm_high}: keep the toddler inside, windows shut.",
                "Needs an indoor monitor": "A toddler sleeps deeper when CO₂ indoors stays low, and only an indoor monitor measures it.",
                True: "CO₂ is under {co2_limit}: fresh air helps a toddler sleep deeper.",
                False: "Stale or dirty air: CO₂ over {co2_limit}, or the air outside is too dirty to go out.",
                None: "The indoor monitor hasn’t reported."},
    "sinus": {"Too damp": "Humidity is over {rh_damp}%: mold and dust mites like it, and both set off allergies.",
              "Too dry": "Humidity is under {rh_dry}%: dry air irritates the nose and sinuses.",
              # {no_indoor_on}: a home without an indoor monitor, so pollen only
              "Pollen high": ["{no_indoor_on}{pollen_type_cap} pollen is {pollen_index} of 5 today: keep the windows shut (pollen only: no indoor monitor for humidity).",
                              "{no_indoor_on}Pollen is high today: keep the windows shut (pollen only: no indoor monitor for humidity).",
                              "{pollen_type_cap} pollen is {pollen_index} of 5 today: keep the windows shut.", "Pollen is high today: keep the windows shut."],
              "Damp + pollen": ["{dehumidifier_on}Damp inside and pollen outside: dehumidify with the windows shut.",
                                "{ac_dry_on}Damp inside and pollen outside: run the AC’s dry mode with the windows shut.",
                                "Damp inside and pollen outside: keep the windows shut."],
              "All fine": "Humidity is between {rh_dry} and {rh_damp}%.",   # no pollen reading: nothing to say about it
              True: ["{no_indoor_on}Pollen is low today (pollen only: no indoor monitor for humidity).",
                     "Humidity is between {rh_dry} and {rh_damp}%, and pollen is low."],
              False: "Damp air, dry air or pollen: the item above says which and what to do.",
              None: ["{no_indoor_on}No pollen reading yet (pollen only: no indoor monitor for humidity).",
                     "The indoor monitor hasn’t reported."]},
    "runner": {"Avoid": "PM2.5 outside is forecast over {pm_limit} in those hours: run before or after.",
               "Run after": "PM2.5 outside is over {pm_limit} until then.",
               "Skip today": "PM2.5 outside is over {pm_high} today: skip the run.",
               True: "Outdoor PM2.5 is under {pm_limit}.",
               False: "Outdoor PM2.5 is over {pm_limit} then.",
               None: ["{source_on}Outdoor PM2.5 isn’t available right now.", "The outdoor monitor hasn’t reported."]},
}
# the runner's (i) when NOAA sees smoke but the outdoor monitor reads clean air
SMOKE_CLEAN = "NOAA reports smoke in the region; the air here is clean (PM2.5 {pm_now})."

# compass(): the wind's direction in eight words, from north clockwise
_POINTS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]


def compass(deg):
    """The direction a wind comes from, in one of 8 words."""
    return _POINTS[round((deg % 360) / 45) % 8]


def _derived(facts):
    f = {**LIMIT_FACTS, **{k: v for k, v in facts.items() if v is not None}}
    cause = str(f.get("cause") or "")
    if cause.endswith(" rush") and f.get("wind_dir") is not None:   # "<road> rush", from summary.build_summary
        f["road"] = cause[:-len(" rush")]
        f["rush_wind"] = compass(f["wind_dir"])
    if f.get("smoke"):
        f["smoke_on"] = ""
    # the PM2.5 forecast's fit, "calibrated", "anchored" or "area" (summary.build_summary), and whose readings it was
    # fitted to: the home's outdoor monitor unless the caller names another ("this monitor" for a public monitor's page),
    # or for a home without one, its source (source_kind "monitor", "area" or "model", from server.outdoor_source)
    fit, kind = f.get("forecast_fit"), f.get("source_kind")
    if kind is None:
        if fit in ("calibrated", "anchored"):
            f[fit + "_on"] = ""
        f.setdefault("monitor_label", f"your {f['outdoor']} monitor")
    else:
        f["source_on"] = ""
        if kind == "monitor" and fit in ("calibrated", "anchored"):
            f["public_" + fit + "_on"] = ""
        elif kind == "area" and fit == "area":
            f["area_on"] = ""
        elif kind == "model":
            f["model_on"] = ""
        if f.get("source_km") is not None:
            f["source_km"] = f"{f['source_km']:g}"   # 1.1, and 2 rather than 2.0
        # a public monitor whose name isn't known (gone from AirGradient's list since the server started): no name
        f["source_label"] = f"the public monitor at {f['source_name']}" if f.get("source_name") else "the public monitor you chose"
        # why the chosen monitor's reading isn't used: AirGradient's list didn't answer ("list": it may be reporting,
        # so it isn't blamed), or the monitor isn't reporting ("monitor", or True)
        f["fallback_lead"] = ""
        if f.get("source_fallback") == "list":
            f["fallback_lead"] = "AirGradient didn’t answer, so this is an estimate for your area. "
        elif f.get("source_fallback"):
            who = f.get("source_name") or "The public monitor you chose"
            f["fallback_lead"] = f"{who} isn’t reporting, so this is an estimate for your area. "
    # the home's appliances (summary.build_summary): the AC as a second option, and "stop at" for whatever runs
    if f.get("ac_too"):
        f["ac_too_on"] = ""
    if f.get("appliance"):
        f["appliance_on"] = ""
    if f.get("no_appliance"):
        f["no_appliance_on"] = ""
    for a in ("dehumidifier", "ac_dry"):   # which one the home has, for the damp + pollen pill
        if f.get(a):
            f[a + "_on"] = ""
    if f.get("no_indoor"):   # an outdoor-only home (summary.build_summary): the sinus pill says it's pollen only
        f["no_indoor_on"] = ""
    # the dew point decides whether outside air is drier (set by the rules); without it, say nothing
    if f.get("drier_out") is True:
        f["drier_on"] = ""
    elif f.get("drier_out") is False and "rh_out" in f:
        f["wetter_on"] = ""
    if f.get("night_peak") is not None:
        f["night_peak_s"] = f"{f['night_peak']:,}"
    if f.get("pollen_type"):
        f["pollen_type_cap"] = str(f["pollen_type"]).capitalize()
    return f


def fill(template, facts):
    """The template with its slots filled, or None when a slot has no fact."""
    f = _derived(facts)
    slots = re.findall(r"{(\w+)}", template)
    if any(s not in f for s in slots):
        return None
    return template.format(**{s: f[s] for s in slots})


def why(item_id, facts):
    """Two or three sentences for an item's (i)."""
    key = item_id
    if item_id == "rh":
        key = "rh_dry" if facts.get("dry") else "rh_damp"
    parts = LIBRARY[key]
    out = []
    for kind in ("effect", "now", "timing"):
        for t in parts.get(kind, []):
            s = fill(t, facts)
            if s:
                out.append(s)
                break
    return " ".join(out)


def pill_why(profile_id, facts, ok, state=None):
    """One sentence for a tapped profile: the state's own template if it has one, else the ok/not ok one."""
    if profile_id == "runner" and ok and facts.get("smoke"):
        s = fill(SMOKE_CLEAN, facts)
        if s:
            return s
    key = next((k for k in ("Avoid", "Run after") if state and state.startswith(k)), state)   # "Avoid 4–8 PM", "Run after 11 AM": the hours change
    tpl = PILLS[profile_id].get(key) or PILLS[profile_id][ok]
    for t in [tpl] if isinstance(tpl, str) else tpl:
        s = fill(t, facts)
        if s:
            return s
    return ""
