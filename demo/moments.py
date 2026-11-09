"""The demo's three story moments. Every number here is made up, tuned so the summary rules (summary.py, unchanged)
tell each story; tests/test_demo.py pins what they say. A change to the page or the rules that changes a story
updates these numbers and those tests in the same commit.

Hours in `story` are hours from midnight of the moment's day (25 is 1 AM the next day). Each list replaces the usual
day's curve over its span; readings end at the moment, the forecasts go on from it.
"""
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
DEFAULT = "rush"


@dataclass(frozen=True)
class Moment:
    key: str
    label: str
    at: datetime
    # inside (the bedroom): readings now, and the usual levels the week's curves are built from
    co2: float
    co2_night: float          # last night's peak; other nights a little lower
    co2_day: float
    rh_in: float
    rh_in_day: float
    rh_in_night: float        # how damp the closed room gets by morning
    t_in: float
    pm_in: float
    voc: int                  # Sensirion VOC index now (100 = the room's usual)
    # outside (the balcony monitor, and the weather)
    t_out: float
    t_range: tuple            # the usual low and high
    rh_out: float
    rh_out_range: tuple       # the usual afternoon low and morning high
    pm_out: float
    pm_base: float            # clean-air level; the rush hours add to it
    pm_rush_max: float        # the highest a usual weekday rush reaches in the week before
    wind_dir: float
    wind_speed: float
    cloud: int
    weather_code: int
    visibility: int
    uv_max: float
    sun: tuple                # ((sunrise, sunset) today, (sunrise, sunset) tomorrow), "HH:MM" local
    pollen_today: tuple       # (tree, grass, weed) index 0–5
    pollen_tomorrow: tuple
    pollen_in_season: tuple
    nearby_road: float        # how much more PM2.5 a monitor beside the BQE reads than one far from it
    rain: tuple | None = None  # (from, to) hours of rain
    story: dict = field(default_factory=dict)   # signal -> ((hour, value), ...)


MOMENTS = {
    # A bad weekday morning: a stale night in the bedroom, and outside the BQE rush on a southeast wind.
    # Airing has to wait until the rush fumes clear, at 11.
    "rush": Moment(
        key="rush", label="Morning rush", at=datetime(2026, 4, 21, 7, 45, tzinfo=TZ),
        co2=1250, co2_night=1400, co2_day=640,
        rh_in=63, rh_in_day=54, rh_in_night=64, t_in=21.0, pm_in=4.2, voc=128,
        t_out=15.0, t_range=(14, 21), rh_out=93, rh_out_range=(66, 95),
        pm_out=22, pm_base=7, pm_rush_max=19,
        wind_dir=135, wind_speed=9, cloud=55, weather_code=2, visibility=9000, uv_max=6.5,
        sun=(("06:15", "19:39"), ("06:13", "19:40")),
        pollen_today=(4, 1, 0), pollen_tomorrow=(3, 1, 0), pollen_in_season=(True, True, False),
        nearby_road=26,
        # the rush: 22 now, 33 at 9, back under 15 by 11; the evening rush stays under the line
        story={"pm_out": ((5, 8), (6, 11), (7, 16), (7.75, 22), (8, 27), (9, 33), (10, 17), (11, 10), (12, 8),
                          (13, 7), (15, 8), (17, 11), (18, 12), (19, 11), (21, 8), (24, 7))},
    ),
    # A clear November afternoon: west wind, the road's exhaust blown away, nothing to do.
    "clear": Moment(
        key="clear", label="All clear", at=datetime(2026, 11, 3, 14, 0, tzinfo=TZ),
        co2=620, co2_night=760, co2_day=600,
        rh_in=45, rh_in_day=44, rh_in_night=47, t_in=21.5, pm_in=2.1, voc=86,
        t_out=13.0, t_range=(5, 14), rh_out=48, rh_out_range=(45, 78),
        pm_out=5, pm_base=5, pm_rush_max=11,
        wind_dir=290, wind_speed=17, cloud=10, weather_code=1, visibility=24000, uv_max=3,
        sun=(("06:29", "16:47"), ("06:30", "16:46")),
        pollen_today=(0, 0, 0), pollen_tomorrow=(0, 0, 0), pollen_in_season=(False, False, False),
        nearby_road=3,
        story={"pm_out": ((11, 5), (14, 5), (17, 7), (18, 8), (19, 7), (21, 5), (24, 4))},
    ),
    # A warm, rainy October evening: the bedroom is damp and the air outside is wetter still, so a window won't
    # help; the AC's dry mode will. Everything else is fine.
    "humid": Moment(
        key="humid", label="Humid evening", at=datetime(2026, 10, 22, 20, 30, tzinfo=TZ),
        co2=700, co2_night=780, co2_day=640,
        rh_in=66, rh_in_day=57, rh_in_night=59, t_in=23.0, pm_in=3.0, voc=104,
        t_out=18.0, t_range=(16, 21), rh_out=92, rh_out_range=(72, 90),
        pm_out=6, pm_base=6, pm_rush_max=12,
        wind_dir=230, wind_speed=14, cloud=100, weather_code=63, visibility=6000, uv_max=2,
        sun=(("07:15", "18:06"), ("07:16", "18:04")),
        pollen_today=(0, 0, 1), pollen_tomorrow=(0, 0, 1), pollen_in_season=(False, False, False),
        nearby_road=2, rain=(17, 27),
        story={"rh_in": ((17, 58), (18.5, 61), (19.5, 64)),
               "rh_out": ((15, 74), (17.5, 86), (19, 90), (24, 94), (30, 95), (36, 84)),
               "t_out": ((15, 21), (17.5, 19.5), (24, 17.5), (30, 16.5), (36, 19)),
               "pm_out": ((16, 9), (17, 10), (18, 8), (19, 7), (20.5, 6), (22, 5), (24, 5), (30, 5))},
    ),
}


SAMPLES = ("rush", "clear", "humid")   # ?sample=1, 2, 3: the banner's "Sample data 1 2 3"


def moment_for(key, sample=None):
    """The moment for ?sample= (1 to 3) or ?moment= (a key); the sample wins. Anything unknown (or none) is the default."""
    if sample in ("1", "2", "3"):
        key = SAMPLES[int(sample) - 1]
    return MOMENTS.get(key or DEFAULT) or MOMENTS[DEFAULT]
