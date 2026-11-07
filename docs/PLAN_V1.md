# Air Quality Dashboard — Plan v1

> **Attribution Note**: This document contains Claude's analysis, synthesis, and recommendations based on Perplexity deep research (market data, competitive intelligence), the dashboard codebase, and Sacha's existing competitive landscape analysis. Market figures are sourced from industry reports cited inline. These are AI-generated interpretations; review and validate before making strategic decisions.

> **Note Sacha: this was an experiment mainly one-shotted by Claude - don't take it too seriously :)**

## Vision

**Phase 1 (Now):** Build the most useful air quality dashboard for **your family living in Greenpoint, Brooklyn**. Not just data, but actionable intelligence that helps you both breathe better — combining AirGradient sensor data with hyper-local context (weather, traffic, pollen, wildfire smoke).

**Phase 2+ (Future):** Generalize the approach for other people and locations (customizable thresholds, user preferences, location picker, household member profiles).

---



## The Problem We're Solving

- AirGradient shows sensor data but lacks **context** (Why is air bad? What do I do?)
- Generic health scores don't explain **Greenpoint-specific drivers**:
  - BQE pollution peaks (7-9am morning rush, 4-7pm evening rush)
  - Wind direction drift (west winds push pollution toward your home)
  - Seasonal allergen peaks (April=birch, June-Aug=grass/mold, Aug-Oct=ragweed)
  - Humidity/dew point sinus impact (dry air triggers sinus dryness)
  - Wildfire smoke (affects respiratory health)
- No personalization (both household members have different sensitivities)
- No trending insights or proactive alerts

---



## The Solution (v2+)

**AI as the health coach + external context layer.**

Instead of just showing metrics, the dashboard:

1. **Pulls external data** (weather, pollen, traffic, smoke) via free APIs
2. **Calculates health scores** (Allergy Risk 1-10, Respiratory Load 1-10)
3. **Claude narrates a story**:
  ```
   🟢 Your sinuses are clear (humidity 43%) — outdoor tree pollen is moderate

   ⏰ BEST WINDOW: 7-9am (low pollen, low BQE traffic)
   ⚠️  AVOID: 10am-4pm (pollen peaks with traffic surge)

   💡 Action: If dry throat at bedtime, run humidifier 1-2h before sleep
   📅 Relief: Tree pollen drops 70% by late May
  ```

---



## Plan Summary

v1 is the first batch of work, done in April 2026. It covers what the original plan called phases 1.5, 2 and 2.5.

| Version | Focus | Scope | Status | Live date |
| ------- | ----- | ----- | ------ | --------- |
| **v1** | Core monitoring, AI insights, local context, household personalization | Sensors and basic AI; weather, smoke, BQE estimate and health scores; Google Pollen with per-person recommendations; Local Conditions cards | ✅ Done | Apr 10, 2026 |

The work after v1 is planned in a separate roadmap.

---



## Completed Work: v1 (April 2026) ✅



### Weather & context integration

**Open-Meteo (Free API)**

- Wind direction (cardinal + degrees) for pollution drift prediction
- Dew point (°C) for sinus dryness risk
- Visibility (m) for particulate concentration
- UV index + 24h hourly forecast

**NOAA HMS (Free API)**

- Wildfire smoke detection in Northeast region
- Alert inclusion when smoke present

**BQE Traffic Prediction**

- Time-based intensity: 7-9am peak (1.5x), 4-7pm peak (1.4x), low hours (0.7x)
- Wind impact: West winds +1.3x (toward home), East winds -0.5x (away)
- Combined pollution pressure score

**Composite Health Scores (1-10)**

- **Allergy Risk**: Mold risk (humidity >60%), sinus dryness (dew point <10°C), particulates (visibility <2km)
- **Respiratory Load**: PM2.5 + CO2 + visibility averaged

**Result:** LLM now aware of WHY air is good/bad + personalized activity timing

---



### Google Pollen API integration

**Real-Time Pollen Data**

- Birch, Oak, Grass, Ragweed + custom allergens (species level)
- Risk levels: None → Extremely High
- Per-household member recommendations
  - "Sacha: Tree pollen high — avoid 10am-4pm outdoor time"
  - "Janet: PM2.5 fair — mask during 7-9am walk"

**LLM Personalization**

- Household members have different sensitivities
- Activity timing accounts for both pollen + traffic + dew point
- Saline/humidifier recommendations based on dew point + humidity
- Seasonal relief messaging (when does this season end?)

**Result:** Hyper-specific, actionable recommendations for sinus health

---



### External data card layout

**Goal:** Make data sources visible and transparent (understand the *inputs* to AI recommendations)

**Shipped — "Local Conditions" cards below AI insights:**

- **🌍 Weather**: Wind direction + speed, dew point (sinus impact), visibility (particulate proxy), UV
- **🌳 Pollen**: Active allergens with risk levels (None → Extremely High colored pills)
- **🚗 BQE**: Current traffic intensity + peak times + pollution pressure score
- **🔥 Wildfire**: Smoke present/absent for Northeast (NOAA HMS) — status card only; map intentionally skipped

**Result:** External inputs are visible next to AI narrative; builds trust without accounts or history

---



## Data Sources Reference


| Source                 | API        | Cost           | Data                                   | Freshness       |
| ---------------------- | ---------- | -------------- | -------------------------------------- | --------------- |
| **AirGradient**        | REST       | Free tier      | Indoor/outdoor PM, CO2, temp, humidity | Real-time       |
| **Open-Meteo**         | REST       | Free           | Wind, dew point, visibility, UV        | Real-time + 24h |
| **NOAA HMS**           | Web scrape | Free           | Wildfire smoke regions                 | Daily           |
| **Google Pollen**      | REST       | Free           | Pollen types + indices (0-5)           | Real-time       |
| **Anthropic (Claude)** | REST       | $0.002/analyze | LLM analysis + personalization         | Per-call        |


**Total external API cost: $0 (except Claude)**

---



## Success Metrics (v1 Launch)

✅ **AI prominence** — Insights at top, auto-analyze on data change  
✅ **Actionable intelligence** — Activity timing, filter alerts, household personalization  
✅ **External context** — Weather, smoke, pollen, traffic all integrated  
✅ **Health-focused UX** — Sinus-first language, symptom prevention, seasonal relief  
✅ **Code quality** — Single index.html, no duplicate files, clean git history  

**Next validation:** Share v1 with friends/family, gather feedback on usefulness of AI + Local Conditions cards

---



## Questions for User Feedback

1. **External data cards:** Are the Local Conditions cards clear enough, or too much noise under AI insights?
2. **Activity timing window:** Is 10am-3pm too conservative, or right for Greenpoint?
3. **Household personalization:** Does per-person pollen + PM recommendations feel useful, or overkill?
4. **Alerts:** Would you want notifications when thresholds hit (PM2.5 > 35, CO2 > 800)?
5. **Historical context:** Would weekly trend cards ("Air improved 10% vs last week") be useful?

---



## Deployment Path

**Current:** `feature/*` → `dev` (staging) → `main` (production)

- Staging: https://air-quality-dashboard-dev.up.railway.app/
- Production: https://air-quality-dashboard.up.railway.app/
- v1 shipped to production in April 2026
- Later work is planned in the roadmap

