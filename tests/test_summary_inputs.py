"""Weather forecast fields reach the summary rules without live upstream calls."""
from datetime import datetime
from zoneinfo import ZoneInfo

import air_read
import sources
import summary


def test_hourly_weather_dew_point_drives_damp_room_airing(canned, monkeypatch):
    now = datetime(2026, 11, 8, 15, 40, tzinfo=ZoneInfo("America/New_York"))
    weather = {"hourly": {"time": ["2026-11-08T16:00", "2026-11-08T18:00", "2026-11-08T19:00"],
                          "dew_point_2m": [17, 9]}}
    monkeypatch.setattr(sources, "get_open_meteo_data", lambda: weather)
    monkeypatch.setattr(summary, "APPLIANCES", set())
    inputs = air_read.summary_inputs({}, 600, 64, 80, 21, 21, 4, [], [], now)
    assert [h["dew"] for h in inputs["hourly"]] == [17, 9, None]
    rh = next(i for i in summary.build_summary(**inputs)["items"] if i["id"] == "rh")
    assert rh["action"] == {"text": "Air the room for 10 min", "when": "after 6 PM",
                            "when_end": "2026-11-08T18:00:00-05:00"}
