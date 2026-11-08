"""The sentence library behind each (i) on the summary card. Written once, reviewed by Sacha, no model.

Each item's explanation is up to three sentences, one per part:
  effect: what the reading does to people (fixed knowledge)
  now:    why it's happening now (facts from the readings and forecasts)
  timing: why this time (from the action's time)
For each part, the first template whose {slots} are all in the facts is used; a part with none that fits is
skipped, so no sentence ever prints an empty slot. Every number comes from the facts or from the limits below.
"""
import re

LIMIT_FACTS = {"co2_limit": 800, "co2_outdoor": 420, "rh_damp": 60, "rh_dry": 30, "rh_stop": 55, "pm_limit": 15, "pm_high": 35}

LIBRARY = {
    "co2": {
        "effect": ["Above {co2_limit} the air feels stale, and focus and sleep can suffer."],
        "now": ["It’s been over {co2_limit} since {since}.",
                "Outdoor air is about {co2_outdoor}, so a short airing brings it down."],
        "timing": ["Do it before {rush_start}, when the rush fumes arrive.",
                   "Wait until {clean_at}, when the air outside is clean again.",
                   "Close it after ten minutes: it’s {temp_at}° by {temp_time}."],
    },
    "rh_damp": {
        "effect": ["Above {rh_damp}%, mold and dust mites grow, which is hard on sinuses."],
        "now": ["{drier_on}The air outside is drier, so ten minutes of airing helps.",
                "{wetter_on}Outside is wetter ({rh_out}%), so a window won’t dry the room."],
        "timing": ["The AC’s dry mode works too. Stop at {rh_stop}%."],
    },
    "rh_dry": {
        "effect": ["Under {rh_dry}%, dry air irritates the nose and throat."],
        "now": ["{drier_on}Outside is drier still ({rh_out}%), so airing makes it worse."],
        "timing": [],
    },
    "pm": {
        "effect": ["Fine particles reach deep into the lungs. The line is {pm_limit}, WHO’s guideline for a 24-hour average, used here for any hour."],
        "now": ["The {rush_wind} wind carries BQE rush-hour fumes onto the block.",
                "{smoke_on}NOAA reports wildfire smoke over the region.",
                "The forecast peaks at {pm} around {peak_at}, from {pm_now} now."],
        "timing": ["The forecast comes from the Copernicus model via Open-Meteo, adjusted to your backyard monitor."],
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
                                  "Stale air can make sleep lighter: air the apartment before the next nap."],
                "Stale last night": "CO₂ stayed over {co2_limit} most of last night, peaking at {night_peak_s}. Air the apartment before bed, or leave a window open a crack.",
                "Dirty outside": "PM2.5 outside is over {pm_high}: keep the toddler inside, windows shut.",
                True: "CO₂ is under {co2_limit}: fresh air helps a toddler sleep deeper.",
                False: "Stale or dirty air: CO₂ over {co2_limit}, or the air outside is too dirty to go out.",
                None: "The indoor monitor hasn’t reported."},
    "sinus": {"Too damp": "Humidity is over {rh_damp}%: mold and dust mites like it, and both set off allergies.",
              "Too dry": "Humidity is under {rh_dry}%: dry air irritates the nose and sinuses.",
              "Pollen high": ["{pollen_type_cap} pollen is {pollen_index} of 5 today: keep the windows shut.", "Pollen is high today: keep the windows shut."],
              "Damp + pollen": "Damp inside and pollen outside: dehumidify with the windows shut.",
              True: "Humidity is between {rh_dry} and {rh_damp}%, and pollen is low.",
              False: "Damp air, dry air or pollen: the item above says which and what to do.",
              None: "The indoor monitor hasn’t reported."},
    "runner": {"Avoid": "PM2.5 outside is forecast over {pm_limit} in those hours: run before or after.",
               "Not clean now": "PM2.5 outside is over {pm_limit} now.",
               "Skip today": "PM2.5 outside is over {pm_high} today: skip the run.",
               True: "Outdoor PM2.5 is under {pm_limit}.",
               False: "Outdoor PM2.5 is over {pm_limit} then.",
               None: "The outdoor monitor hasn’t reported."},
}
SMOKE_CLEAN = "NOAA reports smoke in the region; the air here is clean (PM2.5 {pm_now})."

_POINTS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]


def compass(deg):
    """The direction a wind comes from, in one of 8 words."""
    return _POINTS[round((deg % 360) / 45) % 8]


def _derived(facts):
    f = {**LIMIT_FACTS, **{k: v for k, v in facts.items() if v is not None}}
    if f.get("cause") == "BQE rush" and f.get("wind_dir") is not None:
        f["rush_wind"] = compass(f["wind_dir"])
    if f.get("smoke"):
        f["smoke_on"] = ""
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


def why(item_id, facts, effect=None):
    """Two or three sentences for an item's (i). `effect`, when given (the model's line), replaces the effect part."""
    key = item_id
    if item_id == "rh":
        key = "rh_dry" if facts.get("dry") else "rh_damp"
    parts = LIBRARY[key]
    out = []
    for kind in ("effect", "now", "timing"):
        if kind == "effect" and effect:
            out.append(effect)
            continue
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
    key = "Avoid" if state and state.startswith("Avoid") else state   # "Avoid 4–8 PM": the hours change
    tpl = PILLS[need_id].get(key) or PILLS[need_id][ok]
    for t in [tpl] if isinstance(tpl, str) else tpl:
        s = fill(t, facts)
        if s:
            return s
    return ""
