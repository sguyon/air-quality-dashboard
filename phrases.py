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
# in ppm (the global average is about 420), the floor a short airing brings a room toward.
LIMIT_FACTS = {"co2_limit": _L["co2"], "co2_outdoor": 420, "rh_damp": _L["rh_damp"], "rh_dry": _L["rh_dry"],
               "rh_stop": _L["rh_stop"], "pm_limit": _L["pm"], "pm_high": _L["pm_high"], "indoor": "home", "outdoor": "outdoor"}

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
        "timing": ["{ac_too_on}The AC’s dry mode works too. Stop at {rh_stop}%.",
                   "{appliance_on}Stop at {rh_stop}%."],
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
        "timing": ["The forecast comes from the Copernicus model via Open-Meteo, adjusted to your {outdoor} monitor."],
    },
    "pollen": {
        "effect": ["{pollen_type_cap} pollen sets off sneezing and a stuffy nose for allergic sinuses."],
        "now": ["Today it’s {pollen_index} of 5."],
        "timing": ["Keep the windows shut and shower after time outside."],
    },
}

# the needs: one short sentence per need, shown when its icon or an item's need is tapped. A key is the state
# (checked first) or ok True/False/None; a value is a template or a list of them, the first that fills is used.
PILLS = {
    "toddler": {"Stale indoors": ["Stale air can make sleep lighter. Last night it stayed over {co2_limit}, peaking at {night_peak_s}, so air before bed too.",
                                  "Stale air can make sleep lighter: air the {indoor} before the next nap."],
                "Stale last night": "CO₂ stayed over {co2_limit} most of last night, peaking at {night_peak_s}. Air the {indoor} before bed, or leave a window open a crack.",
                "Dirty outside": "PM2.5 outside is over {pm_high}: keep the toddler inside, windows shut.",
                True: "CO₂ is under {co2_limit}: fresh air helps a toddler sleep deeper.",
                False: "Stale or dirty air: CO₂ over {co2_limit}, or the air outside is too dirty to go out.",
                None: "The indoor monitor hasn’t reported."},
    "sinus": {"Too damp": "Humidity is over {rh_damp}%: mold and dust mites like it, and both set off allergies.",
              "Too dry": "Humidity is under {rh_dry}%: dry air irritates the nose and sinuses.",
              "Pollen high": ["{pollen_type_cap} pollen is {pollen_index} of 5 today: keep the windows shut.", "Pollen is high today: keep the windows shut."],
              "Damp + pollen": ["{dehumidifier_on}Damp inside and pollen outside: dehumidify with the windows shut.",
                                "{ac_dry_on}Damp inside and pollen outside: run the AC’s dry mode with the windows shut.",
                                "Damp inside and pollen outside: keep the windows shut."],
              "All fine": "Humidity is between {rh_dry} and {rh_damp}%.",   # no pollen reading: nothing to say about it
              True: "Humidity is between {rh_dry} and {rh_damp}%, and pollen is low.",
              False: "Damp air, dry air or pollen: the item above says which and what to do.",
              None: "The indoor monitor hasn’t reported."},
    "runner": {"Avoid": "PM2.5 outside is forecast over {pm_limit} in those hours: run before or after.",
               "Run after": "PM2.5 outside is over {pm_limit} until then.",
               "Skip today": "PM2.5 outside is over {pm_high} today: skip the run.",
               True: "Outdoor PM2.5 is under {pm_limit}.",
               False: "Outdoor PM2.5 is over {pm_limit} then.",
               None: "The outdoor monitor hasn’t reported."},
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
    # the home's appliances (summary.build_summary): the AC as a second option, and "stop at" for whatever runs
    if f.get("ac_too"):
        f["ac_too_on"] = ""
    if f.get("appliance"):
        f["appliance_on"] = ""
    for a in ("dehumidifier", "ac_dry"):   # which one the home has, for the damp + pollen pill
        if f.get(a):
            f[a + "_on"] = ""
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


def pill_why(need_id, facts, ok, state=None):
    """One sentence for a tapped need: the state's own template if it has one, else the ok/not ok one."""
    if need_id == "runner" and ok and facts.get("smoke"):
        s = fill(SMOKE_CLEAN, facts)
        if s:
            return s
    key = next((k for k in ("Avoid", "Run after") if state and state.startswith(k)), state)   # "Avoid 4–8 PM", "Run after 11 AM": the hours change
    tpl = PILLS[need_id].get(key) or PILLS[need_id][ok]
    for t in [tpl] if isinstance(tpl, str) else tpl:
        s = fill(t, facts)
        if s:
            return s
    return ""
