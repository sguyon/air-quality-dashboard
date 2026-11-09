from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from summary import anchor_forecast, pm_outlook, candidates, select

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 8, 15, 40, tzinfo=TZ)


def at(h, m=0, day=0):
    return datetime(2026, 11, 8, 0, 0, tzinfo=TZ) + timedelta(days=day, hours=h, minutes=m)


def outlook(peak=None, now_v=4, at_h=19, cause=None):
    """An outlook whose forecast peaks at `peak` (or stays at now_v) at `at_h` o'clock."""
    pts = [(at(h), now_v) for h in range(16, 24)]
    if peak is not None:
        pts = [(t, peak if t.hour == at_h else now_v) for t, _ in pts]
    o = pm_outlook(now_v, pts, NOW)
    o["cause"] = cause
    return o


def test_anchor_edges():
    t = [NOW + timedelta(hours=h) for h in range(4)]
    adj, ok = anchor_forecast(list(zip(t, [30, 32, 20, 10])), 0, 30)
    assert ok and [v for _, v in adj] == [0, 7, 0, 0]      # the -30 offset fades: -25 at 1 h, -20 at 2 h
    adj, ok = anchor_forecast(list(zip(t, [5, 6, 7, 8])), None, 5)
    assert not ok and [v for _, v in adj] == [5, 6, 7, 8]


def test_anchor_skips_missing_values():
    t = [NOW + timedelta(hours=h) for h in range(3)]
    adj, _ = anchor_forecast(list(zip(t, [10, None, 12])), 4, 10)
    assert [v for _, v in adj] == [4, 8]


def test_outlook_over_stretches_and_high():
    pts = [(at(h), v) for h, v in zip(range(16, 22), [6, 18, 23, 25, 16, 8])]
    o = pm_outlook(4, pts, NOW)
    assert o["max"] == 25 and o["max_at"] == at(19) and o["forecast"] and not o["high"]
    assert o["over"] == [(at(17), at(21))]
    assert pm_outlook(40, [], NOW)["high"] and not pm_outlook(40, [], NOW)["forecast"]


def test_outlook_ignores_beyond_window():
    assert pm_outlook(4, [(at(16), 3), (at(17), 3), (at(1, day=1), 30)], NOW)["max"] == 4


def test_scores_and_order():
    c = candidates({"co2": 1240, "rh": 64, "pm_now": 4}, outlook(peak=25, cause="BQE rush"), None)
    assert [x["id"] for x in c] == ["pm", "co2", "rh"]          # 25/15=1.67 > 1240/800=1.55 > 64/60
    assert c[0]["forecast"] and c[1]["ctx"] == "55% over the 800 limit" and c[2]["ctx"] == "4 points over 60"
    assert c[0]["ctx"] == "Peak 7 PM, BQE rush · now 4" and c[0]["num"] == "25" and c[0]["key"] == "out"
    assert c[1]["num"] == "1,240" and c[1]["unit"] == "ppm" and c[1]["key"] == "in" and c[2]["key"] is None


def test_measured_beats_forecast_on_tie():
    c = candidates({"co2": 1200, "pm_now": 4}, outlook(peak=22.5), None)   # 1.5 and 1.5
    assert [x["id"] for x in c] == ["co2", "pm"]


def test_dry_scores_and_ctx():
    c = candidates({"rh": 24}, outlook(), None)
    assert c[0]["ctx"] == "6 points under 30" and abs(c[0]["score"] - 30 / 24) < 1e-9


def test_measured_pm_item():
    c = candidates({"pm_now": 20}, pm_outlook(20, [], NOW), None)
    assert c[0]["id"] == "pm" and not c[0]["forecast"] and c[0]["ctx"] == "33% over the 15 limit"


def test_pollen_candidate():
    c = candidates({}, outlook(), {"index": 4, "name": "Tree"})
    assert c[0]["id"] == "pollen" and c[0]["num"] == "4" and c[0]["unit"] == "of 5" and c[0]["ctx"] == "Tree pollen, high today"
    assert candidates({}, outlook(), {"index": 2, "name": "Tree"}) == []


def test_select_caps_three_and_builds_also():
    four = candidates({"co2": 1240, "rh": 64, "pm_now": 4}, outlook(peak=25), {"index": 3, "name": "Grass"})
    items, also = select(four, ["pollen high tomorrow (trees), keep windows shut overnight"])
    assert len(items) == 3 and also.startswith("Also: ") and "and 1 more" not in also
    assert "Pollen today" in also and "pollen high tomorrow" in also


def test_also_folds_past_two():
    five = candidates({"co2": 1240, "rh": 64, "pm_now": 4}, outlook(peak=25), {"index": 3, "name": "Grass"})
    _, also = select(five, ["one", "two"])
    assert also.endswith(", and 1 more.")


def test_select_nothing():
    assert select([], []) == ([], None)


def test_missing_readings():
    assert candidates({"co2": None, "rh": None, "pm_now": None}, pm_outlook(None, [], NOW), None) == []


# ── Task 3: timed actions and the needs row ──
from summary import action, needs_row, fmt_range, last_night, candidates  # noqa: E402


def iso(t):
    return t.isoformat()


RUSH = [(at(7), at(10), False), (at(16), at(20), True), (at(7, day=1), at(10, day=1), False)]
CO2_ITEM = {"id": "co2"}
RH_ITEM = {"id": "rh"}
PM_ITEM = {"id": "pm"}


def ol(over=(), now_v=4, high=False):
    o = pm_outlook(now_v, [], NOW)
    o.update(over=list(over), high=high)
    return o


def test_fmt_range():
    assert fmt_range(at(16), at(20)) == "4–8 PM" and fmt_range(at(23), at(1, day=1)) == "11 PM–1 AM"
    assert fmt_range(at(16, 30), at(20)) == "4:30–8 PM"


def test_airing_before_dirty_stretch():
    a = action(CO2_ITEM, {"co2": 1240}, ol(over=[(at(16), at(20))]), RUSH, at(15, 40))
    assert a == {"text": "Open a window for 10 min", "when": "before 4 PM", "when_end": iso(at(16))}


def test_airing_now_when_clean():
    assert action(CO2_ITEM, {"co2": 1240}, ol(), RUSH, at(15, 40)) == {"text": "Open a window for 10 min", "when": "now", "when_end": None}


def test_airing_after_when_dirty_now():
    a = action(CO2_ITEM, {"co2": 1240}, ol(over=[(at(15, 40), at(20))], now_v=22), RUSH, at(15, 40))
    assert a["text"] == "Open a window for 10 min" and a["when"] == "after 8 PM" and a["when_end"] == iso(at(20))


def test_airing_blocked_over_35():
    o = ol(over=[(at(15, 40), at(20))], now_v=40, high=True)
    assert action(CO2_ITEM, {"co2": 1240}, o, RUSH, at(15, 40)) == {"text": "Air out", "when": "after 8 PM", "when_end": iso(at(20))}
    assert action(PM_ITEM, {"pm_now": 40}, o, RUSH, at(15, 40))["text"] == "Keep windows shut"


def test_damp_uses_dehumidifier():
    a = action(RH_ITEM, {"rh": 64, "rh_out": 80, "t_in": 21, "t_out": 21}, ol(), RUSH, at(15))
    assert a == {"text": "Run the dehumidifier", "when": "until under 55%", "when_end": None}


def test_damp_airs_when_drier_outside():
    a = action(RH_ITEM, {"rh": 64, "rh_out": 40, "t_in": 21, "t_out": 8}, ol(), RUSH, at(15))
    assert a["text"] == "Air the room for 10 min" and a["when"] == "drier outside"


def test_dry_has_no_humidifier():
    assert action(RH_ITEM, {"rh": 24, "rh_out": 60, "t_in": 21, "t_out": 21}, ol(), RUSH, at(15))["text"] is None
    a = action(RH_ITEM, {"rh": 24, "rh_out": 40, "t_in": 21, "t_out": 0}, ol(), RUSH, at(15))
    assert a["text"] == "Keep windows shut" and a["when"] == "while it’s this dry outside"


def test_pm_item_window():
    a = action(PM_ITEM, {"pm_now": 4}, ol(over=[(at(16), at(20))]), RUSH, at(15, 40))
    assert a == {"text": "Windows shut", "when": "4–8 PM", "when_end": iso(at(20))}


def test_pm_item_dirty_now():
    a = action(PM_ITEM, {"pm_now": 20}, ol(over=[(at(15, 40), at(20))], now_v=20), RUSH, at(15, 40))
    assert a["when"] == "until 8 PM"


def test_when_across_midnight():
    now = at(22, 30)
    a = action(PM_ITEM, {"pm_now": 4}, ol(over=[(at(23), at(1, day=1))]), RUSH, now)
    assert a["when"] == "11 PM–1 AM"
    b = action(CO2_ITEM, {"co2": 900}, ol(over=[(at(0, day=1), at(2, day=1))]), RUSH, now)
    assert b["when"] == "before 12 AM"


def test_pollen_action():
    assert action({"id": "pollen"}, {}, ol(), RUSH, at(9)) == {"text": "Keep windows shut", "when": "today", "when_end": None}


FINE = {"co2": 600, "rh": 45, "pm_now": 3}


def need(row, nid):
    return next(n for n in row if n["id"] == nid)


def test_runner_says_clean_air_without_a_cutoff():
    # the rush and rain don't end "clean": only PM2.5 itself turns the Runner amber
    n = need(needs_row(FINE, ol(), None, False, None, at(15)), "runner")
    assert (n["ok"], n["state"], n["name"]) == (True, "Clean air", "Runner")


def test_runner_amber_only_on_numbers():
    assert need(needs_row(FINE, ol(over=[(at(16), at(20))]), None, False, None, at(15)), "runner")["state"] == "Avoid 4–8 PM"
    assert need(needs_row(FINE, ol(over=[(at(15), at(20))], now_v=20), None, False, None, at(15)), "runner")["state"] == "Run after 8 PM"
    n = need(needs_row(FINE, ol(over=[(at(15), at(20))], now_v=40, high=True), None, False, None, at(15)), "runner")
    assert (n["ok"], n["state"]) == (False, "Skip today")


def test_smoke_alone_stays_green():
    n = need(needs_row(FINE, ol(), None, True, None, at(15)), "runner")
    assert n["ok"] is True and n["facts"]["smoke"] is True


def test_sinus_states():
    s = lambda r, p=None: need(needs_row({**FINE, **r}, ol(), p, False, None, at(9)), "sinus")["state"]
    assert s({"rh": 64}) == "Too damp" and s({"rh": 24}) == "Too dry"
    assert s({}, {"index": 4, "name": "Tree"}) == "Pollen high" and s({"rh": 64}, {"index": 4, "name": "Tree"}) == "Damp + pollen"
    assert s({}, {"index": 1, "name": "Tree"}) == "Pollen low" and s({}) == "All fine"
    assert need(needs_row(FINE, ol(), None, False, None, at(9)), "sinus")["name"] == "Sinus & allergy"


def test_toddler_states():
    t = lambda r, o=None, night=None: need(needs_row({**FINE, **r}, o or ol(), None, False, night, at(9)), "toddler")["state"]
    assert t({"co2": 900}) == "Stale indoors" and t({}) == "Fresh indoors" and t({}, ol(now_v=40, high=True)) == "Dirty outside"
    stale = {"peak": 1150, "share": 1.0, "stale": True}
    assert t({}, night=stale) == "Stale last night" and t({"co2": 900}, night=stale) == "Stale indoors"
    assert t({}, night={"peak": 820, "share": 0.2, "stale": False}) == "Fresh indoors"


def test_toddler_night_facts():
    n = need(needs_row(FINE, ol(), None, False, {"peak": 1150, "share": 1.0, "stale": True}, at(9)), "toddler")
    assert n["ok"] is False and n["facts"]["night_peak"] == 1150


def test_missing_pills():
    row = needs_row({"co2": None, "rh": None, "pm_now": None}, pm_outlook(None, [], NOW), None, False, None, at(9))
    assert [(n["ok"], n["state"]) for n in row] == [(None, "No reading")] * 3


def test_pill_states_are_short():
    for r in (FINE, {"co2": 900, "rh": 64, "pm_now": 20}):
        for n in needs_row(r, ol(over=[(at(16), at(20))]), {"index": 4, "name": "Tree"}, False, None, at(15)):
            assert len(n["state"].replace(" PM", "").replace(" AM", "").split()) <= 3


def night_pts(v_night, day=0):
    """CO2 every 10 minutes from 9 PM the evening before to 9 AM, v_night from 10 PM to 7 AM, 600 otherwise."""
    start = at(21, day=day - 1)
    return [(start + timedelta(minutes=10 * i), v_night if 6 <= i < 60 else 600) for i in range(73)]


def test_last_night():
    s = last_night(night_pts(1000), at(9))
    assert s["stale"] and s["peak"] == 1000 and s["share"] == 1.0
    assert not last_night(night_pts(700), at(9))["stale"]
    assert last_night(night_pts(1000), at(5)) is None          # the night isn't over yet
    assert last_night(night_pts(1000), at(22, 30)) is None     # a new night has started: the reading now counts
    assert last_night([], at(9)) is None


def test_co2_item_mentions_the_night():
    c = candidates({"co2": 1120}, ol(), None, night={"peak": 1150, "share": 1.0, "stale": True})[0]
    assert c["ctx"] == "40% over the 800 limit · over 800 all last night"
    c = candidates({"co2": 1120}, ol(), None, night={"peak": 1150, "share": 0.6, "stale": True})[0]
    assert c["ctx"].endswith("· over 800 most of last night")
    assert candidates({"co2": 1120}, ol(), None)[0]["ctx"] == "40% over the 800 limit"


# ── Task 5: chart data and the payload ──
from summary import timeline, build_summary  # noqa: E402


def hourly_for(start, n, temp=15, pop=0, mm=0, uv=0, wind=135):
    return [{"t": start + timedelta(hours=k), "temp": temp, "pop": pop, "mm": mm, "uv": uv, "wind_dir": wind} for k in range(n)]


SUN = [{"t": at(6, 35), "kind": "Sunrise"}, {"t": at(16, 40), "kind": "Sunset"},
       {"t": at(6, 36, day=1), "kind": "Sunrise"}, {"t": at(16, 39, day=1), "kind": "Sunset"}]


def pts(start, end, v, step=30):
    out, t = [], start
    while t <= end:
        out.append((t, v)); t += timedelta(minutes=step)
    return out


def test_timeline_window():
    tl = timeline(at(15, 40), pts(at(10), at(15, 40), 900), [], [], [], hourly_for(at(11), 20), SUN, False)
    assert tl["t0"] == iso(at(12)) and tl["t1"] == iso(at(3, day=1)) and tl["now"] == iso(at(15, 40))
    assert tl["co2"][0][0] >= iso(at(12)) and tl["co2"][-1][0] <= iso(at(15, 40))
    assert [h["t"] for h in tl["hours"]] == [iso(at(h)) for h in (12, 15, 18, 21)] + [iso(at(0, day=1)), iso(at(3, day=1))]
    assert tl["sun"] == [{"t": iso(at(16, 40)), "kind": "Sunset"}] and tl["night"] == [[iso(at(16, 40)), iso(at(3, day=1))]]
    assert tl["limits"] == {"co2": 800, "pm": 15, "rh": 60}


def test_timeline_midnight():
    tl = timeline(at(21, 30), [], [], [], [], hourly_for(at(17), 20), SUN, False)
    assert tl["t0"] == iso(at(18)) and tl["t1"] == iso(at(9, day=1))
    assert {"t": iso(at(6, 36, day=1)), "kind": "Sunrise"} in tl["sun"]
    assert tl["night"] == [[iso(at(18)), iso(at(6, 36, day=1))]]


def test_timeline_rain_and_uv():
    hr = hourly_for(at(11), 20)
    for h in hr:
        if h["t"].hour in (13, 14, 15):
            h["uv"] = 7
        if h["t"] in (at(18), at(19)):
            h.update(pop=80, mm=1.2)
    tl = timeline(at(9, 10), [], [], [], [], hr, SUN, False)
    assert tl["uv"] == [[iso(at(13)), iso(at(16)), 7]]
    eighteen = next(h for h in tl["hours"] if h["t"] == iso(at(18)))
    assert eighteen["pop"] == 80 and eighteen["mm"] == 2.4
    assert next(h for h in tl["hours"] if h["t"] == iso(at(12)))["pop"] is None


def test_timeline_missing():
    tl = timeline(at(15, 40), [], [], [], [], [], [], False)
    assert tl["co2"] is None and tl["pm"] == {"past": [], "fc": []} and tl["hours"] == [] and tl["rh"] is None


def test_rh_only_when_asked():
    rh = pts(at(12), at(15, 40), 64)
    assert timeline(at(15, 40), [], rh, [], [], [], [], True)["rh"] and timeline(at(15, 40), [], rh, [], [], [], [], False)["rh"] is None


BUSY_R = {"co2": 1240, "rh": 64, "rh_out": 80, "t_in": 21, "t_out": 21, "pm_now": 4}


def busy(**k):
    cams = [(at(h), v) for h, v in zip(range(15, 27), [4, 6, 18, 23, 25, 16, 8, 5, 4, 4, 4, 4])]
    args = dict(r=BUSY_R, cams=cams, hourly=hourly_for(at(11), 20), co2_pts=pts(at(12), at(15, 40), 1100),
                rh_pts=pts(at(12), at(15, 40), 63), pm_past=pts(at(12), at(15, 40), 4), smoke=False,
                pollen_today=None, pollen_tomorrow=None,
                rush=[(at(16), at(20), True), (at(7, day=1), at(10, day=1), False)], sun=SUN, now=at(15, 40), road="BQE")
    args.update(k)
    return build_summary(**args)


def test_build_summary_busy():
    s = busy()
    assert set(s) == {"label", "clock", "items", "also", "needs", "all_clear", "timeline"}
    assert s["label"] == "Today" and s["clock"] == "3:40 PM" and not s["all_clear"]
    assert [i["id"] for i in s["items"]] == ["pm", "co2", "rh"]
    pm, co2, rh = s["items"]
    assert pm["forecast"] and pm["ctx"] == "Peak 7 PM, BQE rush · now 4" and pm["action"]["when"].startswith("5")
    assert co2["action"] == {"text": "Open a window for 10 min", "when": "before 5 PM", "when_end": iso(at(17))}
    assert "before 5 PM" in co2["why"] and rh["action"]["text"] == "Run the dehumidifier" and "wetter" in rh["why"]
    assert [n["state"] for n in s["needs"]] == ["Stale indoors", "Too damp", "Avoid 5–9 PM"]
    assert [i["need"] for i in s["items"]] == ["runner", "toddler", "sinus"]
    assert all(n["why"] for n in s["needs"]) and s["timeline"]["rh"] is not None


def test_build_summary_tonight_and_clear():
    s = busy(r={"co2": 600, "rh": 45, "pm_now": 3}, cams=[(at(h), 3) for h in range(21, 34)], now=at(21, 30),
             co2_pts=pts(at(18), at(21, 30), 600), rush=[(at(7, day=1), at(10, day=1), True)])
    assert s["label"] == "Tonight" and s["all_clear"] and s["items"] == []
    assert [n["ok"] for n in s["needs"]] == [True, True, True] and s["needs"][2]["state"] == "Clean air"


def test_tomorrow_pollen_goes_on_also():
    s = busy(pollen_tomorrow={"index": 4, "name": "Tree"})
    assert s["also"] == "Also: pollen high tomorrow (tree), keep windows shut overnight."


def test_night_without_yesterdays_sunset():
    sun_today = [e for e in SUN if e["t"] >= at(0)]          # just after midnight, the data starts with today's sunrise
    tl = timeline(at(0, 33), [], [], [], [], [], sun_today, False)
    assert tl["night"][0] == [iso(at(-3)), iso(at(6, 35))]


from summary import rush_windows  # noqa: E402


def test_rush_windows_from_forecast_wind():
    hr = hourly_for(at(0), 48, wind=135)                       # southeast all day: toward home
    for h in hr:
        if 7 <= h["t"].hour < 10:
            h["wind_dir"] = 300                                # mornings from the northwest: away
    rw = rush_windows(hr, at(15, 40), [(7, 10, "morning"), (16, 20, "evening")], (80, 200))
    assert rw == [(at(7), at(10), False), (at(16), at(20), True), (at(7, day=1), at(10, day=1), False), (at(16, day=1), at(20, day=1), True)]
    assert rush_windows([], at(15), [(16, 20, "evening")], (80, 200)) == [(at(16), at(20), False), (at(16, day=1), at(20, day=1), False)]


def test_anchor_fades_over_six_hours():
    t = [NOW + timedelta(hours=h) for h in (0, 3, 6, 9)]
    adj, ok = anchor_forecast(list(zip(t, [8, 8, 8, 8])), 26, 8)     # a spike of +18 over CAMS
    assert ok and [v for _, v in adj] == [26, 17, 8, 8]               # full at now, half at 3 h, gone by 6 h


from summary import calibrate_forecast  # noqa: E402


def test_calibrate_scales_by_the_days_ratio():
    past = [(NOW - timedelta(hours=h), 12) for h in range(1, 25)]            # CAMS said 12 all day
    mon = [(NOW - timedelta(hours=h, minutes=m), 3) for h in range(1, 25) for m in (10, 40)]   # the monitor read 3
    fut = [(NOW + timedelta(hours=h), v) for h, v in ((1, 12), (2, 40))]
    adj, k = calibrate_forecast(past + fut, mon, NOW)
    assert abs(k - 3.5 / 12.5) < 1e-9
    assert [v for _, v in adj] == [round(12 * k, 1), round(40 * k, 1)]       # 3.4 and 11.2: the shape stays, the level drops


def test_calibrate_needs_enough_hours():
    past = [(NOW - timedelta(hours=h), 12) for h in range(1, 4)]
    adj, k = calibrate_forecast(past + [(NOW + timedelta(hours=1), 12)], [(NOW - timedelta(hours=1), 3)], NOW)
    assert k is None and adj is None


def test_calibrate_factor_is_bounded():
    past = [(NOW - timedelta(hours=h), 1) for h in range(1, 25)]
    mon = [(NOW - timedelta(hours=h), 40) for h in range(1, 25)]
    _, k = calibrate_forecast(past + [(NOW + timedelta(hours=1), 1)], mon, NOW)
    assert k == 3.0


def test_a_value_that_rounds_to_the_limit_is_not_over():
    o = pm_outlook(4, [(at(19), 15.3)], NOW)
    assert o["over"] == [] and candidates({"pm_now": 4}, o, None) == []
    assert pm_outlook(4, [(at(19), 15.6)], NOW)["over"] == [(at(19), at(20))]


def test_build_summary_after_a_stale_night():
    s = busy(r={"co2": 600, "rh": 45, "pm_now": 3}, now=at(9), co2_pts=night_pts(1000), cams=[(at(h), 3) for h in range(0, 24)])
    tod = s["needs"][0]
    assert s["all_clear"] and (tod["ok"], tod["state"]) == (False, "Stale last night") and "1,000" in tod["why"]


def test_pm_item_belongs_to_the_toddler_when_high():
    s = busy(r={**BUSY_R, "pm_now": 40}, cams=[(at(h), 40) for h in range(6, 30)], pm_past=pts(at(12), at(15, 40), 40))
    assert next(i for i in s["items"] if i["id"] == "pm")["need"] == "toddler"


def test_since_names_yesterday():
    from summary import _since
    assert _since(pts(at(13, 20), at(15, 40), 1000), 800, at(15, 40)) == "1:20 PM"
    assert _since(pts(at(14, 20, day=-1), at(8), 1000), 800, at(8)) == "yesterday 2:20 PM"
    assert _since(pts(at(8, day=-1), at(8), 1000), 800, at(8)) is None   # over for the whole window: start unknown


def test_damp_why_never_suggests_airing_when_the_action_is_the_dehumidifier():
    # outside is drier, but PM2.5 goes over 15 at 5 PM, so the action is the dehumidifier
    s = busy(r={"co2": 600, "rh": 70, "rh_out": 40, "t_in": 21, "t_out": 15, "pm_now": 4})
    rh = next(i for i in s["items"] if i["id"] == "rh")
    assert rh["action"]["text"] == "Run the dehumidifier" and "airing helps" not in rh["why"]
    clear = busy(r={"co2": 600, "rh": 70, "rh_out": 40, "t_in": 21, "t_out": 15, "pm_now": 3}, cams=[(at(h), 3) for h in range(6, 30)])
    rh = next(i for i in clear["items"] if i["id"] == "rh")
    assert rh["action"]["text"] == "Air the room for 10 min" and "airing helps" in rh["why"]


def test_needs_still_apply_with_the_indoor_monitor_offline():
    off = {"co2": None, "rh": None, "pm_now": 50}
    row = needs_row(off, ol(now_v=50, high=True), {"index": 4, "name": "Tree"}, False, None, at(9))
    assert [(n["ok"], n["state"]) for n in row][:2] == [(False, "Dirty outside"), (False, "Pollen high")]
    row = needs_row({"co2": None, "rh": None, "pm_now": 3}, ol(), None, False, None, at(9))
    assert [(n["ok"], n["state"]) for n in row][:2] == [(None, "No reading"), (None, "No reading")]


def test_humidity_zero_is_not_a_crash():
    c = candidates({"rh": 0}, ol(), None)
    assert c[0]["id"] == "rh" and c[0]["ctx"] == "30 points under 30"


def test_air_before_a_dirty_stretch_that_has_not_started():
    # over 35 from 11 PM: airing now is clean, so say so instead of "after 12 AM"
    a = action(CO2_ITEM, {"co2": 900}, ol(over=[(at(23), at(0, day=1))], now_v=4, high=True), [], at(21, 30))
    assert (a["text"], a["when"]) == ("Open a window for 10 min", "before 11 PM")
    a = action(CO2_ITEM, {"co2": 900}, ol(over=[(at(21), at(23))], now_v=40, high=True), [], at(21, 30))
    assert (a["text"], a["when"]) == ("Air out", "after 11 PM")


def test_no_road_no_rush_in_the_text():
    s = busy(road=None, rush=[])
    pm, co2 = s["items"][0], s["items"][1]
    assert pm["ctx"] == "Peak 7 PM · now 4" and "rush" not in pm["why"]
    assert co2["why"].endswith("Do it before 5 PM, when the air outside gets dirtier.")


def test_rush_windows_arc_crossing_north():
    hr = hourly_for(at(0), 48, wind=350)
    rw = rush_windows(hr, at(15, 40), [(16, 20, "evening")], (300, 20))
    assert [t for _, _, t in rw] == [True, True]


# ── The damp-room action follows the appliances in [home] ──
import summary as summary_mod  # noqa: E402

DAMP_R = {"rh": 64, "rh_out": 80, "t_in": 21, "t_out": 21}


def damp_item(monkeypatch, appliances):
    monkeypatch.setattr(summary_mod, "APPLIANCES", set(appliances))
    s = busy()
    return next(i for i in s["items"] if i["id"] == "rh")


def test_damp_with_both_appliances(monkeypatch):
    rh = damp_item(monkeypatch, {"dehumidifier", "ac_dry"})
    assert rh["action"]["text"] == "Run the dehumidifier" and rh["action"]["when"] == "until under 55%"
    assert rh["why"].endswith("The AC’s dry mode works too. Stop at 55%.")


def test_damp_with_only_the_dehumidifier(monkeypatch):
    rh = damp_item(monkeypatch, {"dehumidifier"})
    assert rh["action"]["text"] == "Run the dehumidifier"
    assert "dry mode" not in rh["why"] and rh["why"].endswith("Stop at 55%.")


def test_damp_with_only_the_ac(monkeypatch):
    rh = damp_item(monkeypatch, {"ac_dry"})
    assert rh["action"]["text"] == "Run the AC’s dry mode" and rh["action"]["when"] == "until under 55%"
    assert "works too" not in rh["why"] and rh["why"].endswith("Stop at 55%.")


def test_damp_with_neither(monkeypatch):
    rh = damp_item(monkeypatch, set())
    # nothing lowers the humidity, so no "until under" and no "Stop at"
    assert rh["action"] == {"text": "Keep the windows shut", "when": None, "when_end": None}
    assert "dry mode" not in rh["why"] and "Stop at" not in rh["why"]


def damp_pollen_pill(monkeypatch, appliances):
    monkeypatch.setattr(summary_mod, "APPLIANCES", set(appliances))
    sinus = next(n for n in busy(pollen_today={"index": 4, "name": "Tree"})["needs"] if n["id"] == "sinus")
    assert sinus["state"] == "Damp + pollen"
    assert set(sinus["facts"]) == {"rh", "pollen_index", "pollen_type"}   # the appliances aren't kept as facts
    return sinus["why"]


def test_damp_pollen_pill_follows_the_appliances(monkeypatch):
    both = damp_pollen_pill(monkeypatch, {"dehumidifier", "ac_dry"})
    assert both == "Damp inside and pollen outside: dehumidify with the windows shut."   # the reference home's text
    assert damp_pollen_pill(monkeypatch, {"dehumidifier"}) == both
    assert damp_pollen_pill(monkeypatch, {"ac_dry"}) == "Damp inside and pollen outside: run the AC’s dry mode with the windows shut."
    assert damp_pollen_pill(monkeypatch, set()) == "Damp inside and pollen outside: keep the windows shut."


def test_airing_mentions_the_ac_only_when_there_is_one(monkeypatch):
    dry_out = {**BUSY_R, "rh_out": 40, "t_out": 8}
    monkeypatch.setattr(summary_mod, "APPLIANCES", {"ac_dry"})
    rh = next(i for i in busy(r=dry_out, cams=[(at(h), 3) for h in range(15, 27)])["items"] if i["id"] == "rh")
    assert rh["action"]["text"] == "Air the room for 10 min" and "The AC’s dry mode works too." in rh["why"]
    monkeypatch.setattr(summary_mod, "APPLIANCES", set())
    rh = next(i for i in busy(r=dry_out, cams=[(at(h), 3) for h in range(15, 27)])["items"] if i["id"] == "rh")
    assert "dry mode" not in rh["why"]
