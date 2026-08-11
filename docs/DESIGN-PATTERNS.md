# Design Patterns — What to Build & How It Should Look

**Last Updated:** April 10, 2026
**Sources:** IQAir, Plume Labs, Apple Health, AirScope, DailyBreath, Oura redesign (Instrument), NNG research

> **Attribution Note**: This document contains Claude's analysis, synthesis, and recommendations based on Perplexity deep research (market data, competitive intelligence), the dashboard codebase, competitors screenshots and Sacha's existing competitive landscape analysis. These are AI-generated interpretations; review and validate before making strategic decisions.

---

## Core Principle: 3-Tier Progressive Disclosure

From Oura's 2024 redesign (42% faster insight delivery):

```
TIER 1: GLANCE (0-2 sec)     Color dot + number + status label
TIER 2: CARD (2-10 sec)      Headline + metric + 1-3 short recommendations
TIER 3: DETAIL (on demand)   Chart + full explanation + sources
```

**Cardinal rule:** Never put Tier 3 content at Tier 1.

---



## A. Metric Card Anatomy

**Proven pattern (IQAir + Apple Health):**

```
┌────────────────────────────────┐
│  🫁  Air Quality (Indoor)     │  ← icon + label (13px muted)
│                                │
│  2.5 µg/m³                    │  ← hero value (1.2rem bold, colored)
│  ████████░░  Excellent        │  ← color bar + status label
│                                │
│  Filtering 73% of street dust │  ← benefit (13px, secondary)
└────────────────────────────────┘
```

**Specs:**

- Card height: 100-120px (consistent across all cards)
- Value font: 28-32px / 700 weight / colored by status
- Label: 11-13px / 500 weight / muted
- Benefit: 13px / 400 weight / secondary color
- Color bar: full width, 4px tall, fill proportional to severity
- Card padding: 16px
- Card gap: 10-12px

**Status → Color mapping:**


| Status               | Color  | Your CSS var        |
| -------------------- | ------ | ------------------- |
| Excellent/Good/Ideal | Green  | `--green: #22c55e`  |
| Fair/Moderate/Watch  | Yellow | `--yellow: #eab308` |
| Caution/Elevated     | Orange | `--orange: #f97316` |
| Poor/Critical/Severe | Red    | `--red: #ef4444`    |


---



## B. Health Score (Single Compound Number)

**Pattern source:** DailyBreath Perry Score, Apple Health rings

Combine Allergy Risk + Respiratory Load into one **Health Score (1-100)**:

- Display as gauge ring or arc (Apple Activity ring style)
- 48-64px diameter
- Color fills by score range
- This is THE number that compounds with symptom tracking

```
┌──────────────────────┐
│    ╭───╮             │
│   │ 78 │  Health     │
│    ╰───╯  Score      │
│                      │
│   Good · Updated 5m  │
└──────────────────────┘
```

---



## C. Recommendations (Not Numbered Lists)

**Pattern source:** Plume morning report, IQAir activity tags

**Before (current — numbered boxes):**

```
  ┌─ 1 ── Run outdoors 10am-2pm... ──┐
  ┌─ 2 ── Turn humidifier on by... ──┐
  ┌─ 3 ── Close windows 4-7pm... ────┐
```

**After (icon-prefix single lines):**

```
  🏃 Run outdoors 10am–2pm — lowest pollen + traffic
  💧 Turn humidifier on by 8pm tonight
  🪟 Close windows 4–7pm during BQE evening rush
```

**Rules:**

- Icon prefix per recommendation (activity-specific)
- Single line each, no boxes/cards
- Max 3 items
- No numbering (numbering implies sequence)
- Max 20 words per line

---



## D. Pollen Display

**Pattern source:** IQAir 3-day pollen forecast

**Before (text pills):** `[🌳 Tree: Moderate] [🌿 Grass: Low]`

**After (horizontal bars):**

```
  Tree   ████████░░  Moderate  (in season)
  Grass  ██░░░░░░░░  Very Low
  Weed   ░░░░░░░░░░  None
```

**Specs:**

- Bar width: 80px, height: 4px
- Fill proportional to index (0-5 scale)
- Color matches severity
- "(in season)" tag for active allergens
- Max 3-4 types before "show more"

---



## E. Activity Timing

**Pattern source:** Plume activity safety icons

Tie to Health profile tags (Runner, Toddler):

```
  🏃 Outdoor run    ✓ Safe now (10am-2pm window)
  👶 Park time      ⚠ Check pollen after 2pm
```

**Future:** Traffic-light timeline strip (IQAir hourly forecast):

```
  6am  ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██  6pm
       🟢 🟢 🟡 🟡 🟡 🟢 🟢 🟢 🟡 🟡 🔴 🔴
```

---



## F. Status Section

**Pattern source:** IQAir hero card

**Current:** Large icon + multi-line text + rank below
**Better:**

```
  ⚠ FAIR                    #4 of 11 nearby
  Sinuses clear — humidity perfect, pollen moderate
```

- Status word in large colored text, same line as icon
- Rank right-aligned
- Description below, normal weight, 1 line max

---



## G. Info Panel (Detail Sheet)

**Pattern source:** Apple Health detail view, Oura Tier 3

For "Learn more" / info icon taps:

- **Mobile:** Bottom sheet (slides up from bottom, 60% height)
- **Desktop:** Side panel or modal
- Contains: scoring thresholds, data sources, methodology, historical chart
- Never navigates away from dashboard

---



## H. Typography Hierarchy


| Element       | Size    | Weight | Color            | Line height |
| ------------- | ------- | ------ | ---------------- | ----------- |
| Section title | 0.8rem  | 600    | --text-muted     | 1.3         |
| Card headline | 0.82rem | 600    | --text           | 1.3         |
| Hero metric   | 1.2rem  | 700    | status color     | 1.1         |
| Body/benefit  | 0.75rem | 400    | --text-secondary | 1.4         |
| Label/caption | 0.65rem | 500    | --text-muted     | 1.4         |
| Status word   | 0.78rem | 700    | status color     | 1.0         |


---



## I. What to Steal per Competitor


| Competitor          | Steal                                                                  | Avoid                            |
| ------------------- | ---------------------------------------------------------------------- | -------------------------------- |
| **IQAir**           | Face emoji status, colored fills, pollen bar chart, hourly color strip | Desktop = stretched mobile       |
| **Plume**           | Morning report notification style, activity safety icons, half-gauge   | Dark-mode-only                   |
| **Apple Health**    | Consistent card height, colored category icons, Favorites + Edit       | Over-reliance on rings           |
| **AirScope**        | Species-level pollen, animated radar concept (future)                  | Feature-dumping without coaching |
| **DailyBreath**     | Perry Score → Health Score, symptom timeline, medication reminders     | Clinical UI, no warmth           |
| **AirGradient Map** | Cigarettes equivalent, WHO comparison, hourly heatmap                  | Info dump without hierarchy      |


---



## Implementation Priority


| #   | What                                            | Impact                          | Effort                               |
| --- | ----------------------------------------------- | ------------------------------- | ------------------------------------ |
| 1   | Color bars on metric cards                      | High (visual clarity)           | Low (CSS only)                       |
| 2   | Icon-prefix recommendations (no numbered boxes) | High (scannability)             | Low (JS template)                    |
| 3   | Pollen horizontal bars                          | Medium (better than pills)      | Low (CSS + JS)                       |
| 4   | Health Score (single compound number)           | High (moat)                     | Medium (scoring logic + ring visual) |
| 5   | Activity safety rows (Runner/Toddler)           | Medium (personalization)        | Low (JS template)                    |
| 6   | Info panel / bottom sheet                       | Medium (progressive disclosure) | Medium (CSS + JS overlay)            |
| 7   | Hourly AQ forecast strip                        | High (time-based planning)      | High (needs forecast data)           |


