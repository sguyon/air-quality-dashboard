// The demo's top area and the public-monitor picker (static/picker.js): what they draw, and the URL every /api call takes.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const picker = require('../static/picker.js');
const LIMITS = { pm: 15, pm_high: 35 };
const MOMENTS = [{ key: 'rush', label: 'Morning rush', n: 1 }, { key: 'clear', label: 'All clear', n: 2 }, { key: 'humid', label: 'Humid evening', n: 3 }];
const current = html => [...html.matchAll(/<a [^>]*aria-current="page"[^>]*>([^<]*)<\/a>/g)].map(m => m[1]);

const TITLES = ['See a demo', 'See a live monitor near you', 'Set up your own monitor'];

test('top on sample 2: only 2 is marked, no sample name, the three ways in order, the pitch with its repo link', () => {
  const html = picker.topHTML({ now: { moment: 'clear', moments: MOMENTS } });
  assert.deepEqual(current(html), ['2']);
  for (const n of [1, 2, 3]) assert.match(html, new RegExp(`<a href="\\?sample=${n}"`));
  assert.doesNotMatch(html, /dt-now|>All clear</);   // no sample name under See a demo (Sacha, 2026-11-12: remove it)
  assert.match(html, /<h1 class="dt-name"><svg class="dt-mark"[^>]*>.*?<\/svg>Home Air Quality <span class="dt-tag">Demo<\/span><\/h1>/);
  assert.match(html, /Your AirGradient monitor's readings and the forecast, turned into timed actions, each with a why\. <span>Free and <a href="https:\/\/github\.com\/sguyon\/home-air-quality">open source<\/a>\. You run it for your home\.<\/span>/);
  const at = TITLES.map(t => html.indexOf(`</span>${t}</p>`));
  assert.ok(at[0] > 0 && at[0] < at[1] && at[1] < at[2], String(at));
  assert.match(html, /Sample data from a made-up home\./);
  assert.match(html, /Real readings from a public AirGradient monitor\./);
  assert.match(html, /You install it, with a coding agent or Docker\./);
  // each way's control, last: SAMPLE 1 2 3; Select a monitor (the live dot, the drawn chevron); Setup guide (the drawn arrow)
  assert.match(html, /<span class="dt-lab" id="dt-lab">Sample<\/span><nav class="dt-seg" aria-labelledby="dt-lab">/);
  assert.match(html, /<button type="button" class="dt-pick" id="db-pick" aria-haspopup="dialog" aria-expanded="false" aria-controls="db-pop"><i class="live" aria-hidden="true"><\/i><span class="dt-pick-t">Select a monitor<\/span><svg class="i"[^>]*>.*?<\/svg><\/button>/);
  assert.match(html, /<span class="dt-pickwrap" id="db-pickwrap">/);
  assert.match(html, /<a class="dt-btn" href="https:\/\/github\.com\/sguyon\/home-air-quality#installation" target="_blank" rel="noopener">Setup guide<svg class="dt-bi"[^>]*>.*?<\/svg><\/a>/);
  assert.equal((html.match(/<svg /g) || []).length, 6);   // the logo, three way icons, the chevron, the arrow
  // every arrow and chevron drawn: a text arrow shows as an emoji on iOS (Sacha, 2026-11-12); the old bar's parts are gone
  assert.doesNotMatch(html, /[↗↓▾→]/);
  assert.doesNotMatch(html, /Show me|Or live|GitHub<|db-gh|aria-label="Source and setup/);
});

test("top on a monitor's page: no sample marked or named, the escaped name in the button and its accessible name", () => {
  const html = picker.topHTML({ public: { id: 7, name: 'Roof <b>bold</b> & co', contributor: 'Ann', url: '' } });
  assert.deepEqual(current(html), []);
  for (const n of [1, 2, 3]) assert.match(html, new RegExp(`href="\\?sample=${n}"`));   // samples are still one click away
  assert.doesNotMatch(html, /class="dt-now"/);
  assert.match(html, /<button type="button" class="dt-pick is-chosen" id="db-pick" aria-label="Monitor: Roof &lt;b&gt;bold&lt;\/b&gt; &amp; co\. Change monitor" aria-haspopup="dialog"/);
  assert.match(html, /<span class="dt-pick-t">Roof &lt;b&gt;bold&lt;\/b&gt; &amp; co<\/span>/);
  assert.doesNotMatch(html, /<b>bold|Select a monitor/);
});

test("top when the monitor can't be shown: Select a monitor, and the sample the page shows instead is marked", () => {
  const html = picker.topHTML({ public: { id: 99, error: "Monitor 99 isn't on AirGradient's public map" }, now: { moment: 'rush', moments: MOMENTS } });
  assert.deepEqual(current(html), ['1']);
  assert.doesNotMatch(html, /dt-now|>Morning rush</);
  assert.match(html, /Select a monitor/);
  assert.doesNotMatch(html, /is-chosen|aria-label="Monitor:/);
});

test('top on a hidden one-monitor moment: no sample marked or named', () => {
  const html = picker.topHTML({ now: { moment: 'indoor-near', moments: MOMENTS } });
  assert.deepEqual(current(html), []);
  assert.doesNotMatch(html, /class="dt-now"/);
});

const ROWS = [
  { locationId: 5, name: 'Greenpoint <i>Roof</i>', street: 'Greenpoint Ave', contributor: 'Dana <script>x</script>', distance_km: 0.53, pm02: 22, offline: false },
  { locationId: 7, name: 'Linden', street: 'Linden St', contributor: 'Priya', distance_km: 12.4, pm02: 8.26, offline: false },
  { locationId: 9, name: 'Gone', street: null, contributor: null, distance_km: 2, pm02: null, offline: true },
];

test('rows: name, street · distance, owner, PM2.5 with its band word; the current one marked; all escaped', () => {
  const html = picker.rowsHTML(ROWS, 7, LIMITS);
  assert.equal((html.match(/<li>/g) || []).length, 3);
  assert.match(html, /href="\?monitor=5"/);
  assert.match(html, /<a class="pm-row" href="\?monitor=7" aria-current="page">/);
  assert.equal((html.match(/aria-current/g) || []).length, 1);
  assert.match(html, /Greenpoint &lt;i&gt;Roof&lt;\/i&gt;/);
  assert.match(html, /Shared by Dana &lt;script&gt;x&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>|<i>Roof/);
  assert.match(html, /Greenpoint Ave · 0\.5 km/);
  assert.match(html, /Linden St · 12 km/);
  assert.match(html, /<b>22<\/b><em>Moderate<\/em>/);
  assert.match(html, /<b>8\.3<\/b><em>Good<\/em>/);
  assert.match(html, /<b>—<\/b><em>Offline<\/em>/);
  assert.doesNotMatch(html, /Shared by null|null ·/);
});

test('roundCoord keeps 2 decimals (about 1 km) before a location leaves the browser', () => {
  assert.equal(picker.roundCoord(40.73456), 40.73);
  assert.equal(picker.roundCoord(-73.95123), -73.95);
  assert.equal(picker.roundCoord('13.756'), 13.76);
});

test('apiUrl names the monitor on its page, the moment on a sample, nothing for a real home', () => {
  assert.match(picker.apiUrl({ public: { id: 7 } }, '/api/current'), /\?monitor=7$/);
  assert.match(picker.apiUrl({ public: { id: 7, error: 'x' } }, '/api/history/1?x=1'), /\?x=1&monitor=7$/);
  assert.equal(picker.apiUrl({ now: { moment: 'rush' } }, '/api/current'), '/api/current?moment=rush');
  assert.equal(picker.apiUrl({}, '/api/current'), '/api/current');
});

test("app.js's apiUrl is the picker's, so every /api call names the monitor", () => {
  const app = readFileSync(new URL('../static/app.js', import.meta.url), 'utf8');
  assert.match(app, /const apiUrl = url => Picker\.apiUrl\(APP, url\);/);
  assert.doesNotMatch(app, /demo-moments/);
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  assert.ok(html.indexOf('/static/home.js') < html.indexOf('/static/picker.js') && html.indexOf('/static/picker.js') < html.indexOf('/static/app.js'));
});

test('rows draw without limits (Node has no window.APP): no throw, the number, no band word', () => {
  const html = picker.rowsHTML(ROWS, 7);
  assert.match(html, /<b>22<\/b><em><\/em>/);
  assert.match(html, /<b>—<\/b><em>Offline<\/em>/);
});

const DEMO_APP = { now: { moment: 'rush', moments: MOMENTS } };

test('top: on every demo page (the default, a sample, a moment, a monitor), also with tracking parameters', () => {
  for (const s of ['', '?utm_source=reddit&fbclid=x1', '?sample=2', '?moment=clear', '?moment=indoor-near', '?x=1&sample=2'])
    assert.equal(picker.showsTop(DEMO_APP, s), true, s);
  assert.equal(picker.showsTop({ public: { id: 7, name: 'Roof' } }, '?monitor=7'), true);
  assert.equal(picker.showsTop({ public: { id: 99, error: 'x' }, now: DEMO_APP.now }, '?monitor=99'), true);
});

test('top: not in screenshots, on a real home or the token card', () => {
  for (const s of ['?shot', '?shot=dark', '?sample=2&shot'])
    assert.equal(picker.showsTop(DEMO_APP, s), false, s);
  assert.equal(picker.showsTop({}, ''), false);                        // a real home: no APP.now, no APP.public
  assert.equal(picker.showsTop({ state: 'no_token' }, ''), false);     // the token card
  assert.equal(picker.showsTop(null, ''), false);
});

test("a click on the picker's button counts as inside the picker, so the picker doesn't close itself", () => {
  const el = matches => ({ isConnected: true, closest: sel => (sel.includes(matches) ? {} : null) });
  assert.equal(picker.insidePicker(el('[aria-controls="db-pop"]')), true);
  assert.equal(picker.insidePicker(el('#db-pickwrap')), true);
  assert.equal(picker.insidePicker(el('.sum-card')), false);
  assert.equal(picker.insidePicker(null), false);
  assert.match(picker.topHTML(DEMO_APP), /id="db-pick"[^>]*aria-controls="db-pop"/);
  assert.equal(picker.bannerHTML, undefined);   // the dark bar and the band are gone: one top area
  assert.equal(picker.bandHTML, undefined);
  assert.equal(picker.showsBand, undefined);
});

test("location off: the note says the list is around the default place, not the visitor's location", () => {
  assert.equal(picker.offNote('New York'), 'Location is off, so this list is around New York. Type a place to see another.');
});

// The page part of picker.js, run against a small stand-in for the page: each element the picker looks up by id, the
// document's listeners and the focused element. Enough to follow the picker's behaviour without a browser.
function page() {
  const els = new Map(), doc = {};
  let active = null;
  const el = id => {
    if (!els.has(id)) els.set(id, { id, hidden: id === 'db-pop', attrs: {}, on: {}, isConnected: true, innerHTML: '', textContent: '', value: '',
      inPicker: id === 'db-pick' || id === 'db-pickwrap' || id.startsWith('pm-'), parentElement: { hidden: false },
      setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k] ?? null; },
      addEventListener(t, f) { (this.on[t] ||= []).push(f); }, insertAdjacentHTML() {}, focus() { active = this; },
      closest() { return this.inPicker ? this : null; } });
    return els.get(id);
  };
  const fire = (t, e) => (doc[t] || []).forEach(f => f(e));
  // a click: the element's own listeners, then the document's (the event bubbles up)
  const click = target => { (target.on.click || []).forEach(f => f({ target })); fire('click', { target }); };
  const document = { getElementById: el, addEventListener: (t, f) => (doc[t] ||= []).push(f), get activeElement() { return active; },
    querySelectorAll: sel => (sel === '[aria-controls="db-pop"]' ? [el('db-pick')] : []) };
  const sandbox = { document, navigator: {}, URLSearchParams, console,
    fetch: async () => ({ ok: true, json: async () => ({ monitors: [] }) }) };
  sandbox.window = sandbox;
  vm.runInNewContext(readFileSync(new URL('../static/picker.js', import.meta.url), 'utf8'), sandbox);
  return { Picker: sandbox.Picker, el, click, key: key => fire('keydown', { key }), get active() { return active; } };
}

test('the picker opens from its button and moves focus into it; Esc closes it and focus returns to the button', () => {
  const pg = page();
  pg.Picker.mount(pg.el('demo-top'), DEMO_APP);
  assert.equal(pg.el('demo-top').hidden, false);
  assert.match(pg.el('demo-top').innerHTML, /id="db-pick"/);   // the top area holds the picker's button
  assert.equal(pg.el('db-pop').hidden, true);
  pg.click(pg.el('db-pick'));
  assert.equal(pg.el('db-pop').hidden, false);
  assert.equal(pg.el('db-pick').getAttribute('aria-expanded'), 'true');
  assert.equal(pg.active.id, 'pm-near');
  pg.key('Escape');
  assert.equal(pg.el('db-pop').hidden, true);
  assert.equal(pg.el('db-pick').getAttribute('aria-expanded'), 'false');
  assert.equal(pg.active.id, 'db-pick');
});

test('a tap outside closes the picker; a tap inside it or on its button again does what it says', () => {
  const pg = page();
  pg.Picker.mount(pg.el('demo-top'), DEMO_APP);
  pg.click(pg.el('db-pick'));
  pg.click(pg.el('pm-near'));                         // inside: stays open
  assert.equal(pg.el('db-pop').hidden, false);
  pg.click(pg.el('summary'));                         // outside
  assert.equal(pg.el('db-pop').hidden, true);
  assert.equal(pg.el('db-pick').getAttribute('aria-expanded'), 'false');
  pg.click(pg.el('db-pick'));                         // open, then the button again closes it
  pg.click(pg.el('db-pick'));
  assert.equal(pg.el('db-pop').hidden, true);
});

test("an unknown monitor's page opens the picker with the reason, without taking focus", () => {
  const pg = page();
  pg.Picker.mount(pg.el('demo-top'), { public: { id: 99, error: "Monitor 99 isn't on AirGradient's public map" }, now: DEMO_APP.now });
  assert.equal(pg.el('db-pop').hidden, false);
  assert.equal(pg.el('pm-error').textContent, "Monitor 99 isn't on AirGradient's public map");
  assert.equal(pg.active, null);
});
