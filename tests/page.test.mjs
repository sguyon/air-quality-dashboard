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
const files = ['static/app.js', 'static/sky.js', 'static/summary.js', 'static/home.js', 'static/picker.js'].map(f => strip(readFileSync(new URL(f, root), 'utf8')));
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

test('the summary is "For:" the profiles that are on, in the same words', () => {
  assert.equal(home.profilesFor({ toddler: true, sinus: true, runner: true }), 'toddler, sinus & allergy, running');
  assert.equal(home.profilesFor({ toddler: true, sinus: true, runner: false }), 'toddler, sinus & allergy');
  assert.equal(home.profilesFor({ toddler: false, sinus: false, runner: false }), '');
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
  assert.deepEqual(home.sourceOff('pollen', 'not_set_up'), { word: 'Off', line: 'Needs a Google Pollen key', calendar: true });
  assert.deepEqual(home.sourceOff('pollen', 'off'), { word: 'Off', line: 'Adds daily pollen levels from Google.' });
  assert.deepEqual(home.sourceOff('smoke', 'off'), { word: 'Off', line: 'Adds wildfire smoke from NOAA\u2019s satellite map.' });
  assert.deepEqual(home.sourceOff('nearby', 'off'), { word: 'Off', line: 'Adds readings from public AirGradient monitors nearby.' });
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

// AirGradient's public data is CC-BY-SA 4.0: the neighborhood's footer says so; each owner is named in their open row (Task 6d).
const escHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

test('the neighborhood credits AirGradient and CC-BY-SA 4.0, with links, and lists no contributors', () => {
  const html = home.creditHtml(false);
  assert.equal(html, 'Data provided by <a href="https://www.airgradient.com" target="_blank" rel="noopener">AirGradient</a> · ' +
    'Licensed under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC-BY-SA 4.0</a>');
  assert.doesNotMatch(html, /Contributors/);
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  assert.doesNotMatch(app, /creditHtml\(others/);
});

test('in the demo the line says the monitors are made up and links nothing', () => {
  assert.equal(home.creditHtml(true), 'Made-up monitors for the demo');
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

// The Home menu's rows: no (i) buttons; a source row explains itself on hover, focus or a tap, like the profile chips.
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

// ── A public monitor's page (the demo's ?monitor=<id>): what the page draws when the view has no indoor monitor ──
const NOW = new Date('2026-11-09T12:00:00Z');
const FRESH = { timestamp: '2026-11-09T11:58:00Z' };

test('an indoor monitor the view does not have is disabled: tone off, Not set up, never Offline', () => {
  assert.deepEqual(home.freshness(null, NOW, true), { tone: 'off', label: 'Not set up' });
  assert.deepEqual(home.freshness(FRESH, NOW, true), { tone: 'off', label: 'Not set up' });
  assert.equal(home.freshness(null, NOW).label, 'Offline');   // a home's indoor monitor that stopped: still red
  const pill = home.monitorPill({ indoor: null, outdoor: 'Roof' }, null, FRESH, NOW, { one: '<svg id="one"/>', openair: '<svg id="oa"/>' });
  const [indoor, outdoor] = pill.split(/(?=<span class="vhw)/);
  assert.match(indoor, /^<span class="vhw off" data-tip="Indoor · AirGradient ONE: Not set up"><svg id="one"\/><i class="off"><\/i><\/span>$/);
  assert.match(outdoor, /class="vhw" data-tip="Outdoor · AirGradient Open Air: Online"/);
  assert.doesNotMatch(pill, /Offline|class="bad"/);
  const home2 = home.monitorPill({ indoor: 'Living room', outdoor: 'Roof' }, null, FRESH, NOW, {});
  assert.match(home2, /class="vhw" data-tip="Indoor · AirGradient ONE: Offline"><i class="bad">/);
});

test('the menu counts only the monitors the view has', () => {
  assert.deepEqual(home.monitorsLive([{ tone: 'off' }, { tone: 'good' }]), { text: '1 monitor live', tone: 'good' });
  assert.deepEqual(home.monitorsLive([{ tone: 'good' }, { tone: 'good' }]), { text: '2 monitors live', tone: 'good' });
  assert.deepEqual(home.monitorsLive([{ tone: 'bad' }, { tone: 'good' }]), { text: '1 of 2 monitors live', tone: 'warn' });
  assert.deepEqual(home.monitorsLive([{ tone: 'bad' }, { tone: 'warn' }]), { text: '0 of 2 monitors live', tone: 'bad' });
  assert.deepEqual(home.monitorsLive([{ tone: 'off' }, { tone: 'bad' }]), { text: '1 monitor, not live', tone: 'bad' });
  assert.deepEqual(home.sourcesOn({ pollen: false, smoke: true }, false, false), ['openair', 'wx', 'smoke']);
});

test('pollen without a key (a public monitor, or a home with no key) is Off, keeps its calendar, and never names the config', () => {
  for (const o of [home.sourceOff('pollen', 'not_set_up'), home.sourceOff('pollen', 'off', true)]) {
    assert.deepEqual(o, { word: 'Off', line: 'Needs a Google Pollen key', calendar: true });
  }
  assert.deepEqual(home.sourceOff('pollen', 'off'), { word: 'Off', line: 'Adds daily pollen levels from Google.' });   // a home that turned it off
  const smoke = home.sourceOff('smoke', 'off', true);   // a public monitor outside North America
  assert.equal(smoke.word, 'Off');
  assert.doesNotMatch(smoke.line, /config/i);
  // the Off card keeps the season calendar: drawn with no level for today, "—" for each type
  const SEASONS = [{ name: 'Tree', start: [3, 1], end: [5, 31], peak: [[4, 1], [4, 30]] },
    { name: 'Grass', start: [5, 1], end: [7, 31], peak: [[6, 1], [6, 30]] }];
  const cal = home.pollenSeasonHTML(SEASONS, [], new Date(2026, 3, 15, 9), { pollen: 3 }, null, escHtml);
  assert.match(cal, /class="ps-grid"/);
  assert.equal((cal.match(/<\/div>—<\/div>/g) || []).length, 2);   // no level from Google
  assert.match(cal, /<b>Now: tree season<\/b>, at its peak/);
  assert.equal(home.pollenSeasonHTML([], [], new Date(2026, 3, 15), { pollen: 3 }, null, escHtml), '');   // a place without seasons: no calendar
  assert.match(home.pollenSeasonHTML(SEASONS, [{ name: 'Tree', index: 4 }], new Date(2026, 3, 15, 9), { pollen: 3 }, null, escHtml), /<b class="warn">High<\/b>/);
});

test('the page never mentions the config', () => {
  const html = readFileSync(new URL('index.html', root), 'utf8').replace(/<!--[\s\S]*?-->/g, '').replace(/<script>[\s\S]*?<\/script>/g, '')
    .replace(/<article class="card no-token-card"[\s\S]*?<\/article>/, '');   // the setup state ("Config loaded, add your token"): for whoever is setting it up, decided in the spec
  assert.doesNotMatch(html, /config/i);
  for (const id of ['pollen', 'smoke', 'nearby', 'road']) for (const st of ['off', 'not_set_up']) for (const pub of [false, true]) {
    const o = home.sourceOff(id, st, pub);
    if (o) assert.doesNotMatch(o.line, /config/i, `${id} ${st} ${pub}`);
  }
  const strings = s => (s.replace(/\/\/.*$/gm, '').match(/'[^'\n]*'|`[^`]*`|"[^"\n]*"/g) || []).join('\n');
  for (const f of ['static/app.js', 'static/home.js', 'static/picker.js', 'static/summary.js']) assert.doesNotMatch(strings(readFileSync(new URL(f, root), 'utf8')), /\bconfig\b/i, f);
});

test('a public monitor has no road: its card reads Off with a plain line', () => {
  assert.deepEqual(home.sourceOff('road', 'off', true), { word: 'Off', line: 'Not available for public monitors yet.' });
});

test("a public monitor's card credits its owner, linked when there's a link, escaped", () => {
  const c = home.monitorCredit({ contributor: 'Dana <b>K</b>', url: 'www.example.org/roof' }, escHtml);
  assert.equal(c, 'Shared by <a href="https://www.example.org/roof" target="_blank" rel="noopener"><b>Dana &lt;b&gt;K&lt;/b&gt;</b></a> on ' +
    `<a href="https://www.airgradient.com/map/" target="_blank" rel="noopener">AirGradient's public map</a> · CC BY-SA`);
  assert.match(home.monitorCredit({ contributor: 'Ann', url: 'javascript:alert(1)' }, escHtml), /^Shared by <b>Ann<\/b> on /);
  assert.match(home.monitorCredit({ contributor: null, url: null }, escHtml), /^Shared on <a /);
});

test('the indoor card on a public monitor is the same card, empty and marked as missing', () => {
  const src = readFileSync(new URL('../static/app.js', import.meta.url), 'utf8');
  assert.match(src, /monitorCard\(state\.outdoor, false\) \+ monitorCard\(null, true, true\)/);
  assert.match(src, /mc-ghost/);
});

test("a public monitor with no history: one line, not three empty charts", () => {
  const html = home.noHistoryHTML();
  assert.match(html, /<b>No past readings for this monitor<\/b>/);
  assert.match(html, /<span>AirGradient's map has none for it right now\. Today's forecast is in the summary\.<\/span>/);
  assert.match(readFileSync(new URL('index.html', root), 'utf8'), /id="hist-none"[^>]* hidden/);
});

test('the neighborhood calls the shown monitor This on a public page, You at home', () => {
  assert.deepEqual(home.selfWords(true), { row: 'This', map: 'This monitor', legend: 'This monitor', block: 'this monitor', near: 'this monitor' });
  assert.deepEqual(home.selfWords(false), { row: 'You', map: 'You', legend: 'Your monitor', block: 'your block', near: 'home' });
  const f = { esc: escHtml, pm: v => (v >= 10 ? String(Math.round(v)) : v.toFixed(1)), num: v => v.toFixed(1) };   // app.js pmNum, num
  const others = [{ pm02: 5, distance_km: 1, locationName: 'A' }, { pm02: 6, distance_km: 2, locationName: 'B' }, { pm02: 7, distance_km: 3, locationName: 'C' }];
  const lead = home.nbLead({ pm02: 40 }, others, 15, home.selfWords(true), f);
  assert.match(lead, /This monitor reads well above the area.*a source close to this monitor: traffic/);
  const area = [{ pm02: 30, distance_km: 1, locationName: 'A' }, { pm02: 31, distance_km: 2, locationName: 'B' }];
  assert.match(home.nbLead(null, area, 15, home.selfWords(true), f), /not a source near this monitor\./);
  assert.match(home.nbLead(null, area, 15, home.selfWords(false), f), /not a source near home\./);
  assert.doesNotMatch(lead, /Your block|your block/);
  assert.match(home.nbLead({ pm02: 40 }, others, 15, home.selfWords(false), f), /Your block reads well above the area/);
  const one = home.nbLead({ pm02: 5 }, [{ pm02: 30, distance_km: 1.1, locationName: 'X' }, ...others], 15, home.selfWords(true), f);
  assert.match(one, /the nearest is X, 1\.1 km away\. This monitor is still clean\./);
  assert.match(readFileSync(new URL('static/map.js', root), 'utf8'), /selfWords\(/);
});

test('the model past hours are a dotted line over a pale fill, labeled as the model', () => {
  const summary = require('../static/summary.js');
  const col = { muted: '#777', card: '#fff', fill: '#7f93a6' };
  const model = summary.pmPastSvg('model', 'M0 50 L100 30', 'M0 50 L100 30 L 100 96 L 0 96 Z', { x: 2, y: 22 }, col);
  assert.match(model, />PM2\.5 outside · model<\/text>/);
  assert.match(model, /stroke-dasharray="2 3"/);
  assert.match(model, /fill="#7f93a6" fill-opacity="\.14"/);
  const measured = summary.pmPastSvg(undefined, 'M0 50 L100 30', 'M0 50 L100 30 L 100 96 L 0 96 Z', { x: 2, y: 22 }, col);
  assert.equal(measured, '<path d="M0 50 L100 30 L 100 96 L 0 96 Z" fill="url(#sx-fp)"/>');
});

test("the open menu's indoor row on a public monitor's page: greyed (off), Not set up, no reading time", () => {
  const r = home.monitorRow(null, NOW, true, 'America/New_York');
  assert.deepEqual(r, { tone: 'off', text: 'Not set up', title: 'Not set up', off: true });
  const live = home.monitorRow(FRESH, NOW, false, 'America/New_York');
  assert.equal(live.off, false); assert.equal(live.tone, 'good'); assert.equal(live.text, 'Live · 2 min ago');
  assert.match(live.title, /^Last reading Nov 9, 6:58\sAM$/);
  assert.deepEqual(home.monitorRow(null, NOW, false, 'UTC'), { tone: 'bad', text: 'Offline', title: 'No reading', off: false });
});

test('the neighborhood row for the shown monitor reads This on a public page, You at home', () => {
  const f = { esc: escHtml, pm: v => String(v), num: v => v.toFixed(1), temp: v => `${v}°C` };
  const scale = { limit: 15, barMax: 55, limPct: '27.3' };
  const n = { locationId: 5, locationName: 'Oak <b>st</b>', pm02: 22, distance_km: 0, atmp: 15, rhum: 92.6 };
  const row = home.nbRowHTML(n, true, home.selfWords(true), 'Roof & co', scale, f);
  assert.match(row, /^<tr class="you" data-id="5">/);
  // the id is AirGradient's number: anything else in it can't reach the markup (as in the open band's id)
  assert.match(home.nbRowHTML({ ...n, locationId: '5"><b>x' }, false, home.selfWords(false), 'x', scale, f), /^<tr class="" data-id="NaN">/);
  assert.match(row, /<td class="dist">This<\/td>/);
  assert.match(row, /<td class="loc" title="Oak &lt;b&gt;st&lt;\/b&gt;">Roof &amp; co<\/td>/);
  assert.match(row, /<td class="r pm warn">22<\/td><td class="r">15°C<\/td><td class="r">93%<\/td>/);
  assert.match(home.nbRowHTML(n, true, home.selfWords(false), 'Home', scale, f), /<td class="dist">You<\/td>/);
  assert.match(home.nbRowHTML({ ...n, atmp: null }, false, home.selfWords(true), 'x', scale, f), /<td class="dist">0\.0 km<\/td>.*<td class="r">—<\/td>/);
});

// ── Neighbors on the corrected PM2.5, like the home's own monitors (Task 6c) ──
const NB_F = { esc: escHtml, pm: v => (v >= 10 ? String(Math.round(v)) : v.toFixed(1)), num: v => v.toFixed(1), temp: v => `${v}°C` };

test("a neighbor's PM2.5 is the corrected one, the raw only without it", () => {
  assert.equal(home.nbPm({ pm02: 22, pm02_corrected: 12.4 }), 12.4);
  assert.equal(home.nbPm({ pm02: 22 }), 22);
  assert.equal(home.nbPm({ pm02: 22, pm02_corrected: null }), 22);
  assert.equal(home.nbPm({ pm02: 0, pm02_corrected: 0 }), 0);   // zero is a reading
  assert.equal(home.nbPm({}), null);
});

test('the neighborhood row shows the corrected PM2.5, its tone and its bar', () => {
  const scale = { limit: 15, barMax: 50, limPct: '30.0' };
  const row = home.nbRowHTML({ locationId: 1, locationName: 'A', pm02: 22, pm02_corrected: 10, distance_km: 1 }, false, home.selfWords(false), 'Home', scale, NB_F);
  assert.match(row, /<td class="r pm good">10<\/td>/);
  assert.match(row, /<i style="width:20\.0%" class="good">/);
  assert.doesNotMatch(row, />22</);
});

test('the lead counts the monitors over the limit on the corrected PM2.5', () => {
  const self = home.selfWords(false);
  // raw over the limit, corrected under it: nothing to say
  const clean = [{ pm02: 22, pm02_corrected: 12, distance_km: 1, locationName: 'A' }, { pm02: 4, pm02_corrected: 4.5, distance_km: 2, locationName: 'B' },
    { pm02: 5, pm02_corrected: 5, distance_km: 3, locationName: 'C' }];
  assert.equal(home.nbLead({ pm02: 6, pm02_corrected: 6 }, clean, 15, self, NB_F), '');
  // raw under, corrected over: counted, with the shown monitor still clean on its corrected reading
  const over = [{ pm02: 14, pm02_corrected: 18, distance_km: 1.2, locationName: 'Near' }, { pm02: 4, pm02_corrected: 4.5, distance_km: 2, locationName: 'B' },
    { pm02: 5, pm02_corrected: 5, distance_km: 3, locationName: 'C' }];
  assert.match(home.nbLead({ pm02: 20, pm02_corrected: 9 }, over, 15, self, NB_F),
    /One nearby monitor is over the 15 µg\/m³ limit<\/b>: the nearest is Near, 1\.2 km away\. Your block is still clean\./);
  // the median and "well above the area" read the corrected values too
  const area = [{ pm02: 40, pm02_corrected: 5, distance_km: 1, locationName: 'A' }, { pm02: 40, pm02_corrected: 6, distance_km: 2, locationName: 'B' }];
  assert.match(home.nbLead({ pm02: 10, pm02_corrected: 30 }, area, 15, self, NB_F), /Your block reads well above the area<\/b> \(30 against a typical 6\.0\)/);
});

test("each real neighbor row links to AirGradient's map in a new tab; made-up ones don't", () => {
  const scale = { limit: 15, barMax: 55, limPct: '27.3' };
  const url = 'https://www.airgradient.com/map?zoom=15&long=100.5&lat=13.9&meas=ug_m3';
  const row = home.nbRowHTML({ locationId: 3, locationName: 'Soi <b>7</b>', pm02: 5, distance_km: 2, map_url: url }, false, home.selfWords(false), 'Home', scale, NB_F);
  assert.match(row, /<a class="nb-ext" href="https:\/\/www\.airgradient\.com\/map\?zoom=15&amp;long=100\.5&amp;lat=13\.9&amp;meas=ug_m3" target="_blank" rel="noopener" title="Open on AirGradient's map" aria-label="Open Soi &lt;b&gt;7&lt;\/b&gt; on AirGradient's map">/);
  const fake = home.nbRowHTML({ locationId: 4, locationName: 'Demo monitor · X', pm02: 5, distance_km: 2 }, false, home.selfWords(false), 'Home', scale, NB_F);
  assert.doesNotMatch(fake, /<a /);
  const bad = home.nbRowHTML({ locationId: 5, locationName: 'Y', pm02: 5, distance_km: 2, map_url: 'javascript:alert(1)' }, false, home.selfWords(false), 'Home', scale, NB_F);
  assert.doesNotMatch(bad, /<a /);
});

test("the neighborhood header has no map button; the map reads the corrected PM2.5", () => {
  const html = readFileSync(new URL('index.html', root), 'utf8');
  assert.doesNotMatch(html, /Open the map/);
  assert.doesNotMatch(html, /data-app="map-area"/);
  const map = readFileSync(new URL('static/map.js', root), 'utf8');
  assert.doesNotMatch(map, /\.pm02\b/);
  assert.match(map, /nbPm\(/);
  // an unknown monitor's page ({id, error}) shows the default sample: the map calls the home's monitor "You"
  assert.match(map, /selfWords\(!!\(APP\.public && !APP\.public\.error\)\)/);
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  const nb = app.slice(app.indexOf('function renderNeighborhood'), app.indexOf('// ── Charts'));
  assert.doesNotMatch(nb, /\.pm02\b/);
});

// ── A neighbor row opens in place (Task 6d) ──
const OPEN_SCALE = { limit: 15, high: 35, barMax: 55, limPct: '27.3' };
const OPEN_F = { ...NB_F, when: ts => home.lastReadingText(ts, new Date('2026-11-09T12:45:00Z'), 'America/New_York') };
const REAL = { locationId: 5107, locationName: 'Oak <b>&</b> Elm', publicContributorName: ' Rosa <i>D</i> ', pm02: 30, pm02_corrected: 25,
  rhum: 90.6, atmp: 15.2, distance_km: 1.9, timestamp: '2026-11-09T12:38:00Z', map_url: 'https://www.airgradient.com/map?zoom=15&long=-73.9&lat=40.7&meas=ug_m3' };

test('a real neighbor row has a chevron toggle with aria-expanded; open, the band follows the row', () => {
  const closed = home.nbRowHTML(REAL, false, home.selfWords(false), 'Home', OPEN_SCALE, OPEN_F);
  assert.match(closed, /^<tr class="nb-can" data-id="5107">/);
  assert.match(closed, /<td class="nb-tg"><button type="button" class="nb-tgb" aria-expanded="false" aria-controls="nbd-5107" aria-label="Details: Oak &lt;b&gt;&amp;&lt;\/b&gt; Elm">/);
  assert.doesNotMatch(closed, /nb-detail/);
  const open = home.nbRowHTML(REAL, false, home.selfWords(false), 'Home', OPEN_SCALE, OPEN_F, true);
  assert.match(open, /^<tr class="nb-can nb-open" data-id="5107">/);
  assert.match(open, /aria-expanded="true"/);
  assert.match(open, /<\/tr><tr class="nb-detail" id="nbd-5107"><td colspan="8">/);   // the id the toggle's aria-controls names
  assert.equal(open.split('<tr').length - 1, 2);
});

test('the shown monitor and the demo samples\' made-up neighbors do not open', () => {
  const you = home.nbRowHTML(REAL, true, home.selfWords(false), 'Home', OPEN_SCALE, OPEN_F, true);
  assert.match(you, /^<tr class="you" data-id="5107">/);
  assert.match(you, /<td class="nb-tg"><\/td><\/tr>$/);
  const fake = home.nbRowHTML({ locationId: 4, locationName: 'Demo monitor · X', pm02: 5, distance_km: 2 }, false, home.selfWords(false), 'Home', OPEN_SCALE, OPEN_F, true);
  assert.match(fake, /^<tr class="" data-id="4">/);
  assert.doesNotMatch(fake, /<button|nb-detail|aria-expanded/);
});

test("the open band: PM2.5 now with its word, humidity, temperature, the owner, the last reading, and the map action only", () => {
  for (const self of [home.selfWords(false), home.selfWords(true)]) {   // a real home, and a public monitor's page on the demo
    const band = home.nbDetailHTML(REAL, OPEN_SCALE, OPEN_F);
    assert.equal(home.nbRowHTML(REAL, false, self, 'x', OPEN_SCALE, OPEN_F, true).endsWith(band), true);
    assert.match(band, /<dt>PM2\.5 now<\/dt><dd class="warn">25 <small>µg\/m³<\/small> · Moderate<\/dd>/);
    assert.match(band, /<dt>Humidity<\/dt><dd>91%<\/dd>/);
    assert.match(band, /<dt>Temperature<\/dt><dd>15\.2°C<\/dd>/);
    assert.match(band, /<p class="nbd-meta"><b class="nbd-band warn">Moderate<\/b><span class="nbd-sep"> · <\/span>Shared by Rosa &lt;i&gt;D&lt;\/i&gt; · last reading 7:38\sAM, 7 min ago<\/p>/);
    // one action: a quiet link to the monitor on AirGradient's map, in a new tab
    assert.equal(band.split('<a ').length - 1, 1);
    assert.match(band, /<a class="nbd-q" href="https:\/\/www\.airgradient\.com\/map\?zoom=15&amp;long=-73\.9&amp;lat=40\.7&amp;meas=ug_m3" target="_blank" rel="noopener"><svg[^>]*>.*<\/svg>Open on AirGradient's map<\/a>/);
    assert.doesNotMatch(band, /Switch|\?monitor=|<button/);
    assert.doesNotMatch(band, /<b>&|<i>D/);
  }
  // no owner: the reading time starts the line; no time: the owner alone
  assert.match(home.nbDetailHTML({ ...REAL, publicContributorName: null }, OPEN_SCALE, OPEN_F), /<span class="nbd-sep"> · <\/span>Last reading 7:38\sAM, 7 min ago<\/p>/);
  assert.match(home.nbDetailHTML({ ...REAL, timestamp: null }, OPEN_SCALE, OPEN_F), /<span class="nbd-sep"> · <\/span>Shared by Rosa &lt;i&gt;D&lt;\/i&gt;<\/p>/);
  assert.match(home.nbDetailHTML({ ...REAL, pm02_corrected: 9 }, OPEN_SCALE, OPEN_F), /<dd class="good">9\.0 <small>µg\/m³<\/small> · Good<\/dd>/);
});

test("a neighbor's last reading: its time in the home's timezone and how long ago", () => {
  const now = new Date('2026-11-09T12:45:00Z'), tz = 'America/New_York';
  assert.match(home.lastReadingText('2026-11-09T12:38:00Z', now, tz), /^7:38\sAM, 7 min ago$/);
  assert.match(home.lastReadingText('2026-11-09T12:44:40Z', now, tz), /^7:44\sAM, just now$/);
  assert.match(home.lastReadingText('2026-11-09T11:20:00Z', now, tz), /^6:20\sAM, 1 h 25 min ago$/);
  assert.match(home.lastReadingText('2026-11-09T11:45:00Z', now, tz), /^6:45\sAM, 1 h ago$/);
  assert.equal(home.lastReadingText(null, now, tz), '');
  assert.equal(home.lastReadingText('nope', now, tz), '');
});

test('the page opens one row at a time, in place, and the neighborhood links to no other monitor page', () => {
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  const nb = app.slice(app.indexOf('// ── Neighborhood'), app.indexOf('// ── Charts'));
  assert.match(nb, /state\.nbOpen = state\.nbOpen === id \? null : id/);
  assert.match(nb, /closest\('a'\)/);   // the row's ↗ opens the map, it doesn't toggle the row
  assert.match(nb, /nbRowHTML\([^)]*n\.locationId === state\.nbOpen\)/);
  const h = readFileSync(new URL('static/home.js', root), 'utf8'), rowsJs = h.slice(h.indexOf('const NB_COLS'), h.indexOf('function lastReadingText'));
  for (const text of [nb, rowsJs]) assert.doesNotMatch(text, /\?monitor=|Switch to this monitor/);
  const html = readFileSync(new URL('index.html', root), 'utf8');
  assert.match(html, /<th class="nbbar">.*<\/th><th class="nb-tg"><\/th><\/tr><\/thead><tbody id="nb">/);
});

test("on a phone the row's ↗ lives only in the open band, a full-width action at least 44 px tall", () => {
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  assert.match(css, /@media \(max-width: 700px\) \{\s*\.nbt td\.loc \.nb-ext \{ display: none; \}/);
  const q = css.match(/\.nbd-q \{[^}]*\}/)[0];
  assert.match(q, /width: 100%/);
  assert.match(q, /min-height: 44px/);
  assert.doesNotMatch(q, /background: var\(--accent\)/);   // quiet: no fill
});

test("at home, the You row reads the outdoor card's PM2.5 (the row, the lead and the map label alike)", () => {
  const you = { locationId: 7, pm02: 20, pm02_corrected: 9, rhum: 80 };
  assert.deepEqual(home.nbYou(you, { locationId: 7, pm02: 21, pm02_corrected: 11.2 }, 11.2), { ...you, pm02_corrected: 11.2 });
  assert.equal(home.nbYou(you, { locationId: 8 }, 3), you);   // the indoor monitor's row, or another: as it came
  assert.equal(home.nbYou(you, null, null), you);
  assert.equal(home.nbYou(undefined, { locationId: 7 }, 3), undefined);
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  assert.match(app, /const you = nbYou\(split\.you \|\| undefined, state\.outdoor, pick\(state\.outdoor, 'pm02_corrected', 'pm02'\)\)/);
});

test('neighborhood: the header says only Neighborhood, the findings sit in the card, the count is in Show more', () => {
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  const html = readFileSync(new URL('index.html', root), 'utf8');
  assert.match(html, /<h2>Neighborhood<\/h2>/);
  assert.doesNotMatch(html + app, /nb-sub|nb-foot|nb-why/);
  // map and legend, then the findings (neighbors line, wind line), then the table
  assert.ok(html.indexOf('id="nb-map"') < html.indexOf('id="nb-find"') && html.indexOf('id="nb-find"') < html.indexOf('class="nbt"'));
  assert.ok(html.indexOf('id="nb-lead"') < html.indexOf('id="nb-wind"') && html.indexOf('id="nb-wind"') < html.indexOf('class="nbt"'));
  assert.match(html, /PM2\.5<span class="nb-unit">µg\/m³<\/span>/);   // the unit moved from the header to the column
  // the road's distance is the legend's ⓘ (the page's data-tip), only with a road
  assert.match(html, /class="lg-info"[^>]*data-app="road-why"[^>]*tabindex="0"/);
  assert.match(app, /'road-why': el => \{ if \(!road\) return;/);
  // nearby off: the one-line note sits outside the hidden card
  assert.match(app, /\$?.*getElementById\('nb-off'\)/);
  assert.match(app, /\$\('nb-find'\)\.hidden = lead\.hidden && wind\.hidden/);
  assert.match(app, /nbMoreText\(extra, state\.nbCount\)/);
});

test('nbMoreText: the collapsed button says how many more and how many monitors in all', () => {
  assert.equal(home.nbMoreText(5, 12), 'Show 5 more of 12 within 15 km');
  assert.equal(home.nbMoreText(1, 9), 'Show 1 more of 9 within 15 km');
});


// ── The map's first view: the nearest neighbors in view, centered on the block (map.js create) ──
// map.js runs in a sandbox with a fake MapLibre that records the camera it's asked for.
function mapWith(others, width) {
  const vm = require('node:vm');
  const rec = { jumps: [], asks: [] };
  class LngLatBounds {
    constructor(a, b) { this.w = a[0]; this.s = a[1]; this.e = b[0]; this.n = b[1]; }
    extend([x, y]) { this.w = Math.min(this.w, x); this.e = Math.max(this.e, x); this.s = Math.min(this.s, y); this.n = Math.max(this.n, y); return this; }
  }
  class Map {
    constructor(o) { rec.opts = o; this.scrollZoom = { disable() {} }; }
    addControl() {} on() {} once() {}
    // a stand-in for MapLibre's fit: one zoom level out for each doubling of the box past 0.02°
    cameraForBounds(b, o) { rec.asks.push({ b, o }); return { zoom: Math.min(o.maxZoom, 12.7 - Math.log2(Math.max(b.e - b.w, b.n - b.s) / 0.02)) }; }
    jumpTo(c) { rec.jumps.push(c); }
  }
  const el = () => ({ set onload(f) { this._ok = f; }, get onload() { return this._ok; } });
  const box = { clientWidth: width, querySelectorAll: () => [], innerHTML: '' };
  const document = { documentElement: { dataset: {} }, body: { dataset: {} }, createElement: el,
    head: { appendChild: x => x.onload && x.onload() }, querySelectorAll: () => [] };
  const ctx = { window: {}, document, maplibregl: { Map, LngLatBounds, NavigationControl: class {}, AttributionControl: class {} },
    $: id => (id === 'nb-map' ? box : null), APP: { place: { lat: 13.75, lon: 100.48 }, road: null },
    apiUrl: x => x, selfWords: home.selfWords, bearingIn: home.bearingIn, nbPm: home.nbPm, Promise };
  vm.createContext(ctx);
  vm.runInContext(readFileSync(new URL('static/map.js', root), 'utf8') + ';this.NBMAP = NBMAP;', ctx);
  const you = { locationId: 1, longitude: 100.48, latitude: 13.75, pm02: 9 };
  ctx.NBMAP.update(you, others, null);
  return new Promise(r => setTimeout(() => r(rec), 0));
}
const east = km => ({ locationId: 100 + km, longitude: 100.48 + km / 108, latitude: 13.75, pm02: 5 });   // ~108 km per degree here

test("the map opens with the six nearest neighbors in view, centered on the block, never past the city's scale", async () => {
  const map = readFileSync(new URL('static/map.js', root), 'utf8');
  assert.match(map, /const FIT_NEAREST = 6, FIT_PAD = 40, FIT_MIN_ZOOM = 10\.5;/);
  // Bangkok-like: the nearest is 1 km away, the sixth 6 km, the seventh 14 km (left out)
  const rec = await mapWith([1, 2, 3, 4, 5, 6, 14].map(east), 1200);
  assert.equal(rec.opts.zoom, 12.7);
  assert.equal(rec.asks.length, 1);
  const { b, o } = rec.asks[0];
  assert.deepEqual({ ...o }, { padding: 40, maxZoom: 12.7 });
  assert.ok(Math.abs((b.w + b.e) / 2 - 100.48) < 1e-9 && Math.abs(b.e - (100.48 + 6 / 108)) < 1e-9);   // centered; the 6th, not the 7th
  assert.equal(rec.jumps.length, 1);
  assert.deepEqual([...rec.jumps[0].center], [100.48, 13.75]);
  assert.ok(rec.jumps[0].zoom < 12.7 && rec.jumps[0].zoom >= 10.5);
  // neighbors far out: no wider than FIT_MIN_ZOOM; all close by: the usual zoom (the phone's under 600 px)
  assert.equal((await mapWith([20, 30].map(east), 1200)).jumps[0].zoom, 10.5);
  assert.equal((await mapWith([0.2].map(east), 390)).jumps[0].zoom, 12.1);
  assert.equal((await mapWith([], 390)).jumps.length, 0);   // no neighbors: the map stays where it opened
});


test("a public monitor's empty week isn't kept, so a slow first answer from the map doesn't hide History", () => {
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  const week = app.slice(app.indexOf('function loadWeek'), app.indexOf('function chartsLoading'));
  assert.match(week, /if \(!ih \|\| !oh \|\| \(mapWeek\(\) && !oh\.length\)\) throw new Error\('history'\);\s*hist\.week = \{ ih, oh, to \}/);
  // the map's week: a public monitor's page, and the nearby public monitor an indoor-only home chose (not an estimate,
  // which has no locationId and so no week of its own)
  assert.match(app, /const mapWeek = \(\) => PUB \|\| \(NO_OUTDOOR && !noOutLine\(\)\);/);
});




// ── A home with one monitor: where an indoor-only home's outdoor PM2.5 comes from (/api/current's "source") ──
const PINNED = { kind: 'monitor', id: 900002, name: 'Cedar & 2nd Ave', distance_km: 1.1, area_count: 0, fallback: false };

test("an indoor-only home's outdoor source in words: the card's name line and the Home menu's", () => {
  assert.deepEqual(home.sourceLine(PINNED), { name: 'Nearby public monitor', sub: 'Cedar & 2nd Ave, 1.1 km', menu: 'Nearby public monitor, 1.1 km', estimate: false, down: null });
  assert.deepEqual(home.sourceLine({ kind: 'area', area_count: 4 }), { name: 'Estimate for your area', sub: 'from 4 public monitors', menu: 'Estimate for your area', estimate: true, down: null });
  assert.equal(home.sourceLine({ kind: 'area', area_count: 1 }).sub, 'from 1 public monitor');
  assert.equal(home.sourceLine({ kind: 'area', area_count: 0 }).sub, '');
  assert.deepEqual(home.sourceLine({ kind: 'model' }), { name: 'Estimate for your area (Open‑Meteo)', sub: '', menu: 'Estimate for your area', estimate: true, down: null });
  assert.equal(home.sourceLine(null), null);
  assert.equal(home.sourceLine({}), null);
});

test('a source distance has at most one decimal and no trailing .0, like the summary', () => {
  assert.equal(home.sourceLine({ ...PINNED, distance_km: 2 }).sub, 'Cedar & 2nd Ave, 2 km');
  assert.equal(home.sourceLine({ ...PINNED, distance_km: 2.0 }).menu, 'Nearby public monitor, 2 km');
  assert.equal(home.sourceLine({ ...PINNED, distance_km: 1.04 }).sub, 'Cedar & 2nd Ave, 1 km');
  assert.equal(home.sourceLine({ ...PINNED, distance_km: 0.46 }).sub, 'Cedar & 2nd Ave, 0.5 km');
});

test('a public monitor without a name or a distance still reads', () => {
  assert.equal(home.sourceLine({ ...PINNED, name: null }).sub, '1.1 km');
  assert.equal(home.sourceLine({ ...PINNED, name: '  ' }).sub, '1.1 km');
  assert.deepEqual(home.sourceLine({ kind: 'monitor', name: null, distance_km: null }), { name: 'Nearby public monitor', sub: '', menu: 'Nearby public monitor', estimate: false, down: null });
});

test("the chosen monitor isn't reporting: the card shows the estimate and says why; the menu keeps the chosen monitor", () => {
  const s = home.sourceLine({ kind: 'area', name: 'Cedar & 2nd Ave', distance_km: 1.1, area_count: 3, fallback: true });
  assert.deepEqual(s, { name: 'Estimate for your area', sub: 'from 3 public monitors', menu: 'Nearby public monitor, 1.1 km', estimate: true,
    down: "Cedar & 2nd Ave isn't reporting · showing an estimate for your area" });
  assert.equal(home.sourceLine({ kind: 'model', name: null, distance_km: null, fallback: true }).down,
    "The nearby public monitor isn't reporting · showing an estimate for your area");
});

test("AirGradient's list didn't answer: the card shows the estimate without blaming the chosen monitor", () => {
  const s = home.sourceLine({ kind: 'model', name: 'Cedar & 2nd Ave', distance_km: 1.1, area_count: 0, fallback: 'list' });
  assert.deepEqual(s, { name: 'Estimate for your area (Open‑Meteo)', sub: '', menu: 'Nearby public monitor, 1.1 km', estimate: true,
    down: "AirGradient didn't answer · showing an estimate for your area" });
  const st = home.sourceStatus({ kind: 'model', name: 'Cedar & 2nd Ave', distance_km: 1.1, fallback: 'list' }, { locationType: 'outdoor' }, NOW, 'UTC');
  assert.deepEqual(st.card, { tone: 'warn', label: "AirGradient didn't answer · showing an estimate for your area" });
  assert.deepEqual(st.row, { tone: 'warn', text: 'No answer', title: "AirGradient didn't answer · showing an estimate for your area", off: false });
  assert.doesNotMatch(JSON.stringify(st), /reporting/);
  assert.equal(home.sourceLine({ kind: 'area', name: 'X', area_count: 2, fallback: 'monitor' }).down, "X isn't reporting · showing an estimate for your area");
});

test('the source words never say "your outdoor monitor" nor a config word', () => {
  for (const s of [PINNED, { kind: 'area', area_count: 2 }, { kind: 'model' }, { kind: 'area', name: 'X', distance_km: 1, area_count: 2, fallback: true }]) {
    const w = home.sourceLine(s), all = [w.name, w.sub, w.menu, w.down].join(' ');
    assert.doesNotMatch(all, /your outdoor monitor|outdoor_from|\bmodel\b|config/i, JSON.stringify(s));
  }
});

test("the source's status: a public monitor's freshness, an estimate in grey, a monitor that isn't reporting in amber, never red", () => {
  const live = home.sourceStatus(PINNED, { ...FRESH, source: PINNED }, NOW, 'UTC');
  assert.deepEqual(live.card, { tone: 'good', label: 'Online' });
  assert.deepEqual(live.row, home.monitorRow(FRESH, NOW, false, 'UTC'));
  const est = home.sourceStatus({ kind: 'model' }, { locationType: 'outdoor' }, NOW, 'UTC');
  assert.deepEqual(est.card, { tone: 'neutral', label: 'Estimate' });
  assert.deepEqual(est.row, { tone: 'neutral', text: 'Estimate', title: 'Estimate for your area (Open‑Meteo)', off: false });
  const down = home.sourceStatus({ kind: 'area', name: 'Cedar & 2nd Ave', distance_km: 1.1, area_count: 3, fallback: true }, { locationType: 'outdoor' }, NOW, 'UTC');
  assert.deepEqual(down.card, { tone: 'warn', label: "Cedar & 2nd Ave isn't reporting · showing an estimate for your area" });
  assert.deepEqual(down.row, { tone: 'warn', text: 'Not reporting', title: "Cedar & 2nd Ave isn't reporting · showing an estimate for your area", off: false });
});

test('no history request for an outdoor entry without a locationId (an estimate)', () => {
  const from = new Date('2026-11-09T11:00:00Z'), to = new Date('2026-11-09T12:00:00Z');
  assert.equal(home.histUrl({ locationType: 'outdoor', source: { kind: 'area' } }, from, to), null);
  assert.equal(home.histUrl(null, from, to), null);
  assert.equal(home.histUrl({ locationId: 900002 }, from, to), '/api/history/900002?from=2026-11-09T11:00:00.000Z&to=2026-11-09T12:00:00.000Z');
  assert.equal(home.histUrl({ locationId: 0 }, from, to), '/api/history/0?from=2026-11-09T11:00:00.000Z&to=2026-11-09T12:00:00.000Z');
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  const fetchHist = app.slice(app.indexOf('const fetchHist'), app.indexOf('function loadWeek'));
  assert.match(fetchHist, /histUrl\(m, from, to\)/);
  assert.doesNotMatch(app, /\/api\/history\/\$\{m\.locationId\}/);
});

test("an estimate's PM2.5 now is the summary's model hour, only when it is this hour's", () => {
  const tl = { pm: { source: 'model', past: [['2026-11-09T10:00:00+00:00', 8.2], ['2026-11-09T11:00:00+00:00', 9.4]] } };
  assert.deepEqual(home.estimateNow(tl, NOW), { pm: 9.4, at: '2026-11-09T11:00:00+00:00' });   // the hour, for the ring's title
  assert.equal(home.estimateNow(tl, new Date('2026-11-09T14:00:00Z')), null);   // an old summary: no number
  assert.equal(home.estimateNow({ pm: { past: tl.pm.past } }, NOW), null);         // a measured past isn't an estimate
  assert.equal(home.estimateNow({ pm: { source: 'model', past: [] } }, NOW), null);
  assert.equal(home.estimateNow(null, NOW), null);
});

test("an indoor-only home's Home pill greys the outdoor picture and names the source", () => {
  const pill = home.monitorPill({ indoor: 'Bedroom', outdoor: null }, FRESH, { locationType: 'outdoor' }, NOW, {}, 'Estimate for your area');
  assert.match(pill, /class="vhw" data-tip="Indoor · AirGradient ONE: Online"/);
  assert.match(pill, /class="vhw off" data-tip="Outdoor PM2.5: Estimate for your area"><i class="off">/);
  assert.doesNotMatch(pill, /Offline|class="bad"/);
});

test('the Sources label counts the monitors the home has', () => {
  assert.equal(home.sourcesLabel({ smoke: false, pollen: false }, false, true, false), 'Sources: your monitor and weather. Open to see them.');
  assert.equal(home.sourcesLabel({ smoke: false, pollen: false }, false, false, true, false), 'Sources: your monitor and weather. Open to see them.');
  assert.equal(home.sourcesLabel({ smoke: false, pollen: false }, false, false), 'Sources: this monitor and weather. Open to see them.');   // a public monitor's page
});

test("an outdoor-only home: Toddler stays, greyed, with its reason; the indoor card says it isn't set up", () => {
  assert.equal(home.profileOff('toddler', false), 'Needs an indoor monitor');
  assert.equal(home.profileOff('toddler', true), null);
  assert.equal(home.profileOff('sinus', false), null);
  assert.equal(home.profileOff('runner', false), null);
  assert.deepEqual(home.ghostWords(false), { status: 'Not set up', aria: 'Indoor: no indoor monitor' });
  assert.deepEqual(home.ghostWords(true), { status: 'Public monitors are outdoor only', aria: 'Indoor: none, this is a public outdoor monitor' });
});

test("an estimate's card: one plain line on what it covers", () => {
  assert.equal(home.estimateNote(true), 'The estimate covers PM2.5 only. Temperature and humidity are Open‑Meteo’s weather.');
  assert.equal(home.estimateNote(false), 'The estimate covers PM2.5 only.');
});

test("a home with one monitor reads its own entries, whatever else the token sees", () => {
  const IN = { locationId: 1, locationType: 'indoor' }, OUT = { locationId: 2, locationType: 'outdoor' };
  const SRC = { locationType: 'outdoor', source: { kind: 'model' } };
  assert.deepEqual(home.pickEntries([IN, OUT], false, false), { indoor: IN, outdoor: OUT });   // two monitors: as before
  assert.deepEqual(home.pickEntries([IN, OUT, SRC], false, true), { indoor: IN, outdoor: SRC });   // indoor-only: the source
  assert.deepEqual(home.pickEntries([IN], false, true), { indoor: IN, outdoor: null });           // no source entry yet
  assert.deepEqual(home.pickEntries([IN, OUT], true, false), { indoor: null, outdoor: OUT });     // outdoor-only
  assert.deepEqual(home.pickEntries(null, false, false), { indoor: null, outdoor: null });
});

test('a greyed menu row stays greyed: tone off, or Off / Not set up in grey', () => {
  assert.equal(home.rowOff('off', 'Not set up'), true);
  assert.equal(home.rowOff('neutral', 'Off'), true);
  assert.equal(home.rowOff('neutral', 'Not set up'), true);
  assert.equal(home.rowOff('neutral', 'Estimate'), false);
  assert.equal(home.rowOff('good', 'Live · just now'), false);
  assert.equal(home.rowOff('bad', 'Offline'), false);
});

test("an indoor-only home without its source entry: the outdoor card is greyed with one line, the menu row grey, never red", () => {
  const st = home.sourceStatus(null, null, NOW, 'UTC');
  assert.deepEqual(st.card, { tone: 'off', label: 'No outdoor reading yet' });
  assert.deepEqual(st.row, { tone: 'neutral', text: 'No reading yet', title: 'No outdoor reading yet', off: false });
});

test("the neighborhood on an indoor-only home: no You row; the pinned monitor stays with the others, tagged", () => {
  const A = { locationId: 10, locationName: 'A' }, B = { locationId: 11, locationName: 'B' }, OWN = { locationId: 2, locationName: 'Yard' };
  // a two-monitor home: its outdoor monitor is You, as before
  assert.deepEqual(home.nbSplit([OWN, A, B], [1, 2], null), { you: OWN, others: [A, B] });
  // an indoor-only home pinned to A: no You, A stays among the others with its tag
  const s = home.nbSplit([A, B], [1], 10);
  assert.equal(s.you, null);
  assert.deepEqual(s.others, [{ ...A, used: true }, B]);
  const f = { esc: escHtml, pm: v => v.toFixed(1), num: v => v.toFixed(1), temp: v => v + '°' };
  const row = home.nbRowHTML({ ...s.others[0], pm02_corrected: 4, distance_km: 1.1 }, false, home.selfWords(false), '', { limit: 15, barMax: 55, limPct: 27 }, f);
  assert.match(row, /<td class="loc" title="A">A<span class="nb-used"> · used for your outdoor PM2\.5<\/span><\/td>/);
  assert.doesNotMatch(home.nbRowHTML({ ...B, pm02_corrected: 4, distance_km: 2 }, false, home.selfWords(false), '', { limit: 15, barMax: 55, limPct: 27 }, f), /nb-used/);
  assert.equal(home.NB_USED, 'used for your outdoor PM2.5');
});

test('nbCountText: with no Show more button, the count leads the credit line', () => {
  assert.equal(home.nbCountText(6), '6 public monitors within 15 km');
  assert.equal(home.nbCountText(1), '1 public monitor within 15 km');
  assert.equal(home.nbCountText(0), '');
});

test("monitorPill: an indoor-only home's chosen public monitor shows live, an estimate greyed", () => {
  const now = new Date('2026-11-10T03:30:00Z'), place = { indoor: 'apartment', outdoor: null };
  const indoor = { timestamp: '2026-11-10T03:28:00Z' };
  const pinned = { timestamp: '2026-11-10T03:25:00Z', source: { kind: 'monitor', name: 'Long Island City' } };
  const live = home.monitorPill(place, indoor, pinned, now, {}, 'Nearby public monitor, 1.4 km');
  assert.equal((live.match(/class="vhw off"/g) || []).length, 0);
  const est = home.monitorPill(place, indoor, { locationType: 'outdoor', source: { kind: 'model' } }, now, {}, 'Estimate for your area');
  assert.equal((est.match(/class="vhw off"/g) || []).length, 1);
});

test('the demo has one top area above the page, empty and hidden until the demo draws it; the band and the dark bar are gone', () => {
  const html = readFileSync(new URL('index.html', root), 'utf8');
  assert.match(html, /<header class="demo-top" id="demo-top" hidden><\/header>/);
  assert.ok(html.indexOf('id="demo-top"') < html.indexOf('<div class="page">'));
  assert.doesNotMatch(html, /entry-band|demo-bar/);
});


// ── The logo (mock 94, round 8 a): its dot says whether the readings are fresh, green while they are, grey otherwise ──
test('readingsState: fresh up to 10 min, otherwise when the readings are from, in words for the logo and the summary', () => {
  const NOW = new Date('2026-11-13T12:20:00Z'), at = m => new Date(NOW - m * 60000).toISOString();
  assert.deepEqual(home.readingsState(at(4), NOW, { tz: 'UTC' }), { fresh: true, status: 'Live readings', meta: '' });
  assert.deepEqual(home.readingsState(at(10), NOW, { tz: 'UTC' }).fresh, true);
  assert.deepEqual(home.readingsState(at(25), NOW, { tz: 'UTC' }), { fresh: false, status: 'Readings as of 11:55 AM', meta: '25 min old' });
  assert.deepEqual(home.readingsState(at(180), NOW, { tz: 'UTC' }), { fresh: false, status: 'Readings as of 9:20 AM', meta: '3 h old' });
  assert.deepEqual(home.readingsState(at(3000), NOW, { tz: 'UTC' }), { fresh: false, status: 'Readings as of Nov 11, 10:20 AM', meta: '2 days old' });
  assert.deepEqual(home.readingsState(at(4), NOW, { tz: 'UTC', offline: true }), { fresh: false, status: 'Offline · last reading 12:16 PM', meta: 'Last reading 12:16 PM' });
  assert.deepEqual(home.readingsState(null, NOW, { tz: 'UTC' }), { fresh: false, status: 'Loading readings', meta: '' });
  assert.deepEqual(home.readingsState(null, NOW, { tz: 'UTC', failed: true }), { fresh: false, status: 'Readings did not load', meta: 'Readings did not load' });
  assert.deepEqual(home.readingsState(null, NOW, { tz: 'UTC', offline: true }), { fresh: false, status: 'Offline', meta: 'Offline' });   // in words on screen, not only the grey dot
});

test('the logo follows freshness: green while fresh, grey when stale, offline or not loaded; never amber or red', () => {
  const app = readFileSync(new URL('static/app.js', root), 'utf8');
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  const html = readFileSync(new URL('index.html', root), 'utf8');
  const show = app.slice(app.indexOf('function showUpdated'), app.indexOf('function startSpin'));
  assert.match(show, /readingsState\(lastStamp, readingsNow\(\), \{ offline, failed: loadFailed, tz: TZ \}\)/);
  assert.match(show, /mark\.classList\.toggle\('is-stale', !s\.fresh\)/);
  assert.match(show, /mark\.title = name/);
  assert.match(show, /\$\('mark-name'\)\.textContent = name/);
  assert.doesNotMatch(show, /title\.textContent = (?!fresh)/);   // the hidden heading stays Today or Tonight
  // the dot and its glow take --logo-dot: green by default, grey on .is-stale
  assert.match(css, /--logo-live: #4fd68f;/);
  assert.match(css, /--logo-idle: #a7adb6;/);
  assert.match(css, /svg\.mark, svg\.dt-mark \{[^}]*--logo-dot: var\(--logo-live\);/);
  assert.match(css, /\.now-mark\.is-stale svg\.mark \{ --logo-dot: var\(--logo-idle\); --logo-glow-a: 0; \}/);   // stale: flat grey, no glow (not hue alone)
  assert.match(css, /\.lg-dot, svg\.mark \.lg-glow[^{]*\{ fill: var\(--logo-dot\); \}/);
  const marks = css.slice(css.indexOf('/* The logo'), css.indexOf('/* The logo') + 3000);
  assert.doesNotMatch(marks, /--(?:warn|bad)/);
  // the logo on the page: the house, the window bar, the roof's sky, the glow and the dot; no moon, no live sky gradient
  const svg = html.match(/<div class="site now-mark[^"]*"[^>]*>(<svg class="mark".*?<\/svg>)/)[1];
  assert.match(svg, /<path d="M13\.8 3\.2Q16 1\.4 18\.2 3\.2L30\.1 12\.8Q31 13\.5 31 14\.7V25Q31 31 25 31H7Q1 31 1 25V14\.7Q1 13\.5 1\.9 12\.8Z" fill="#fff"\/>/);
  assert.match(svg, /<path d="M0 17\.5h32M16 17\.5v15" stroke="#000" stroke-width="2\.6"\/>/);
  assert.match(svg, /<path class="lg-glow" d="M8\.6 16\.2A7\.4 7\.4 0 0 1 23\.4 16\.2Z"\/><path class="lg-dot" d="M11\.6 16\.2A4\.4 4\.4 0 0 1 20\.4 16\.2Z"\/>/);
  assert.doesNotMatch(html + app + css, /mk-g|mk-sky|mk-fr|mk-br|mk-dot|--mark-top|--mark-hor/);
  assert.match(html, /<span class="vh" id="mark-name">Home Air Quality<\/span>/);
});

test('the weather line has no time and no live dot; the "Today" heading is hidden but still read out', () => {
  const sky = readFileSync(new URL('static/sky.js', root), 'utf8');
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  assert.doesNotMatch(sky, /cap-live/);
  assert.doesNotMatch(css, /cap-live/);
  assert.match(css, /\.now-h \{ position: absolute !important; width: 1px; height: 1px;[^}]*clip: rect\(0 0 0 0\)/);
  assert.doesNotMatch(css, /\.now-h \{[^}]*display: none/);
});

test('the summary line shows one status: the readings\' age or "Updated …", never both, on one line on a phone', () => {
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  // stale or offline: the age ("40 min old", "Last reading 3:16 PM", "Offline") replaces "Updated just now", which would contradict it
  assert.match(css, /#updated:not\(:empty\) ~ #s-ago \{ display: none !important; \}/);
  // the dot before the age only where the line goes on after "from 6 sources" (a computer); a phone starts a new row with it
  assert.match(css, /@media \(min-width: 481px\) \{\s*:root \.sum-card > \.s-bar #updated:not\(:empty\)::before \{ content: "· "; color: var\(--muted\); \}/);
  assert.doesNotMatch(css, /^:root \.sum-card > \.s-bar #updated:not\(:empty\)::before/m);
  // the status never wraps inside itself (Sacha's phone, offline: "Updated / just now" on two lines)
  assert.match(css, /:root \.sum-card > \.s-bar #updated, :root \.sum-card > \.s-bar #s-ago \{ white-space: nowrap; \}/);
  // the age sits on the same baseline as "Updated just now" and "from 6 sources": the same font box (design check, 1 px high before)
  assert.match(css, /:root \.sum-card > \.s-bar #updated \{ font: 400 13px\/1\.2 Inter, sans-serif; line-height: 20px !important; display: inline-block; margin: 0 !important; padding: 0 !important; \}/);
  assert.match(css, /:root \.sum-card > \.s-bar #updated:empty \{ display: none; \}/);   // fresh: takes no slot in the row
});

test('on a phone the summary header is two rows: title and profile icons, then the status across the full width', () => {
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  // the longest status ("Last reading Nov 12, 1:23 PM") pushed the refresh button under the icons when row 2 shared their column
  const phone = css.slice(css.indexOf('/* Summary profile icons and phone byline layout */'));
  const block = phone.slice(phone.indexOf('@media (max-width: 480px)'), phone.indexOf('.blocks .pop-head'));
  assert.match(block, /:root \.sum-card > \.s-bar \{ display: grid !important; grid-template-columns: minmax\(0, 1fr\) auto;/);
  assert.match(block, /\.s-meta \{ display: contents; \}/);
  assert.match(block, /:root \.sum-card > \.s-bar \.s-tools \{ grid-row: 2; grid-column: 1 \/ -1;/);
  assert.match(block, /\.s-profiles \{ grid-row: 1; grid-column: 2;/);
});

test('the header logo is 40 px on a computer and 32 on a phone, as tall as the menu beside it (mock 94, round 21)', () => {
  const css = readFileSync(new URL('static/app.css', root), 'utf8');
  assert.match(css, /\n\.site svg\.mark \{ flex: none; width: 40px !important; height: 40px !important; \}/);
  assert.match(css, /@media \(max-width: 640px\) \{\s*\.bar \.site svg\.mark, \.site svg\.mark \{ width: 32px !important; height: 32px !important; \}/);
  assert.match(css, /:root \{ --dt-row: 40px; --dt-mark: 32px; \}/);
});
