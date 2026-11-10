# Design

How the page looks and behaves, for anyone (or any agent) changing it. Values live in the code; this file holds the rules the code can't tell you.

## Principles

- **Actions first.** The page says what to do and when; every reading comes with its why.
- **Plain and calm.** Plain words (AGENTS.md, "Copy"), no decoration for its own sake, no marketing.
- **Honest data.** Say where a number comes from (a monitor, a public monitor, an estimate) and when it's missing; never invent a value.

## Where things live

- **Colors and surfaces** are tokens on `:root` in `static/app.css`, with a light and a dark set. Use the tokens, never a raw color. The ones that carry meaning:
  - `--good`, `--warn`, `--bad`: how good or bad a reading is. Only for meaning, never decoration.
  - `--series-in`, `--series-out`: indoor and outdoor, everywhere they're drawn (charts, labels, cards).
  - `--accent`: controls, links and focus.
- **Type:** Inter, from the page's own stylesheet; reuse the sizes of the nearest existing component.
- **Spacing and corners:** no scale to learn; copy the component next to yours.

## Cards

- A card is a header (what it is, where it comes from, its status), one main reading, the details, then the why.
- **A missing or disabled part** (no indoor monitor, a source turned off) is the same card on its solid background, its contents greyed and lightened, with one plain line on why. No dashed outline, no see-through card, no setup pitch.
- **No colored card edges or stripes**, top or left.
- Estimates say so ("Estimate for your area"); forecast values are marked as forecast (the striped key, like the chart's forecast area).

## Charts

- Readings as lines, forecasts hatched, the limit as one dashed line. Indoor and outdoor in their series colors.
- Label the line, not a legend far away.

## The live sky

- The sky behind the header follows the weather and time of day. Text over it must stay readable: the header's ink follows the sky's brightness (`static/sky.js`). Check new header text over a bright fog and a night sky.

## Motion

- Short and purposeful (a change you need to notice, a small delight on tap). Nothing under `prefers-reduced-motion`. No layout shift.

## Before you ship a change to the page

- Both themes, and a phone at 390 px wide (no sideways scroll).
- Contrast at least 4.5:1 for text, focus rings on everything you can tab to, labels on controls.
- Screenshots of the demo stories (`?moment=rush`, `clear`, `humid`) before and after, compared side by side (`scripts/screenshot.sh`).
- A change to the token page or setup also compares `scripts/setup_shots.sh` screenshots before and after.
- `pytest -q && node --test tests/*.test.mjs`.
