import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { staleWhen, lerp, tipSide, hoursOf, fmtClock, shareOfLimit } = require('../static/summary.js');

test('when passed is dropped', () => {
  assert.equal(staleWhen({ when: 'before 4 PM', when_end: '2026-11-08T16:00:00-05:00' }, new Date('2026-11-08T16:05:00-05:00')), null);
  assert.equal(staleWhen({ when: 'before 4 PM', when_end: '2026-11-08T16:00:00-05:00' }, new Date('2026-11-08T15:40:00-05:00')), 'before 4 PM');
  assert.equal(staleWhen({ when: 'until under 55%', when_end: null }, new Date()), 'until under 55%');
  assert.equal(staleWhen({ text: 'x', when: null }, new Date()), null);
});

test('lerp outside range is null', () => {
  assert.equal(lerp([[1, 10], [2, 20]], 3), null);
  assert.equal(lerp([[1, 10], [2, 20]], 1.5), 15);
  assert.equal(lerp([], 1), null);
});

test('tip flips near the right edge', () => {
  assert.equal(tipSide(380, 400, 196), 'left');
  assert.equal(tipSide(40, 400, 196), 'right');
});

test('axis hours run past midnight', () => {
  const t0 = '2026-11-08T18:00:00-05:00';
  assert.equal(hoursOf(t0, t0), 18);
  assert.equal(hoursOf('2026-11-09T06:30:00-05:00', t0), 30.5);
});

test('clock to ten minutes', () => {
  assert.equal(fmtClock(15.5), '3:30 PM');
  assert.equal(fmtClock(24.99), '1:00 AM');
  assert.equal(shareOfLimit(1240, 800), 1.55);
});

const { profilesHeadHtml, itemProfileHtml } = require('../static/summary.js');
const PROFILES = [
  { id: 'toddler', name: 'Toddler', ok: false, state: 'Stale indoors', why: 'Stale air can make sleep lighter.' },
  { id: 'sinus', name: 'Sinus & allergy', ok: true, state: 'All fine', why: 'Humidity is fine.' },
  { id: 'runner', name: 'Runner', ok: null, state: 'No reading', why: 'No reading.' },
];

test('header shows the three profiles as icons, amber when not met', () => {
  const h = profilesHeadHtml(PROFILES);
  assert.equal((h.match(/<summary/g) || []).length, 3);
  assert.match(h, /sx-nh-i warn/); assert.match(h, /sx-nh-i ok/); assert.match(h, /sx-nh-i muted/);
  assert.match(h, /<strong>Sinus &amp; allergy: All fine\.<\/strong> Humidity is fine\./);
  assert.doesNotMatch(h, /Stale indoors<\/summary>/);   // icons only up top
  // each icon names its profile and state for screen readers and on hover
  assert.match(h, /aria-label="Toddler: Stale indoors" title="Toddler: Stale indoors"/);
  assert.match(h, /aria-label="Sinus &amp; allergy: All fine"/);
});

test('an item names its profile instead of the (i), and opens both sentences', () => {
  const h = itemProfileHtml({ profile: 'toddler', why: 'Above 800 the air feels stale.' }, PROFILES);
  assert.match(h, /sx-nchip warn/); assert.match(h, /Stale indoors/);
  assert.match(h, /Above 800 the air feels stale\.<span class="sx-nl"><strong>Toddler:<\/strong> Stale air/);
  assert.doesNotMatch(h, /r="6\.5"/);
});

test('an item without a profile keeps the (i)', () => {
  assert.match(itemProfileHtml({ why: 'Why.' }, PROFILES), /r="6\.5"/);
  assert.equal(itemProfileHtml({ profile: 'toddler' }, PROFILES), '');
});

const { fitLabel, rhLabelY, peakAhead, rewire } = require('../static/summary.js');

test('a label that would run past the chart flips to end before its point', () => {
  assert.deepEqual(fitLabel(100, 'PM2.5 outside 22', 368), { x: 108, anchor: 'start' });
  const f = fitLabel(300, 'PM2.5 outside 22 · BQE rush', 368);
  assert.equal(f.anchor, 'end'); assert.equal(f.x, 292);
});

test('the humidity label moves clear of the CO2 label', () => {
  assert.equal(rhLabelY(null, 50), 64);            // no CO2 label above its dot: under the humidity dot
  assert.equal(rhLabelY(20, 80), 94);              // far apart: unchanged
  const y = rhLabelY(43, 36);                      // humidity dot just above the CO2 label: would overlap
  assert.ok(Math.abs(y - 43) >= 12);
});

test('the PM2.5 peak label only looks at the outlook hours', () => {
  const past = [[10, 3]], fc = [[11, 5], [14, 12], [19, 30]];
  assert.deepEqual(peakAhead(past, fc, 10.5, 8), [14, 12]);   // 19 is past now + 8
  assert.deepEqual(peakAhead(past, fc, 10.5, 9), [19, 30]);
  assert.equal(peakAhead([], [], 10, 8), null);
});

test('each redraw drops the previous listeners', () => {
  const card = {};
  const a = rewire(card), b = rewire(card);
  assert.equal(a.aborted, true); assert.equal(b.aborted, false);
});

const { kickHtml } = require('../static/summary.js');
test('the card header can leave its label to the page', () => {
  assert.match(kickHtml('Today', PROFILES), /<span>Today<\/span>/);
  const h = kickHtml('Today', PROFILES, false);
  assert.doesNotMatch(h, /Today/); assert.match(h, /sx-nh/);
});

test('demo clock advances from the moment', () => {
  const { appNow } = require('../static/summary.js');
  const realNow = Date.now;
  try {
    delete globalThis.APP;
    assert.ok(Math.abs(appNow() - realNow()) < 1000);   // a real home: the real clock
    globalThis.APP = { now: { at: '2026-04-21T07:45:00-04:00', moment: 'rush', moments: [] } };
    const start = realNow();
    Date.now = () => start + 3 * 3600e3;   // the tab has been open three hours
    const now = appNow();
    assert.ok(Math.abs(now - Date.parse('2026-04-21T10:45:00-04:00')) < 5000);
    // a "when" that passed meanwhile is dropped, as it is live
    assert.equal(staleWhen({ when: 'after 10:30 AM', when_end: '2026-04-21T10:30:00-04:00' }, now), null);
    assert.equal(staleWhen({ when: 'until 11 AM', when_end: '2026-04-21T11:00:00-04:00' }, now), 'until 11 AM');
  } finally {
    Date.now = realNow;
    delete globalThis.APP;
  }
});

test('demo readings stay fresh while the tab stays open', () => {
  const { readingsNow, appNow } = require('../static/summary.js');
  const { freshness } = require('../static/home.js');
  const realNow = Date.now;
  try {
    delete globalThis.APP;
    assert.ok(Math.abs(readingsNow() - realNow()) < 1000);   // a real home: readings age with the real clock
    assert.equal(freshness({ timestamp: new Date(realNow() - 30 * 60e3).toISOString() }, readingsNow()).label, 'Late · 30 min');
    globalThis.APP = { now: { at: '2026-04-21T07:45:00-04:00', moment: 'rush', moments: [] } };
    const start = realNow();
    Date.now = () => start + 3 * 3600e3;   // three hours later
    assert.equal(+readingsNow(), Date.parse('2026-04-21T07:45:00-04:00'));   // the demo's readings are from its moment
    assert.ok(appNow() > readingsNow());                                       // while its clock moves on
    assert.equal(freshness({ timestamp: '2026-04-21T11:45:00.000Z' }, readingsNow()).label, 'Online');
    assert.equal(freshness(null, readingsNow()).label, 'Offline');
  } finally {
    Date.now = realNow;
    delete globalThis.APP;
  }
});

test('the summary chart writes temperatures in the page\'s unit (°C alone, the page\'s fmtTemp when it is there)', () => {
  const { tempText } = require('../static/summary.js');
  assert.equal(tempText(14.4), '14°C');   // without the page (a test, or before app.js): °C, as the readings arrive
  globalThis.fmtTemp = (c, o) => `${Math.round(c * 9 / 5 + 32)}°F${o && o.tight ? '' : ''}`;
  try { assert.equal(tempText(14), '57°F'); } finally { delete globalThis.fmtTemp; }
  const src = require('node:fs').readFileSync(new URL('../static/summary.js', import.meta.url), 'utf8');
  assert.doesNotMatch(src, /°C<\/text>|\+ '°C', u:/);   // no °C written by hand (Sacha's demo showed 59°F above a chart in °C)
});
