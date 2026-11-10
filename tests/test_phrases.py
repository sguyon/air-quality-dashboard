import re

from phrases import LIBRARY, LIMIT_FACTS, PILLS, why, pill_why, compass, fill

FULL_FACTS = {
    "co2": {"co2": 1240, "since": "noon", "rush_start": "4 PM", "temp_at": 7, "temp_time": "11 PM", "clean_at": "8 PM"},
    "rh": {"rh": 64, "rh_out": 80, "dry": False, "drier_out": False},
    "pm": {"pm": 25, "pm_now": 4, "peak_at": "7 PM", "cause": "BQE rush", "wind_dir": 135, "smoke": True},
    "pollen": {"pollen_index": 4, "pollen_type": "tree"},
}


def numbers(text):
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}


def numbers_in(facts):
    return {float(v) for v in facts.values() if isinstance(v, (int, float)) and not isinstance(v, bool)} | \
        {float(n) for v in facts.values() if isinstance(v, str) for n in re.findall(r"\d+", v)}


def test_every_template_fills_or_drops():
    for item, parts in LIBRARY.items():
        facts = FULL_FACTS["rh" if item.startswith("rh") else item]
        for kind, temps in parts.items():
            for t in temps:
                out = fill(t, {**facts, "dry": item == "rh_dry"})
                assert out is None or "{" not in out, (item, kind, t)


def test_missing_slot_drops_sentence():
    text = why("co2", {"co2": 1240})
    assert "{" not in text and text.startswith("Above 800 the air feels stale")


def test_numbers_come_from_facts():
    for item, facts in FULL_FACTS.items():
        text = why(item, facts)
        assert numbers(text) <= numbers_in(facts) | {800, 60, 30, 55, 15, 24, 35, 10, 3, 5}, (item, text)


def test_two_or_three_sentences():
    for item, facts in FULL_FACTS.items():
        n = len(re.findall(r"[.!?](\s|$)", why(item, facts)))
        assert 1 <= n <= 4, why(item, facts)


def test_wind_word_from_direction():
    assert compass(135) == "southeast" and compass(0) == "north" and compass(350) == "north"
    assert "southeast wind" in why("pm", FULL_FACTS["pm"])


def test_pm_explains_the_15_line():
    assert "24-hour average" in why("pm", {"pm": 25})


def test_dry_and_damp_differ():
    assert "mold" in why("rh", {"rh": 64, "dry": False}) and "dry" in why("rh", {"rh": 24, "dry": True}).lower()
    # the AC is named only for a home that has one (summary sets ac_too from [home] appliances)
    assert "dry mode" in why("rh", {"rh": 64, "dry": False, "ac_too": True})
    assert "dry mode" not in why("rh", {"rh": 64, "dry": False})


def test_toddler_pill_by_state():
    s = pill_why("toddler", {"night_peak": 1150}, ok=False, state="Stale last night")
    assert "1,150" in s and "before bed" in s
    assert "1,150" in pill_why("toddler", {"co2": 900, "night_peak": 1150}, ok=False, state="Stale indoors")
    assert "{" not in pill_why("toddler", {"co2": 900}, ok=False, state="Stale indoors")
    assert "35" in pill_why("toddler", {}, ok=False, state="Dirty outside")


def test_sinus_pill_by_state():
    assert "60%" in pill_why("sinus", {"rh": 64}, ok=False, state="Too damp")
    assert "30%" in pill_why("sinus", {"rh": 24}, ok=False, state="Too dry")
    assert "Tree pollen is 4 of 5" in pill_why("sinus", {"pollen_index": 4, "pollen_type": "tree"}, ok=False, state="Pollen high")
    assert "item above" not in pill_why("sinus", {"rh": 64, "pollen_index": 4}, ok=False, state="Damp + pollen")


def test_runner_pill_by_state():
    assert pill_why("runner", {}, ok=False, state="Avoid 4–8 PM") == "PM2.5 outside is forecast over 15 in those hours: run before or after."
    assert pill_why("runner", {}, ok=False, state="Run after 11 AM") == "PM2.5 outside is over 15 until then."
    assert pill_why("runner", {}, ok=False, state="Skip today") == "PM2.5 outside is over 35 today: skip the run."


def test_pill_whys():
    assert "smoke" in pill_why("runner", {"pm_now": 0, "smoke": True}, ok=True).lower()
    assert "smoke" not in pill_why("runner", {"pm_now": 3, "smoke": False}, ok=True).lower()
    for nid in PILLS:
        for ok in (True, False, None):
            assert "{" not in pill_why(nid, {}, ok=ok)


def test_damp_wording_follows_the_dew_point():
    assert "wetter" in why("rh", {"rh": 64, "rh_out": 80, "dry": False, "drier_out": False})
    t = why("rh", {"rh": 64, "rh_out": 70, "dry": False, "drier_out": True})
    assert "wetter" not in t and "drier" in t
    assert "drier still" not in why("rh", {"rh": 24, "rh_out": 40, "dry": True, "drier_out": False})


def test_outdoor_co2_number_is_a_fact():
    assert "420" in why("co2", {"co2": 1240}) and 420 in LIMIT_FACTS.values()


# ── A home with one monitor: where its outdoor PM2.5 comes from, and the profiles it can't judge ──

FORECAST = "The forecast is Open-Meteo’s prediction for the wider area"
NEAR = {"source_kind": "monitor", "source_name": "Cedar & 2nd Ave", "source_km": 1.1, "source_fallback": False}


def timing(facts):
    """The PM2.5 item's last sentence(s): what follows the effect sentence and any now sentence."""
    return why("pm", {"pm": 25, **facts}).split(FORECAST, 1)[1]


def test_own_outdoor_monitor_sentences_unchanged():
    assert why("pm", {"pm": 25, "forecast_fit": "calibrated"}).endswith(
        f"{FORECAST}, scaled to what your {LIMIT_FACTS['outdoor']} monitor measured over the last day.")
    assert why("pm", {"pm": 25, "forecast_fit": "anchored", "monitor_label": "this monitor"}).endswith(
        f"{FORECAST}, started from this monitor’s reading now.")


def test_nearby_public_monitor_sentence():
    assert why("pm", {"pm": 25, "forecast_fit": "calibrated", **NEAR}).endswith(
        f"{FORECAST}, scaled to what the public monitor at Cedar & 2nd Ave, 1.1 km away, measured over the last day.")
    assert why("pm", {"pm": 25, "forecast_fit": "anchored", **NEAR}).endswith(
        f"{FORECAST}, started from what the public monitor at Cedar & 2nd Ave, 1.1 km away, reads now.")
    assert "2 km away" in timing({"forecast_fit": "calibrated", **NEAR, "source_km": 2.0})
    # its name unknown (gone from AirGradient's list since the server started): never "None"
    unnamed = {"forecast_fit": "calibrated", "source_kind": "monitor", "source_name": None, "source_km": None}
    assert timing(unnamed) == ", scaled to what the public monitor you chose measured over the last day."


def test_area_sentence():
    facts = {"forecast_fit": "area", "source_kind": "area", "area_count": 4, "source_fallback": False}
    assert why("pm", {"pm": 25, **facts}).endswith(
        f" {FORECAST}, scaled to what 4 public monitors near you measured over the last day.")


def test_model_sentence():
    facts = {"forecast_fit": None, "source_kind": "model", "source_fallback": False}
    assert why("pm", {"pm": 25, **facts}).endswith(
        f" {FORECAST}: an estimate, with no monitor outside to check it against.")


def test_fallback_says_the_chosen_monitor_isnt_reporting():
    area = {"forecast_fit": "area", "source_kind": "area", "area_count": 3, "source_name": "Cedar & 2nd Ave",
            "source_km": 1.1, "source_fallback": True}
    assert why("pm", {"pm": 25, **area}).endswith(
        f" Cedar & 2nd Ave isn’t reporting, so this is an estimate for your area. {FORECAST}, scaled to what 3 public"
        " monitors near you measured over the last day.")
    model = {"source_kind": "model", "source_name": None, "source_fallback": True}
    assert why("pm", {"pm": 25, **model}).endswith(
        f" The public monitor you chose isn’t reporting, so this is an estimate for your area. {FORECAST}: an estimate,"
        " with no monitor outside to check it against.")


def test_fallback_when_airgradient_didnt_answer_doesnt_blame_the_monitor():
    """AirGradient's list of public monitors didn't answer: the chosen monitor may well be reporting."""
    model = {"source_kind": "model", "source_name": "Cedar & 2nd Ave", "source_km": 1.1, "source_fallback": "list"}
    text = why("pm", {"pm": 25, **model})
    assert text.endswith(f" AirGradient didn’t answer, so this is an estimate for your area. {FORECAST}: an estimate,"
                         " with no monitor outside to check it against.")
    assert "reporting" not in text
    monitor = {**model, "source_fallback": "monitor"}
    assert "Cedar & 2nd Ave isn’t reporting, so this is an estimate for your area." in why("pm", {"pm": 25, **monitor})


def test_a_source_never_names_an_outdoor_monitor_the_home_lacks():
    for facts in ({"forecast_fit": "calibrated", **NEAR}, {"forecast_fit": "area", "source_kind": "area", "area_count": 2},
                  {"source_kind": "model"}):
        assert "your outdoor monitor" not in why("pm", {"pm": 25, **facts})
    assert pill_why("runner", {"source_kind": "model"}, ok=None) == "Outdoor PM2.5 isn’t available right now."
    assert pill_why("runner", {}, ok=None) == "The outdoor monitor hasn’t reported."


def test_toddler_needs_an_indoor_monitor():
    s = pill_why("toddler", {"no_indoor": True}, ok=None, state="Needs an indoor monitor")
    assert s == "A toddler sleeps deeper when CO₂ indoors stays low, and only an indoor monitor measures it."


def test_sinus_on_pollen_only():
    no_in = {"no_indoor": True}
    assert pill_why("sinus", {**no_in, "pollen_index": 4, "pollen_type": "tree"}, ok=False, state="Pollen high") == \
        "Tree pollen is 4 of 5 today: keep the windows shut (pollen only: no indoor monitor for humidity)."
    assert pill_why("sinus", {**no_in, "pollen_index": 1}, ok=True, state="Pollen low") == \
        "Pollen is low today (pollen only: no indoor monitor for humidity)."
    assert "pollen only: no indoor monitor for humidity" in pill_why("sinus", no_in, ok=None, state="No reading")
    # a home with an indoor monitor keeps its sentences
    assert pill_why("sinus", {"pollen_index": 4, "pollen_type": "tree"}, ok=False, state="Pollen high") == \
        "Tree pollen is 4 of 5 today: keep the windows shut."
    assert pill_why("sinus", {}, ok=None) == "The indoor monitor hasn’t reported."
    assert pill_why("sinus", {"pollen_index": 1}, ok=True, state="Pollen low").startswith("Humidity is between")
