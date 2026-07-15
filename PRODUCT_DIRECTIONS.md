# Air Quality Dashboard — Product Directions

*A founder/PM view of where to take the Greenpoint household air + health coach next. Complements the phase plan in `ROADMAP.md`; framed by leverage, not sequence.*

## The wedge: be the coach, not the chart

Anyone can show PM2.5. The moat is the compounding loop of **personal sensors + logged symptoms + AI coaching** for a specific household. Everything below is scored by how much it deepens that loop or how reliably it delivers advice at the moment it matters.

## Where we are today

| | |
|---|---|
| **5** | Live data sources (AirGradient, Open-Meteo, NOAA HMS, Google Pollen, Anthropic) |
| **2** | Home sensors (indoor + outdoor) |
| **2** | Household profiles |
| **$0** | External API cost (excluding the LLM) |

Reactive today — data only shows when the app is open; no history, alerts, or symptom memory yet.

## Ideas worth adding

Nine candidates, grouped by when I'd ship them. Impact and Effort are subjective founder/PM estimates on a 1–10 scale (higher impact = more household value; higher effort = more build cost).

| Idea | What it unlocks | Impact | Effort | When |
|------|-----------------|:------:|:------:|------|
| **Data foundation** (cache + history DB) | Fast loads, lower API cost, and the stored history that trends and symptoms depend on | 7 | 4 | **Next** |
| **Daily plan + push alerts** | Turns a passive dashboard into a daily habit; reaches you before you head outside | 9 | 4 | **Next** |
| **Symptom logging + triggers** | Learns each person's real triggers over time — the defensible personal-data moat | 9 | 6 | **Next** |
| **Sensor health alerts** | Know instantly when a monitor drops offline or reads stale | 6 | 2 | Quick win |
| **Compound Health Score (0–100)** | One compounding number that gets smarter as symptom history accumulates | 7 | 3 | Soon |
| **Real-time window nudges** | "Open the window now" cues from the live indoor vs outdoor delta | 7 | 3 | Soon |
| **Next-day predictive planner** | Pre-plans tomorrow's best/worst windows from pollen + weather + BQE forecasts | 8 | 6 | Bet |
| **Smart-home actuation** | Closes the loop — auto-runs purifier/HVAC when a threshold is crossed | 8 | 7 | Bet |
| **Conversational air coach** | Ask Claude follow-ups grounded in your live sensor + context data | 6 | 5 | Bet |

**Leverage (impact ÷ effort), highest first:** Sensor health alerts (3.0) → Health Score (2.3) → Window nudges (2.3) → Daily plan + alerts (2.25) → Data foundation (1.75) → Symptom logging (1.5) → Predictive planner (1.33) → Conversational coach (1.2) → Smart-home actuation (1.14).

## Recommended next three

Sequenced so each unblocks the next: the data foundation makes alerts and symptom memory possible.

1. **Data foundation — cache + history DB**
   Fast loads, lower cost, and the history trends/symptoms need.
   *First step:* add an in-memory TTL cache for weather/pollen/smoke, then persist each reading + context snapshot to SQLite.

2. **Daily plan + push alerts**
   Turns a passive dashboard into a daily habit and reaches you before you go outside.
   *First step:* add a web-push subscription + a scheduled 7am "today's plan"; fire threshold alerts at PM2.5 > 35 and CO2 > 800.

3. **Symptom logging + trigger correlation**
   Learns each person's triggers — the moat.
   *First step:* ship one-tap symptom logging to the DB; after ~2 weeks, surface the first pollen / dew-point correlation.

**Quick win to slot in anytime:** sensor offline/health alerts — highest leverage, tiny effort.

## Bigger bets

Higher effort or newer surface area — pursue once the daily loop is sticky.

- **Close the loop — smart-home actuation.** Push insight into action: trigger the air purifier, HVAC, or a "close the windows" reminder via Home Assistant / HomeKit when PM2.5 or CO2 crosses a threshold. Add filter-life tracking from purifier runtime + measured particulate load. This is what separates a dashboard from a system that actually protects the home.
- **Predictive next-day planner.** Shift from reactive to proactive. Combine the Open-Meteo forecast, Google Pollen forecast, and learned BQE traffic patterns into a "tomorrow" view: best outdoor window, when to pre-run the purifier, and a heads-up the night before.
- **Conversational air coach.** Let each person ask Claude follow-ups grounded in their live sensor + context data ("is it safe for a toddler walk at 3pm?"), plus a weekly AI health review that reads symptom + environment history.
- **Beyond one household.** The neighborhood comparison already hints at a network. A shareable block view and "invite a neighbor" could seed growth before the full generalization work (location picker, profiles, custom thresholds) outlined as v5 in `ROADMAP.md`.

## The one metric to compound

A single personal **Health Score (0–100)** that gets more accurate as symptom logs accumulate. It ties the sensors, context, and coaching into one number a family checks daily — and it's the layer competitors can't copy without your data.
