# Air Quality Dashboard — Roadmap

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



## Roadmap at a Glance


| Phase      | Focus                                          | Scope                                            | Status              | Live Date           |
| ---------- | ---------------------------------------------- | ------------------------------------------------ | ------------------- | ------------------- |
| **v1**     | Core monitoring + basic AI                     | Greenpoint-specific                              | ✅ Done              | Apr 10 (main)       |
| **v1.5+**  | Weather + smoke + BQE + health scores          | Greenpoint + household aware                     | ✅ Done              | Apr 10 (v2 staging) |
| **v2**     | Google Pollen API + personalized for household | Sacha + Janet specific recommendations           | ✅ Done              | Apr 10 (v2 staging) |
| **v2.5**   | External data card layout                      | Visual cards for weather, pollen, BQE, smoke     | ✅ Done              | Apr 10 (v2 staging) |
| **v2.8**   | Server-side caching                            | Cache weather/pollen/smoke API calls             | ⏳ Not started       | TBD                 |
| **v3**     | Symptom tracking                               | Log symptoms → correlate with environment        | ⏳ Not started       | TBD                 |
| **v3.5**   | Trending & alerts                              | Historical comparisons, threshold notifications  | ⏳ Backlog           | TBD                 |
| **v3.75**  | Visual design overhaul                         | Color bars, health score, icon recs, pollen bars | ⏳ Not started       | TBD                 |
| **v4**     | Generalize for others                          | Location picker, user profiles, multi-household  | ⏳ Future            | TBD                 |
| **v5**     | Mobile UX, PWA, offline                        | Optimize for mobile + installable                | 🔶 Partial           | Apr 10 (basics)     |


---



## Completed Work



### ✅ Phase 1.5+: Weather & Context Integration

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



### ✅ Phase 2: Google Pollen API Integration

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



### ✅ Phase 2.5: External Data Card Layout

**Goal:** Make data sources visible and transparent (understand the *inputs* to AI recommendations)

**Shipped — "Local Conditions" cards below AI insights:**

- **🌍 Weather**: Wind direction + speed, dew point (sinus impact), visibility (particulate proxy), UV
- **🌳 Pollen**: Active allergens with risk levels (None → Extremely High colored pills)
- **🚗 BQE**: Current traffic intensity + peak times + pollution pressure score
- **🔥 Wildfire**: Smoke present/absent for Northeast (NOAA HMS) — status card only; map intentionally skipped

**Deferred polish:** pollen horizontal bars → Phase 3.75 D

**Result:** External inputs are visible next to AI narrative; builds trust without accounts or history

---



## Upcoming Phases (Greenpoint-First Strategy)



### Phase 2.8: Server-Side Caching (High Priority)

**Status:** ⏳ Not started — client `localStorage` caches AI insights (5 min TTL) only; no server-side TTL cache for weather/pollen/smoke or hash-keyed LLM responses.

**Goal:** Reduce redundant API calls, improve response time, lower cost

**Add:**

- Server-side cache for external API responses (weather, pollen, smoke) with TTL
  - Weather: cache 5 min (changes slowly)
  - Pollen: cache 1 hour (daily data, rarely changes intraday)
  - Smoke: cache 15 min (daily updates)
  - BQE: no cache needed (pure calculation, no API call)
- LLM analysis cache: hash sensor data + context → serve cached response if unchanged
  - Manual refresh button bypasses cache
  - Auto-refresh on significant data change only
- Simple in-memory dict with timestamp expiry (no Redis needed for single-instance)

**Why now:**

- Weather + pollen + smoke = 3 API calls per page load, every 60s = wasteful
- LLM calls are the most expensive (~$0.002 each)
- Single dict cache is trivial to implement, huge ROI

---



### Phase 3: Symptom Tracking + Trigger Correlation (High Priority)

**Status:** ⏳ Not started — no symptom UI, persistence, or correlation logic.

**Goal:** Let users log how they feel → correlate with environmental data over time → discover personal triggers

**Add:**

- Quick symptom input (tap-based, <5 sec): congested, dry sinuses, headache, tired, itchy eyes, clear
- Log stored in localStorage (later: server-side for persistence)
- Timestamp each entry → match against sensor + pollen + weather data at that moment
- After 2+ weeks of data: surface correlations ("You report congestion 3x more when tree pollen is Moderate+ AND humidity drops below 35%")
- Feed symptom history into LLM prompt for hyper-personalized recommendations
- Weekly digest: "This week: 4 congested days, all correlated with dew point <6°C"

**Why this is the moat:**

- <1% of 300M asthma sufferers use AQ apps — gap is personalization, not data
- AirRater (Australia) proved trigger detection drives retention
- Market analysis: "the compounding data layer is the defensible piece"
- Nobody else has personal sensor data + symptom logs + LLM coaching in one product

**UX pattern (from design research):**

- Floating action button or inline card: "How are you feeling?" 
- Quick emoji/tag selector: 😤 Congested · 🤧 Sneezy · 😫 Headache · 😴 Tired · ✓ Clear
- Optional: severity 1-3 tap
- Auto-dismiss after selection, no friction

---



### Phase 3.5: Trending & Alerts (Medium Priority)

**Status:** ⏳ Backlog — Chart.js history exists (1h/6h/24h/7d); no week-over-week comparison cards or threshold notifications.

**Goal:** Explain patterns, help predict problems before they happen

**Add:**

- Historical comparison ("Air improved 8% this week vs last week")
- Time-of-day patterns ("BQE traffic peaks at 7-9am + 4-7pm, pollen peaks 10am-4pm")
- Symptom trend overlay on environmental charts (see congestion spikes vs pollen/humidity)
- Seasonal insights ("Tree pollen season ends May 15 — 2 weeks remaining")
- Peer context ("You're in top 10% cleanest neighborhoods")
- Threshold alerts (PM2.5 > 35, CO2 > 800, humidity extremes)

**Why after symptom tracking:**

- Symptom data makes trends actionable ("you're congested on high-pollen mornings")
- Without symptoms, trending is just data visualization (commodity)
- 2+ weeks of symptom logs = enough for first correlation report

---



### Phase 3.75: Visual Design Overhaul (High Priority — Next)

**Status:** ⏳ Not started as a coherent overhaul — a few scraps exist; A–G below are still open.

**Goal:** Apply competitive best practices to match IQAir/Apple Health polish level

**Based on:** Competitive design analysis of IQAir, Plume, Apple Health, AirScope, DailyBreath

**A. Metric Cards — Color bars + visual hierarchy** — 🔶 Partial

- Some sensor metrics have thin bars; not the full IQAir card pattern (consistent height, bar + status label under every value)
- Add color bar under metric value (like AQI bars): ████████░░ Excellent
- Status label next to bar, colored by severity (green/yellow/orange/red)
- Consistent card height (100-120px)
- Value font: 1.2rem bold, colored by status
- Pattern source: IQAir mobile AQI card

**B. Health Score — Single compound number** — ❌ Not done

- Ring today shows PM2.5 µg/m³, not a compound 1–100 Health Score
- Combine Allergy Risk + Respiratory Load into one "Health Score" (1-100)
- Like DailyBreath's Perry Score but powered by personal sensors + LLM
- Display as gauge/ring visual (Apple Health style)
- This is the number that compounds with symptom tracking over time
- Pattern source: DailyBreath Perry Score, Apple Health rings

**C. Recommendations — Icon-prefix single lines** — ❌ Not done

- UI still uses numbered circles inside bordered boxes (opposite of target)
- Remove numbered list in boxes
- Switch to: 🏃 single line per recommendation, icon prefix
- Max 3 items, no boxes/cards around each one
- No numbering (implies sequence that doesn't exist)
- Pattern source: Plume morning report notifications

**D. Pollen — Horizontal bar chart** — ❌ Not done

- Still colored text pills; API returns `in_season` but UI does not render it
- Replace text pills with: Tree ████████░░ Moderate (in season)
- Color bars proportional to index (0-5), colored by severity
- "(in season)" tag for active allergens
- Pattern source: IQAir 3-day pollen forecast

**E. Activity Timing — Dedicated safety rows** — ❌ Not done

- Runner/Toddler are static profile tags only; timing lives in LLM copy, not UI rows
- Tie to Health profile tags (Runner, Toddler):
🏃 Outdoor run: ✓ Safe now (10am-2pm)
👶 Park time: ⚠ Check pollen after 2pm
- Pattern source: Plume activity safety icons

**F. Status Section — Compact single-line** — 🔶 Partial

- Colored status + description exist; rank is a second muted line, not right-aligned on the status row
- Status word (GOOD/FAIR/POOR) in large colored text, same line as icon
- Rank right-aligned on same line
- Status description below, normal weight
- Pattern source: IQAir hero card

**G. Info Panel — Bottom sheet for detail** — ❌ Not done

- `?` hover tooltips only — no "Learn more" bottom sheet
- "Learn more" links on cards open bottom sheet overlay
- Contains: scoring thresholds table, data sources, methodology
- Works on mobile (slide up) and desktop (slide from right or modal)
- Pattern source: Apple Health detail sheets, Oura 3-tier progressive disclosure

**Why now:**

- Current UI works functionally but looks unpolished vs competitors
- These are CSS + HTML changes, no backend work needed
- Polish drives trust — especially for health products
- IQAir/Apple Health patterns are proven by millions of users

---



### Phase 4: Generalize for Others (Lower Priority - Far Future)

**Status:** ⏳ Future — location/household hardcoded (Greenpoint + Sacha); Edit profile is "Coming soon".

**Goal:** Make the Greenpoint solution work for any location/household

**Add:**

- Location picker (detect user location or manual entry)
- User profiles: health conditions, activity level, schedule
- Household member management (add Sacha + Janet, or other people)
- Custom thresholds per location (Brooklyn different from Arizona)
- Customizable allergen preferences (care about birch vs not)
- Historical weather + pollen baselines by location

**Why much later:**

- v1/v2/v2.5/v3 solve the problem for *you* — validate that works first
- Generalizing requires user accounts, persistence, more complexity
- Better to optimize for Greenpoint specifically before building generic solution

**Estimate:** 6-8 hours (requires backend persistence, user management)

---



### Phase 5: Mobile UX & PWA (Lower Priority - Future)

**Status:** 🔶 Partial

**Goal:** Optimize for mobile devices + installable app

**Progress:**

- ✅ Responsive card layout (vertical stacking on <768px) — mostly done
- ❌ Neighborhood table → mobile-friendly cards — still a table/grid
- 🔶 PWA offline mode — `sw.js` network-first for APIs + static cache; not "past week" offline product; SW disabled on localhost
- 🔶 Installable — `manifest.json` + SW on deployed host; icons are inline SVG data URIs

**Still open:** neighborhood mobile cards, richer offline, localhost SW for local PWA testing

**Estimate remaining:** ~2–3 hours

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



## Success Metrics (v2 Launch)

✅ **AI prominence** — Insights at top, auto-analyze on data change  
✅ **Actionable intelligence** — Activity timing, filter alerts, household personalization  
✅ **External context** — Weather, smoke, pollen, traffic all integrated  
✅ **Health-focused UX** — Sinus-first language, symptom prevention, seasonal relief  
✅ **Code quality** — Single index.html, no duplicate files, clean git history  

**Next validation:** Share v2 with friends/family, gather feedback on usefulness of AI + Local Conditions cards

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
- v2 (through Phase 2.5) is live on production
- Later phases (2.8+) still open — see glance table

