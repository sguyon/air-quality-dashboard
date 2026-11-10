// The demo banner and the public-monitor picker (static/picker.js): what they draw, and the URL every /api call takes.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const picker = require('../static/picker.js');
const LIMITS = { pm: 15, pm_high: 35 };
const MOMENTS = [{ key: 'rush', label: 'Morning rush', n: 1 }, { key: 'clear', label: 'All clear', n: 2 }, { key: 'humid', label: 'Humid evening', n: 3 }];
const current = html => [...html.matchAll(/<a [^>]*aria-current="page"[^>]*>([^<]*)<\/a>/g)].map(m => m[1]);

test('banner on sample 2: only 2 is marked, the dropdown says Pick a monitor', () => {
  const html = picker.bannerHTML({ now: { moment: 'clear', moments: MOMENTS } });
  assert.deepEqual(current(html), ['2']);
  for (const n of [1, 2, 3]) assert.match(html, new RegExp(`href="\\?sample=${n}"`));
  assert.match(html, />Demo</);
  assert.match(html, /Sample data/);
  assert.match(html, /Or live: a public AirGradient monitor/);
  assert.match(html, /Pick a monitor/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /href="https:\/\/github\.com\/sguyon\/home-air-quality#installation"[^>]*>.*Source and setup<\/a>/);
});

test("banner on a monitor's page: no sample marked, the dropdown shows the escaped name", () => {
  const html = picker.bannerHTML({ public: { id: 7, name: 'Roof <b>bold</b> & co', contributor: 'Ann', url: '' } });
  assert.deepEqual(current(html), []);
  for (const n of [1, 2, 3]) assert.match(html, new RegExp(`href="\\?sample=${n}"`));   // samples are still one click away
  assert.match(html, /Roof &lt;b&gt;bold&lt;\/b&gt; &amp; co/);
  assert.doesNotMatch(html, /<b>bold/);
  assert.doesNotMatch(html, /Pick a monitor/);
});

test("banner when the monitor can't be shown: Pick a monitor, and the sample the page shows instead is marked", () => {
  const html = picker.bannerHTML({ public: { id: 99, error: "Monitor 99 isn't on AirGradient's public map" }, now: { moment: 'rush', moments: MOMENTS } });
  assert.deepEqual(current(html), ['1']);
  assert.match(html, /Pick a monitor/);
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
