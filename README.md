# <img src="static/icons/icon.svg" alt="" width="36" height="36" align="middle"> Home Air Quality

A page for your AirGradient air monitors that tells you what to do about your air: when to open the window, when to keep it shut, when to go for a run. It combines your readings with public data sources: the weather and PM2.5 forecast (Open-Meteo's [weather](https://open-meteo.com/en/docs) and [air quality](https://open-meteo.com/en/docs/air-quality-api) APIs), pollen ([Google](https://developers.google.com/maps/documentation/pollen)), wildfire smoke ([NOAA](https://www.ospo.noaa.gov/products/land/hms.html)) and nearby public AirGradient monitors ([AirGradient's map](https://www.airgradient.com/map/)), plus an estimate of rush-hour traffic on a road near you.

**[Try the demo](https://homeair.guyon.dev)** · [Demo](#demo) · [Installation](#installation) · [Features](#features)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/hero-dark.png">
    <img src="docs/hero-light.png" alt="Home Air Quality on a laptop and a phone" width="800">
  </picture>
</p>

<sub>The screenshots use sample data from an example home.</sub>

## Demo

[The demo](https://homeair.guyon.dev) has three samples (1, 2, 3): an example home in Williamsburg, Brooklyn, with made-up readings: a morning rush, an all-clear afternoon and a humid evening. Its banner also opens any public AirGradient outdoor monitor (Pick a monitor, or `?monitor=<id>`): that monitor's live readings from [AirGradient's public map](https://www.airgradient.com/map/), with the weather, the PM2.5 forecast and the monitors around it.

## Installation

You need an indoor and an outdoor AirGradient monitor on AirGradient's cloud, and your API token. US only for now.

**With a coding agent** (Claude Code, Codex, Cursor). Clone this repo, open it with your agent, and paste:

```
Set up Home Air Quality for my home by following SETUP.md. Ask me for my address and which needs I care about; never ask me to paste a key into the chat.
```

It asks a few questions, writes your config and runs the page on your computer, then can put it online ([`DEPLOYMENT.md`](DEPLOYMENT.md)).

**With Docker,** on a home server or NAS: copy `config.example.toml` to `config.toml` and fill it in, put your token in `.env`, then run `docker compose up -d` and open http://localhost:8000. [Details](DEPLOYMENT.md#docker).

**Just trying it?** A fresh copy with no token opens the demo: `uv run --with-requirements requirements.txt server.py`, then http://localhost:5555.

## Features

- **An action and a why for each reading that needs one.** CO₂ and humidity inside, PM2.5 and pollen outside: "Open a window for 10 min", "Keep windows shut", with one line on why.
- **Your household's needs.** A toddler's sleep (CO₂), sinus and allergies (humidity and pollen), a runner (outdoor PM2.5, smoke and rush hour). Each says whether it's met right now. Pick the ones that apply.
- **A day chart** of CO₂, humidity and outdoor PM2.5, with the forecast for the hours ahead, so you see when the air clears.
- **A forecast tuned to your street.** Open-Meteo's PM2.5 forecast covers a wide area, so the app compares its last 24 hours with your outdoor monitor and scales the next hours to match. That's how the page can tell you *when*: 'Windows shut until 11 AM', 'Run after 11 AM'.
- **A map** of your outdoor monitor against public AirGradient monitors nearby, and a busy road's exhaust when the wind blows it your way.
- **Live weather animations and a phone app.** The background follows the real sun, clouds, rain and haze, or stays plain. Add it to your phone's home screen and it opens full screen.

## Why I built it

I have two AirGradient monitors at home, one inside and one outside. AirGradient's dashboard shows their readings well, but it doesn't say what to do about them, and the rest of what matters lives in other apps: the weather, the pollen season, rush hour on the expressway a kilometer away. I wanted one place to know everything about the air at home and what to do about it, weighed against what my household cares about: a toddler's sleep, sinus allergies, and running. My toddler also loves playing with the live weather animations :)

The actions come from a small set of plain rules, not an AI model. My first version had a model write them, but it kept suggesting the same few things, so I turned each action it could suggest into a fixed rule. I plan to try AI again for patterns across weeks of readings.

## Limitations

- **Works best in the US.** Wildfire smoke (NOAA) and the forecast and pollen links use US sources. Elsewhere, turn those off in `config.toml`: your monitors' readings, the actions, the weather and the PM2.5 forecast still work.
- **One indoor and one outdoor monitor.** No rooms or several monitors of the same kind yet.
- **AirGradient's cloud.** The page reads your monitors through AirGradient's API with your token, not from the monitors on your network.
- **No road for new homes yet.** The road and its exhaust need a route file traced along the road, and nothing in the repo builds one yet. The demo has one; new homes start without.

## How it works

The actions come from fixed rules in `summary.py` and `server.py`, not a model. Each rule compares a reading with a limit from your `config.toml` (`[limits]`). The defaults, and why:

| Limit | Default | Why |
|---|---|---|
| CO₂ inside | 800 ppm | About twice the outdoor level (around 420). Above it the room is short on fresh air, and it starts to feel stuffy; guidelines put the line between 800 and 1,000. |
| PM2.5 outside | 15 µg/m³ | The World Health Organization's guideline for a 24-hour average. Used here for any hour, so it's strict on purpose. |
| PM2.5 outside, high | 35 µg/m³ | The US EPA's 24-hour standard. Above it, sensitive people (children, asthma) should keep time outside short. |
| Humidity inside | 30–60%, comfortable up to 50% | Under 30% dries the nose and throat; over 60% helps mold and dust mites grow. The damp-room action stops at 55%. |
| Pollen | 3 of 5 | "Moderate" on Google's pollen index, where people with allergies start to feel it. |

Change any of them in `config.toml`; the comments in [`config.example.toml`](config.example.toml) say what each one does.

### The PM2.5 forecast

The server asks [Open-Meteo's Air Quality API](https://open-meteo.com/en/docs/air-quality-api) (free, no key) for hourly PM2.5 at the home, the past 24 hours and the next 24, and keeps the answer 30 minutes. For each past hour it compares your outdoor monitor's average with the forecast and takes the median ratio, kept between ×0.1 and ×3, so one odd hour doesn't sway it; the coming hours are multiplied by it. With fewer than 6 matching hours it starts the forecast from the monitor's reading now instead, and the gap fades over 6 hours. The actions look 8 hours ahead on that curve for when PM2.5 crosses the limit.

### Corrected PM2.5

AirGradient monitors measure particles with a laser sensor (Plantower) that reads high, more so in humid air, where particles swell with water. The US EPA compared these sensors with reference stations and published a correction that uses humidity and the sensor's non-linear response at high levels ([Barkjohn et al. 2021](https://amt.copernicus.org/articles/14/4617/2021/)). AirGradient applies it and sends the corrected value next to the raw one (`pm02_corrected` in [its API](https://api.airgradient.com/public/docs/api/v1/)); its [EGU25 abstract](https://meetingorganizer.copernicus.org/EGU25/EGU25-8701.html) describes the correction on its monitors. The app uses the corrected value whenever there is one (your monitors, the public monitors' history from AirGradient's map, and, computed with the same formula, a public monitor's reading now), so the limits compare like with like.

## Screenshots

<p align="center">
  <img src="docs/screenshot.png" alt="The full Home Air Quality page from the demo: today's actions, the needs, the day chart, the home monitors, local conditions and the neighborhood map" width="720">
</p>

## Credits

- Your monitors, and the nearby public monitors: [AirGradient](https://www.airgradient.com) ([API](https://api.airgradient.com/public/docs/api/v1/), [public map](https://www.airgradient.com/map/)). Nearby monitors' data is licensed under [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); the page credits each monitor's contributor when it has one.
- Weather and the PM2.5 forecast: [Open-Meteo](https://open-meteo.com) ([Weather API](https://open-meteo.com/en/docs), [Air Quality API](https://open-meteo.com/en/docs/air-quality-api)).
- Pollen: [Google Pollen API](https://developers.google.com/maps/documentation/pollen) (optional, needs a key).
- Wildfire smoke: NOAA's [Hazard Mapping System](https://www.ospo.noaa.gov/products/land/hms.html).
- Map: [MapLibre](https://maplibre.org), with tiles from [OpenFreeMap](https://openfreemap.org) and map data from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Device frames in the screenshot: [Devices.css](https://github.com/picturepan2/devices.css) (MIT, `scripts/vendor/`).

## Contributing

Questions, bugs and ideas are welcome as GitHub issues. Never paste a token or key in an issue or pull request, even a partial one. To report a security problem, see [`SECURITY.md`](SECURITY.md).

Pull requests: install `requirements-dev.txt` (`pip install -r requirements-dev.txt`), run `pytest -q` and `node --test tests/` first, and keep your `config.toml`, `.env` and readings out of the diff. Agents working on the code read [`AGENTS.md`](AGENTS.md).

## License

[MIT](LICENSE)
