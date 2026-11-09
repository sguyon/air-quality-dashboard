// The page's wiring: index.html uses the new summary card, and every bare function call in app.js is defined
// in one of the page's scripts or is a browser global.
// Found by the branch review: two calls to deleted functions (renderAgenda, renderActionVis) broke the refresh loop.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const root = new URL('../', import.meta.url);
const strip = s => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:\\])\/\/.*$/gm, '$1')
  .replace(/'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"/g, "''");
const files = ['static/app.js', 'static/sky.js', 'static/summary.js', 'static/home.js'].map(f => strip(readFileSync(new URL(f, root), 'utf8')));
const all = files.join('\n');

const declared = new Set();
const add = x => x && declared.add(x.replace(/^\.\.\./, '').replace(/=.*/, ''));
for (const m of all.matchAll(/\b(?:function\s*\*?\s*|const\s+|let\s+|var\s+|class\s+)([A-Za-z_$][\w$]*)/g)) add(m[1]);
for (const m of all.matchAll(/\b(?:const|let|var)\s*[{[]([^=]*?)[}\]]\s*=/g)) m[1].split(/[,:\s]+/).forEach(add);
for (const m of all.matchAll(/function\s*[\w$]*\s*\(([^)]*)\)|\(([^()]*)\)\s*=>|([A-Za-z_$][\w$]*)\s*=>/g)) (m[1] ?? m[2] ?? m[3]).split(/[,\s{}=[\]]+/).forEach(add);
for (const m of all.matchAll(/[{,]\s*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/g)) add(m[1]);   // method shorthand: get() { … }

const GLOBALS = new Set(('if for while switch catch return typeof new function await async import require super ' +
  'setTimeout clearTimeout setInterval clearInterval requestAnimationFrame fetch getComputedStyle matchMedia ' +
  'Number String Boolean Object Array Date Math JSON Promise Set Map WeakMap Symbol Proxy Reflect Error RegExp ' +
  'parseFloat parseInt isNaN isFinite encodeURIComponent decodeURIComponent structuredClone queueMicrotask btoa atob ' +
  'Intl URL URLSearchParams IntersectionObserver ResizeObserver MutationObserver PointerEvent alert confirm ' +
  // not code: CSS functions inside template strings, and a word inside a regex
  'calc var Yesterday').split(' '));

test('app.js calls only functions that exist', () => {
  const missing = new Set();
  for (const m of files[0].matchAll(/(^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/g)) if (!declared.has(m[2]) && !GLOBALS.has(m[2])) missing.add(m[2]);
  assert.deepEqual([...missing], []);
});

test('the page uses the new summary card, not the old headline and need cards', async () => {
  const { readFile } = await import('node:fs/promises');
  const html = await readFile(new URL('index.html', root), 'utf8');
  assert.match(html, /id="summary"/);
  assert.doesNotMatch(html, /id="s-cards"/);
  assert.doesNotMatch(html, /id="lead"/);
});

// Everything about the home comes from the server's config (window.APP), never from the page's own files.
test('no home is hardcoded in the page', async () => {
  const { readdir, readFile } = await import('node:fs/promises');
  const files = ['index.html', ...(await readdir(new URL('static/', root))).filter(f => f.endsWith('.js')).map(f => 'static/' + f)];
  const found = [];
  for (const f of files) {
    const text = await readFile(new URL(f, root), 'utf8');
    for (const s of ['Greenpoint', '40.73', '-73.95', 'America/New_York', '11222', 'Blowing toward']) if (text.includes(s)) found.push(`${f}: ${s}`);
  }
  assert.deepEqual(found, []);
});

// The road helpers app.js, sky.js and map.js share (static/home.js).
const require = createRequire(import.meta.url);
const home = require('../static/home.js');
const BQE = { name: 'BQE', kind: 'expressway', toward: [80, 200], rush: [[7, 10, 'morning'], [16, 20, 'evening']], distance_km: 1 };

test('bearingIn: a plain arc and one that crosses north', () => {
  assert.equal(home.bearingIn(100, [80, 200]), true);
  assert.equal(home.bearingIn(10, [80, 200]), false);
  assert.equal(home.bearingIn(250, [80, 200]), false);
  assert.equal(home.bearingIn(0, [300, 20]), true);
  assert.equal(home.bearingIn(350, [300, 20]), true);
  assert.equal(home.bearingIn(180, [300, 20]), false);
  assert.equal(home.bearingIn(360, [300, 20]), true);
});

test('compass words for an arc, clockwise', () => {
  assert.deepEqual(home.compassIn([80, 200]), ['east', 'south-east', 'south']);
  assert.deepEqual(home.compassAway([80, 200]), ['west', 'north']);
  assert.deepEqual(home.compassIn([300, 20]), ['north-west', 'north']);
  assert.deepEqual(home.compassIn([25, 40]), ['north-east']);   // narrower than the points: the nearest one
});

test('rush hours read as today', () => {
  assert.equal(home.hourRange(7, 10), '7 to 10 AM');
  assert.equal(home.hourRange(16, 20, '–'), '4–8 PM');
  assert.equal(home.hourRange(11, 13), '11 AM to 1 PM');
  assert.equal(home.hourRange(0, 6), '12 to 6 AM');
});

test("The reference home's road reads exactly as the page did before the config", () => {
  assert.equal(home.roadClockText(BQE), 'Traffic is only the clock. Low most of the day, peak from 7 to 10 AM and from 4 to 8 PM, and a step higher in the hours next to those.');
  assert.equal(home.roadWindText(BQE), 'Wind is Open-Meteo’s direction. The BQE expressway runs about 1 km east to south of here, so wind from the east, south-east or south blows its exhaust toward the block, and wind from the west or north blows it away.');
  assert.equal(home.roadWhyText(BQE), 'The BQE expressway runs about 1 km east to south of here, so it matters on east, south-east and south winds.');
});

test('a road without a known distance or rush still reads', () => {
  const r = { name: 'Cross Bronx', toward: [300, 20], rush: [], distance_km: null };
  assert.equal(home.roadWhyText(r), 'The Cross Bronx highway runs north-west to north of here, so it matters on north-west and north winds.');
  assert.equal(home.roadClockText(r), 'Traffic is only the clock: no rush hours are set, so it reads low all day.');
});

test('the summary is "For:" the needs that are on, in the same words', () => {
  assert.equal(home.needsFor({ toddler: true, sinus: true, runner: true }), 'toddler, sinus & allergy, running');
  assert.equal(home.needsFor({ toddler: true, sinus: true, runner: false }), 'toddler, sinus & allergy');
  assert.equal(home.needsFor({ toddler: false, sinus: false, runner: false }), '');
});

test('a region names the place in the smoke and pollen sentences; without one they read neutrally', () => {
  assert.equal(home.smokeText('New York'), 'Wildfire smoke over New York. When it is detected, outdoor PM2.5 is the risk.');
  assert.equal(home.smokeMapText('New York'), 'NOAA Hazard Mapping: wildfire smoke over New York.');
  assert.equal(home.pollenBarsTitle('New York'), "Bars: the usual New York season, peak in amber. Right: today's level from Google.");
  for (const r of [null, undefined, '']) {
    const all = [home.smokeText(r), home.smokeMapText(r), home.pollenBarsTitle(r)].join(' ');
    assert.doesNotMatch(all, /New York|undefined|null/);
    assert.match(all, /over this area/);
    assert.match(home.pollenBarsTitle(r), /^Bars: the usual season, peak/);
  }
});

test('a source that is off or not set up says so in plain words, with one line on what it adds', () => {
  assert.deepEqual(home.sourceOff('pollen', 'not_set_up'), { word: 'Not set up', line: 'Add a Google Pollen key to see daily pollen.' });
  assert.deepEqual(home.sourceOff('pollen', 'off'), { word: 'Off', line: 'Turned off in the config.' });
  assert.deepEqual(home.sourceOff('smoke', 'off'), { word: 'Off', line: 'Turned off in the config.' });
  assert.deepEqual(home.sourceOff('nearby', 'off'), { word: 'Off', line: 'Turned off in the config.' });
  assert.deepEqual(home.sourceOff('road', 'off'), { word: 'Off', line: 'No road set up.' });
  for (const s of ['ok', 'error', undefined]) assert.equal(home.sourceOff('pollen', s), null);
});

test('the sources the page lists leave out what the config turned off', () => {
  const all = { smoke: true, pollen: true, nearby: true };
  assert.deepEqual(home.sourcesOn(all, true), ['one', 'openair', 'wx', 'pollen', 'smoke', 'bqe']);
  assert.deepEqual(home.sourcesOn({ ...all, smoke: false, pollen: false }, false), ['one', 'openair', 'wx']);
});

test('the Sources label names only the sources that are on', () => {
  assert.equal(home.sourcesLabel({ smoke: true, pollen: true }, true), 'Sources: your 2 monitors, weather, pollen, smoke and traffic. Open to see them.');
  assert.equal(home.sourcesLabel({ smoke: false, pollen: true }, false), 'Sources: your 2 monitors, weather and pollen. Open to see them.');
  assert.equal(home.sourcesLabel({ smoke: false, pollen: false }, false), 'Sources: your 2 monitors and weather. Open to see them.');
});

test('home menu has no editing controls (configuration is done in the config file, not the page)', () => {
  const html = readFileSync(new URL('index.html', root), 'utf8');
  const js = readFileSync(new URL('static/app.js', root), 'utf8');
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  for (const [name, text] of [['index.html', html], ['app.js', js]]) {
    for (const bad of ['Add a source', 'Disconnect', '>Edit<', 'class="x"', 'class="add"', 'class="edit"', 'pr-add', 'Coming later']) {
      assert.ok(!text.includes(bad), `${name} still contains ${bad}`);
    }
  }
  assert.doesNotMatch(css, /\.edit\b|button\.x\b|\.pr-add\b|button\.add\b/);
});

// AirGradient's public data is CC-BY-SA 4.0: the neighborhood says so, names the contributors and links them.
const escHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

test('the neighborhood credits AirGradient and CC-BY-SA 4.0, with links', () => {
  const html = home.creditHtml([], false, escHtml);
  assert.match(html, /Data provided by <a href="https:\/\/www\.airgradient\.com"[^>]*>AirGradient<\/a>/);
  assert.match(html, /Licensed under <a href="https:\/\/creativecommons\.org\/licenses\/by-sa\/4\.0\/"[^>]*>CC-BY-SA 4\.0<\/a>/);
  assert.doesNotMatch(html, /Contributors/);
});

test('contributors are named once each, linked when they have a link, and escaped', () => {
  const ns = [
    { publicContributorName: 'Peter Guo', publicPlaceUrl: null },
    { publicContributorName: 'SEEN/SEEDS', publicPlaceUrl: 'www.seen.team' },
    { publicContributorName: 'SEEN/SEEDS', publicPlaceUrl: 'www.seen.team' },
    { publicContributorName: '<b>x</b>', publicPlaceUrl: 'javascript:alert(1)' },
    { publicContributorName: null },
  ];
  const html = home.creditHtml(ns, false, escHtml);
  assert.match(html, /Contributors: /);
  assert.match(html, /<a href="https:\/\/www\.seen\.team" target="_blank" rel="noopener">SEEN\/SEEDS<\/a>/);
  assert.equal(html.split('SEEN/SEEDS').length, 2);
  assert.match(html, /Peter Guo/);
  assert.doesNotMatch(html, /<b>x|javascript:/);
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
});

test('in the demo the line says the monitors are made up and links nothing', () => {
  const html = home.creditHtml([{ publicContributorName: 'Someone', publicPlaceUrl: 'x.com' }], true, escHtml);
  assert.equal(html, 'Made-up monitors for the demo');
});

test('the page has the credit line in the neighborhood section', () => {
  const html = readFileSync(new URL('index.html', root), 'utf8');
  assert.match(html, /id="nb-credit"/);
  assert.match(readFileSync(new URL('static/app.js', root), 'utf8'), /creditHtml\(/);
});

test('index.html makes no AirGradient claim in the static credit line', () => {
  const html = readFileSync(new URL('index.html', root), 'utf8');
  assert.match(html, /<p class="nb-credit" id="nb-credit"><\/p>/);
});

test('the road label says what kind of road it is', () => {
  assert.equal(home.roadLabel({ name: 'BQE', kind: 'expressway' }), 'BQE expressway');
  assert.equal(home.roadLabel({ name: 'I-95' }), 'I-95 highway');
});

test('the top of the comfortable humidity band comes from the config', () => {
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  assert.match(app, /RH_GOOD = APP\.limits\.rh_good/);
  assert.doesNotMatch(app, /RH_HIGH/);
});

test("the pollen warning follows the config's pollen limit", () => {
  assert.equal(home.pollenHigh(3, { pollen: 3 }), true);
  assert.equal(home.pollenHigh(4, { pollen: 5 }), false);   // a home that set pollen = 5
  assert.equal(home.pollenHigh(5, { pollen: 5 }), true);
  assert.equal(home.pollenHigh(null, { pollen: 3 }), false);
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  assert.doesNotMatch(app, /(top|i) >= 3\b/);
});

test('the sky and the PM2.5 words read the configured PM2.5 limits', () => {
  const sky = readFileSync(new URL('static/sky.js', root), 'utf8');
  assert.match(sky, /APP\.limits\.pm_high/);
  assert.doesNotMatch(sky, /pm > 35\b/);
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  assert.doesNotMatch(app, /35\.4/);
});

// The server rounds PM2.5 before comparing (summary.py: round(v) > limit), and the page shows it rounded,
// so the page's words and colours compare the rounded value too.
test('PM2.5 words compare the rounded reading, like the server', () => {
  const limits = { pm: 15, pm_high: 35 };
  assert.equal(home.pmLevel(15.3, limits).word, 'Good');
  assert.equal(home.pmLevel(15.6, limits).word, 'Moderate');
  assert.equal(home.pmLevel(35.2, limits).word, 'Moderate');
  assert.equal(home.pmLevel(35.6, limits).word, 'Unhealthy for sensitive groups');
  assert.equal(home.pmLevel(55.4, limits).word, 'Unhealthy for sensitive groups');
  assert.equal(home.pmLevel(55.6, limits).word, 'Unhealthy');
  assert.equal(home.pmLevel(null, limits).word, 'No reading');
  assert.equal(home.pmOver(15.3, 15), false);
  assert.equal(home.pmOver(15.6, 15), true);
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  assert.doesNotMatch(app, /pm02 > PM_FINE|v > PM_FINE|median > PM_FINE/);
  const sky = readFileSync(new URL('static/sky.js', root), 'utf8');
  assert.doesNotMatch(sky, /pm > /);
  const map = readFileSync(new URL('static/map.js', root), 'utf8');
  assert.match(map, /\['round', \['get', 'pm'\]\]/);
});

// The Home menu's rows: no (i) buttons; a source row explains itself on hover, focus or a tap, like the need chips.
test('home menu rows carry their explanation as a row tooltip, not an (i) button', () => {
  const html = readFileSync(new URL('index.html', root), 'utf8');
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  const lists = [...html.matchAll(/<ul class="plist">([\s\S]*?)<\/ul>/g)].map(m => m[1]);
  assert.equal(lists.length, 2);
  const rows = lists.flatMap(l => l.split(/(?=<li class="pr)/).filter(r => r.startsWith('<li')));
  assert.equal(rows.length, 7);
  for (const row of rows) assert.doesNotMatch(row, /class="q"|class="bubble"|pr-a/);
  const monitors = lists[0].split(/(?=<li class="pr)/).filter(r => r.startsWith('<li'));
  for (const row of monitors) assert.doesNotMatch(row, /tabindex|pr-tip/);   // nothing to explain, no empty tooltip
  const sources = lists[1].split(/(?=<li class="pr)/).filter(r => r.startsWith('<li'));
  assert.equal(sources.length, 5);
  for (const row of sources) {
    const id = (row.match(/^<li class="pr has-tip"[^>]* tabindex="0" aria-describedby="(tip-\w+)"/) || [])[1];
    assert.ok(id, `row not focusable or not described: ${row.slice(0, 80)}`);
    assert.match(row, new RegExp(`<span class="pr-tip" id="${id}" role="tooltip"`));
  }
  assert.match(css, /\.pr\.has-tip:hover \.pr-tip, \.pr\.has-tip:focus \.pr-tip \{ display: block; \}/);
  assert.doesNotMatch(css, /\.pr-a\b/);
});
