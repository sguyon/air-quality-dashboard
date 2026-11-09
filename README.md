# Home Air Quality

A page for AirGradient owners that tells you what to do about your air, not just what it reads.

I have two AirGradient monitors at home, one inside and one outside. AirGradient's dashboard shows their readings well, but it doesn't connect them to what changes their meaning: the weather, the pollen season, rush hour on the expressway a kilometer away. And it doesn't say what to do about any of it.

So I built a page that does. It combines the two monitors with the weather, the PM2.5 forecast, pollen, wildfire smoke and nearby public monitors, and turns them into a few actions, each with a short why: air the apartment now, before the rush-hour fumes arrive; keep the windows shut, tree pollen is high; skip the run this morning. It weighs everything against what my household cares about: a toddler's sleep, sinus allergies, and running.

The actions come from a small set of plain rules, not an AI model. My first version had a model write them, but it kept suggesting the same few things, so I turned each action it could suggest into a fixed rule. I plan to try AI again for patterns across weeks of readings.

It's also meant to be nice to check. The background can follow the real sky outside, with sun, clouds, rain and haze (my toddler loves playing with it), or stay plain. It works in a desktop browser, and on a phone you can add it to your home screen and open it like an app.

**Demo:** https://homeair.guyon.dev

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/hero-dark.png">
    <img src="docs/hero-light.png" alt="Home Air Quality on a laptop and a phone: the morning's actions, the needs and the day chart" width="800">
  </picture>
</p>

The demo and every screenshot here use made-up data for a made-up home, not real readings.

## What it does

- **Readings with an action and a why.** CO₂ and humidity inside, PM2.5 and pollen outside: each reading that needs something gets an action ("Open a window for 10 min", "Keep windows shut") and one line on why.
- **Three needs.** A toddler (CO₂ and the air at sleep time), sinus and allergy (humidity and pollen) and a runner (outdoor PM2.5, smoke and the road's rush hours). Each need says whether it's met right now.
- **A day chart.** CO₂, humidity and outdoor PM2.5 through the day, with the PM2.5 forecast for the hours ahead, so you can see when the air clears.
- **A map.** Your outdoor monitor against public AirGradient monitors within 15 km, and, if you set one, a busy road nearby with its exhaust drawn when the wind blows it toward you.
- **A live sky, and an app on your phone.** The background follows the real sun, clouds, rain and haze, or stays plain. On a phone, add the page to your home screen and it opens full screen.

## Set it up for your home

**Who it's for:** someone with an indoor and an outdoor AirGradient monitor connected to AirGradient's cloud, and a coding agent (Claude Code, Codex, Cursor or similar). The agent does the setup; you answer a few questions and type your keys yourself.

**What you need:**

- your AirGradient API token (from the AirGradient dashboard);
- Python 3.11 or newer, or [uv](https://docs.astral.sh/uv/);
- optional: a Google Cloud project with billing turned on, for pollen (the free tier covers it);
- optional, to put it online: a Railway account.

**Ask your agent**, from a copy of this repo:

> Set up Home Air Quality for my home by following SETUP.md. Ask me for my address and which needs I care about; never ask me to paste a key into the chat.

- [`SETUP.md`](SETUP.md): the steps your agent follows to set up and run it on your computer.
- [`DEPLOYMENT.md`](DEPLOYMENT.md): how to put it online.

Without a token, a fresh copy opens the demo, so you can try it before setting anything up: `uv run --with-requirements requirements.txt server.py`, then open http://localhost:5555.

## Known limits

- **US only.** Smoke (NOAA) and the forecast and pollen links are US sources. Outside the US you can turn them off; nothing else is adapted.
- **One home per copy.** One indoor and one outdoor monitor, one household.
- **AirGradient's cloud.** The page reads your monitors through AirGradient's API with your token, not from the monitors on your network.
- **The humidity action assumes your appliances.** When a room is too damp, it says to run a dehumidifier or the AC's dry mode. The rules don't know which appliances you have yet.
- **No road for new homes yet.** The road and its exhaust need a route file traced along the road, and nothing in the repo builds one yet. The demo has one; new homes start without.

## How it decides

The actions come from fixed rules in `summary.py` and `server.py`, not a model. The limits they use are in your `config.toml` under `[limits]`: indoor CO₂ 800 ppm, outdoor PM2.5 15 and 35 µg/m³, indoor humidity 30% (dry) and 60% (damp), pollen level 3 of 5. Change them there. The comments in [`config.example.toml`](config.example.toml) say what each one does.

## The whole page

<p align="center">
  <img src="docs/screenshot.png" alt="The full Home Air Quality page from the demo: today's actions, the needs, the day chart, the home monitors, local conditions and the neighborhood map" width="720">
</p>

## Data and credits

- Your monitors, and the nearby public monitors: [AirGradient](https://www.airgradient.com). Nearby monitors' data is licensed under [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); the page credits each monitor's contributor when it has one.
- Weather and the PM2.5 forecast: [Open-Meteo](https://open-meteo.com).
- Pollen: [Google Pollen API](https://developers.google.com/maps/documentation/pollen) (optional, needs a key).
- Wildfire smoke: NOAA's [Hazard Mapping System](https://www.ospo.noaa.gov/products/land/hms.html).
- Map: [MapLibre](https://maplibre.org), with tiles from [OpenFreeMap](https://openfreemap.org) and map data from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Device frames in the screenshot: [Devices.css](https://github.com/picturepan2/devices.css) (MIT, `scripts/vendor/`).

## Issues and contributing

Questions, bugs and ideas are welcome as GitHub issues. Never paste a token or key in an issue or pull request, even a partial one. To report a security problem, see [`SECURITY.md`](SECURITY.md).

Pull requests: install `requirements-dev.txt` (`pip install -r requirements-dev.txt`), run `pytest -q` and `node --test tests/` first, and keep your `config.toml`, `.env` and readings out of the diff. Agents working on the code read [`AGENTS.md`](AGENTS.md).

## License

[MIT](LICENSE)
