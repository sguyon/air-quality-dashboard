// Home Air Quality: data, readings, summary, charts, header panels.
const ICONS = {"toddler": "<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M10 16c.5.3 1.2.5 2 .5s1.5-.2 2-.5\"/><path d=\"M15 12h.01\"/><path d=\"M19.38 6.813A9 9 0 0 1 20.8 10.2a2 2 0 0 1 0 3.6 9 9 0 0 1-17.6 0 2 2 0 0 1 0-3.6A9 9 0 0 1 12 3c2 0 3.5 1.1 3.5 2.5s-.9 2.5-2 2.5c-.8 0-1.5-.4-1.5-1\"/><path d=\"M9 12h.01\"/></svg>", "sinus": "<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M12.8 19.6A2 2 0 1 0 14 16H2\"/><path d=\"M17.5 8a2.5 2.5 0 1 1 2 4H2\"/><path d=\"M9.8 4.4A2 2 0 1 1 11 8H2\"/></svg>", "runner": "<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><circle cx=\"12\" cy=\"5\" r=\"1\"/><path d=\"m9 20 3-6 3 6\"/><path d=\"m6 8 6 2 6-2\"/><path d=\"M12 10v4\"/></svg>", "drop": "<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><path d=\"M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z\"/></svg>", "one": "<svg aria-hidden=\"true\" viewBox=\"0 0 48 48\" width=\"44\" height=\"44\" shape-rendering=\"geometricPrecision\"> <defs> <linearGradient id=\"hw8face\" x1=\"0\" y1=\"0\" x2=\".35\" y2=\"1\"><stop offset=\"0\" stop-color=\"#fbfbfc\"/><stop offset=\"1\" stop-color=\"#e9ebee\"/></linearGradient> <linearGradient id=\"hw8edge\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#d5d9de\"/><stop offset=\"1\" stop-color=\"#bfc5cc\"/></linearGradient> <linearGradient id=\"hw8oled\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#14171c\"/><stop offset=\"1\" stop-color=\"#05070a\"/></linearGradient> <radialGradient id=\"hw8sh\" cx=\".5\" cy=\".5\" r=\".5\"><stop offset=\"0\" stop-color=\"#0f172a\" stop-opacity=\".22\"/><stop offset=\"1\" stop-color=\"#0f172a\" stop-opacity=\"0\"/></radialGradient> </defs> <ellipse cx=\"24\" cy=\"42.6\" rx=\"18\" ry=\"2.4\" fill=\"url(#hw8sh)\"/> <rect x=\"5\" y=\"8.5\" width=\"38\" height=\"33\" rx=\"8\" fill=\"url(#hw8edge)\"/> <g fill=\"#aab1b9\"><rect x=\"11\" y=\"38.6\" width=\"5\" height=\".9\" rx=\".45\"/><rect x=\"18.5\" y=\"38.6\" width=\"5\" height=\".9\" rx=\".45\"/><rect x=\"26\" y=\"38.6\" width=\"5\" height=\".9\" rx=\".45\"/><rect x=\"33.5\" y=\"38.6\" width=\"4\" height=\".9\" rx=\".45\"/></g> <rect x=\"5\" y=\"5.5\" width=\"38\" height=\"32.5\" rx=\"8\" fill=\"url(#hw8face)\" stroke=\"#d3d8de\" stroke-width=\".6\"/> <path d=\"M12.5 6.25h23a7.4 7.4 0 0 1 4.6 1.6\" stroke=\"#ffffff\" stroke-width=\".7\" stroke-linecap=\"round\" fill=\"none\" opacity=\".8\"/> <g> <circle cx=\"11.6\" cy=\"11.6\" r=\"1.05\" fill=\"#22c55e\"/><circle cx=\"14.1\" cy=\"11.6\" r=\"1.05\" fill=\"#22c55e\"/><circle cx=\"16.6\" cy=\"11.6\" r=\"1.05\" fill=\"#2fc95b\"/> <circle cx=\"19.1\" cy=\"11.6\" r=\"1.05\" fill=\"#4ccf55\"/><circle cx=\"21.6\" cy=\"11.6\" r=\"1.05\" fill=\"#74d34c\"/><circle cx=\"24.1\" cy=\"11.6\" r=\"1.05\" fill=\"#a3d642\"/> <circle cx=\"26.6\" cy=\"11.6\" r=\"1.05\" fill=\"#cdd23a\"/><circle cx=\"29.1\" cy=\"11.6\" r=\"1.05\" fill=\"#f2c537\"/><circle cx=\"31.6\" cy=\"11.6\" r=\"1.05\" fill=\"#f6ab35\"/> <circle cx=\"34.1\" cy=\"11.6\" r=\"1.05\" fill=\"#f59234\"/><circle cx=\"36.6\" cy=\"11.6\" r=\"1.05\" fill=\"#d9dde2\"/> </g> <g fill=\"#ffffff\" opacity=\".55\"><circle cx=\"11.3\" cy=\"11.2\" r=\".3\"/><circle cx=\"19.0\" cy=\"11.2\" r=\".3\"/><circle cx=\"26.5\" cy=\"11.2\" r=\".3\"/><circle cx=\"34.0\" cy=\"11.2\" r=\".3\"/></g> <rect x=\"23.5\" y=\"17\" width=\"14.5\" height=\"9.6\" rx=\"1.2\" fill=\"url(#hw8oled)\" stroke=\"#2a2f37\" stroke-width=\".5\"/> <g fill=\"#eef3f8\"> <rect x=\"25\" y=\"18.8\" width=\"7.6\" height=\"1\" rx=\".35\"/><rect x=\"25\" y=\"20.8\" width=\"5.6\" height=\"1\" rx=\".35\"/> <rect x=\"25\" y=\"22.8\" width=\"6.8\" height=\"1\" rx=\".35\"/><rect x=\"25\" y=\"24.6\" width=\"4.8\" height=\".8\" rx=\".35\" opacity=\".7\"/> </g> <rect x=\"33.8\" y=\"18.8\" width=\"2.6\" height=\"1\" rx=\".35\" fill=\"#7fd3e6\"/> <g fill=\"none\" stroke=\"#8d949c\" stroke-linecap=\"round\"><path d=\"M11.61 31.70A1.67 1.67 0 1 0 11.61 34.52\" stroke-width=\"0.41\"/><path d=\"M11.10 32.19A1.04 1.04 0 1 0 11.10 34.03\" stroke-width=\"0.24\" opacity=\".8\"/></g><text x=\"10.20\" y=\"34.00\" font-family=\"Inter, Helvetica, Arial, sans-serif\" font-size=\"2.70\" fill=\"#8d949c\" letter-spacing=\"-.04\"><tspan font-weight=\"700\" fill=\"#7b828a\">air</tspan><tspan font-weight=\"500\">gradient</tspan></text> </svg>", "openair": "<svg aria-hidden=\"true\" viewBox=\"0 0 48 48\" width=\"44\" height=\"44\"> <defs> <linearGradient id=\"hw6shell\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\"><stop offset=\"0\" stop-color=\"#eef1f5\"/><stop offset=\".35\" stop-color=\"#ffffff\"/><stop offset=\"1\" stop-color=\"#dfe4ea\"/></linearGradient> <linearGradient id=\"hw6shellTop\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#ffffff\" stop-opacity=\".5\"/><stop offset=\"1\" stop-color=\"#ffffff\" stop-opacity=\"0\"/></linearGradient> <linearGradient id=\"hw6base\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\"><stop offset=\"0\" stop-color=\"#3d8ee6\"/><stop offset=\"1\" stop-color=\"#1f62c4\"/></linearGradient> <radialGradient id=\"hw6shadow\" cx=\".5\" cy=\".5\" r=\".5\"><stop offset=\"0\" stop-color=\"#0f172a\" stop-opacity=\".22\"/><stop offset=\"1\" stop-color=\"#0f172a\" stop-opacity=\"0\"/></radialGradient> </defs> <ellipse cx=\"24\" cy=\"41.6\" rx=\"17\" ry=\"2.4\" fill=\"url(#hw6shadow)\"/> <path d=\"M27.6 37.5c0 3 1.6 4.6 5 6.4\" stroke=\"#8e98a3\" stroke-width=\"2\" fill=\"none\" stroke-linecap=\"round\"/> <path d=\"M27.6 37.5c0 3 1.6 4.6 5 6.4\" stroke=\"#d6dce3\" stroke-width=\".8\" fill=\"none\" stroke-linecap=\"round\" transform=\"translate(-.35 -.2)\"/> <rect x=\"7.6\" y=\"31\" width=\"32.8\" height=\"7.6\" rx=\"3.3\" fill=\"url(#hw6base)\"/> <rect x=\"9\" y=\"32.2\" width=\"30\" height=\"1.2\" rx=\".6\" fill=\"#ffffff\" opacity=\".28\"/> <path d=\"M8.2 31.2V15.5C8.2 11 11 8 15.5 8h17C37 8 39.8 11 39.8 15.5v15.7c0 .5-.4.8-.9.8h-1.6c-.8 0-1.3-.4-1.6-1.1-.4-.9-1.1-1.5-2.1-1.5H14.4c-1 0-1.7.6-2.1 1.5-.3.7-.8 1.1-1.6 1.1H9c-.5 0-.8-.3-.8-.8z\" fill=\"url(#hw6shell)\" stroke=\"#c6ced7\" stroke-width=\".8\" stroke-linejoin=\"round\"/> <path d=\"M9.4 15.3C9.4 11.8 11.8 9.3 15.5 9.3h17c3.7 0 6.1 2.5 6.1 6v3H9.4z\" fill=\"url(#hw6shellTop)\"/> <path d=\"M12.5 9.6h23\" stroke=\"#ffffff\" stroke-width=\"1\" stroke-linecap=\"round\" opacity=\".95\"/> <g fill=\"none\" stroke=\"#8d949c\" stroke-linecap=\"round\"><path d=\"M18.16 23.85A1.86 1.86 0 1 0 18.16 26.97\" stroke-width=\"0.45\"/><path d=\"M17.61 24.39A1.15 1.15 0 1 0 17.61 26.43\" stroke-width=\"0.27\" opacity=\".8\"/></g><text x=\"16.60\" y=\"26.40\" font-family=\"Inter, Helvetica, Arial, sans-serif\" font-size=\"3.00\" fill=\"#8d949c\" letter-spacing=\"-.04\"><tspan font-weight=\"700\" fill=\"#7b828a\">air</tspan><tspan font-weight=\"500\">gradient</tspan></text> </svg>", "alert": "<svg class=\"i\" viewBox=\"0 0 24 24\" aria-hidden=\"true\"><circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M12 8v4\"/><path d=\"M12 16h.01\"/></svg>"};
const TZ = 'America/New_York';
const PM_FINE = 12, PM_HIGH = 35, CO2_OPEN = 800;
const RH_LOW = 30, RH_HIGH = 50, RH_DAMP = 60;   // same as server.py
// Peak hours as the server's BQE estimate counts them: [start, end).
const RUSH = [[7, 10, 'morning'], [16, 20, 'evening']];
const RANGE_HOURS = { '1h': 1, '6h': 6, '24h': 24, '7d': 168 };
const RANGE_LABEL = { '1h': 'Last hour', '6h': 'Last 6 hours', '24h': 'Last 24 hours', '7d': 'Last 7 days' };
const READ_MAX_AGE = 10 * 60 * 1000;
const CACHE_KEY = 'air-read-v2';
const FILTER_NAME = { toddler: 'Toddler', sinus: 'Sinus and allergy', runner: 'Runner' };

const state = { range: '1h', indoor: null, outdoor: null, neighbors: [], read: null, readAt: 0, readKey: '' };

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// Zero is a real reading; only null and undefined mean missing.
const has = v => v !== null && v !== undefined && !Number.isNaN(v);
const num = (v, d = 1) => has(v) ? Number(v).toFixed(d) : '—';
const pick = (m, ...keys) => { for (const k of keys) if (m && has(m[k])) return m[k]; return null; };
const clock = d => new Date(d).toLocaleTimeString('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' });
const toneVar = t => ({ good: 'var(--good)', warn: 'var(--warn)', bad: 'var(--bad)' }[t] || 'var(--soft)');
const hourLabel = h => `${h % 12 || 12} ${h < 12 ? 'AM' : 'PM'}`;
const store = {
  get() { try { return JSON.parse(localStorage.getItem(CACHE_KEY) || 'null'); } catch { return null; } },
  set(v) { try { localStorage.setItem(CACHE_KEY, JSON.stringify(v)); } catch {} }
};

// force: the Refresh button asks the server to skip its cache (it still ignores repeats within 15 s)
let forceNext = false;
async function getJSON(url, opts = {}) {
  if (forceNext) opts = { ...opts, headers: { ...(opts.headers || {}), 'X-Force-Refresh': '1' } };
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}

function homeHour() {
  return Number(new Date().toLocaleString('en-US', { timeZone: TZ, hour: 'numeric', hour12: false })) % 24;
}

function rushText(hour) {
  const on = RUSH.find(([s, e]) => hour >= s && hour < e);
  if (on) return `${on[2]} rush until ${hourLabel(on[1])}`;
  const next = RUSH.find(([s]) => s > hour) || RUSH[0];
  return `next rush ${hourLabel(next[0])}${next[0] <= hour ? ' tomorrow' : ''}`;
}

function freshness(m) {
  if (!m || !m.timestamp) return { tone: 'bad', label: 'Offline' };
  const mins = Math.round((Date.now() - new Date(m.timestamp)) / 60000);
  if (mins <= 10) return { tone: 'good', label: 'Online' };
  if (mins <= 60) return { tone: 'warn', label: `Late · ${mins} min` };
  return { tone: 'bad', label: 'Offline' };
}

// Connection status for a row in the Home panel: a dot plus a few words.
const srcOk = { nearby: null, wx: null, pollen: null, smoke: null, bqe: true };
function setStatus(id, tone, text, title) {
  const el = $('st-' + id); if (!el) return;
  el.className = 'pst ' + tone; el.lastElementChild.textContent = text; el.title = title || text;
  if (id in srcOk && id !== 'bqe') srcOk[id] = tone === 'good';
}
function monitorStatus(id, m) {
  const f = freshness(m), mins = m && m.timestamp ? Math.max(0, Math.round((Date.now() - new Date(m.timestamp)) / 60000)) : null;
  const text = f.tone === 'good' ? `Live · ${mins < 1 ? 'just now' : mins + ' min ago'}` : f.label;
  setStatus(id, f.tone, text, m && m.timestamp ? 'Last reading ' + new Date(m.timestamp).toLocaleString('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit', month: 'short', day: 'numeric' }) : 'No reading');
}
function sourceSummary() {
  const known = Object.values(srcOk).filter(v => v !== null);
  return known.length < 5 ? '5 sources' : `${known.filter(Boolean).length === 5 ? '5' : known.filter(Boolean).length + ' of 5'} sources`;
}

function reading(m, indoor) {
  if (!m) return {};
  return {
    pm: pick(m, 'pm02_corrected', 'pm02'),
    co2: pick(m, 'rco2_corrected', 'rco2'),
    t: indoor ? pick(m, 'atmp', 'atmp_corrected') : pick(m, 'atmp_corrected', 'atmp'),
    rh: indoor ? pick(m, 'rhum', 'rhum_corrected') : pick(m, 'rhum_corrected', 'rhum')
  };
}

// ── Monitors ──────────────────────────────────────────

// Aim for each reading. A value past its aim is amber; nothing else is colored.
const AIM = {
  pm:  { text: `< ${PM_FINE}`, over: v => v > PM_FINE },
  co2: { text: `< ${CO2_OPEN}`, over: v => v > CO2_OPEN, indoorOnly: true },
  voc: { text: '~100', over: v => v > 150, indoorOnly: true },
  nox: { text: '~1', over: v => v > 20, indoorOnly: true },
  rh:  { text: '30–60%', over: v => v > 60 || v < 30, indoorOnly: true },
};

// Production's card structure: PM2.5 hero, then CO₂ / temperature / humidity with bars and words,
// then VOC / NOx / Wi-Fi, then the secondary particle readings.
function pmLevel(pm) {
  if (!has(pm)) return { word: 'No reading', tone: 'muted' };
  if (pm <= PM_FINE) return { word: 'Good', tone: 'good' };
  if (pm <= 35.4) return { word: 'Moderate', tone: 'warn' };
  if (pm <= 55.4) return { word: 'Unhealthy for sensitive groups', tone: 'warn' };
  return { word: 'Unhealthy', tone: 'bad' };
}
function co2Level(v) {
  if (!has(v)) return { word: '', tone: 'muted' };
  if (v <= 600) return { word: 'Excellent', tone: 'good' };
  if (v <= CO2_OPEN) return { word: 'Good', tone: 'good' };
  if (v <= 1000) return { word: 'Fair — open a window soon', tone: 'warn' };
  if (v <= 1500) return { word: 'Poor — ventilate', tone: 'warn' };
  return { word: 'Bad — ventilate now', tone: 'bad' };
}
function rhLevel(v, indoor) {
  if (!has(v)) return { word: '', tone: 'muted' };
  if (!indoor) return { word: v > 80 ? 'Damp outside' : 'Outside air', tone: 'muted' };
  if (v > RH_DAMP) return { word: 'Too damp — mold risk', tone: 'warn' };
  if (v < RH_LOW) return { word: 'Too dry', tone: 'warn' };
  if (v > RH_HIGH) return { word: 'A little damp', tone: 'good' };
  return { word: 'Comfortable', tone: 'good' };
}
const TONE = { good: 'var(--good)', warn: 'var(--warn)', bad: 'var(--bad)', muted: 'var(--soft)' };

function pmRing(pm, tone) {
  const r = 34, c = 2 * Math.PI * r, pct = has(pm) ? Math.min(pm / 55, 1) : 0;
  return `<div class="mc-ring"><svg viewBox="0 0 80 80" aria-hidden="true"><circle class="mc-ring-bg" cx="40" cy="40" r="${r}"/>` +
    `<circle class="mc-ring-fill" cx="40" cy="40" r="${r}" stroke="${TONE[tone]}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c - pct * c).toFixed(1)}"/></svg>` +
    `<div><b style="color:${TONE[tone]}">${num(pm)}</b><span>µg/m³</span></div></div>`;
}

function monitorCard(m, indoor) {
  const f = freshness(m), r = reading(m, indoor);
  const pl = pmLevel(r.pm), cl = co2Level(r.co2), hl = rhLevel(r.rh, indoor);
  const voc = m && m.tvocIndex, nox = m && m.noxIndex, wifi = m && m.wifi;
  const bar = (pct, tone) => `<div class="mc-bar"><i style="width:${Math.max(0, Math.min(100, pct)).toFixed(0)}%;background:${TONE[tone]}"></i></div>`;
  const metric = (label, value, unit, color, extra, sub) =>
    `<div class="mc-m"><span>${label}</span><b${color ? ` style="color:${color}"` : ''}>${value}${unit ? `<small>${unit}</small>` : ''}</b>${extra || ''}<em>${sub || ''}</em></div>`;
  const tF = has(r.t) ? num(r.t * 9 / 5 + 32) : '—';
  return `<article class="card mc" style="--tint:${indoor ? 'var(--series-in)' : 'var(--series-out)'}">
    <div class="mc-head">
      <div class="mc-id"><span class="mc-hw" aria-hidden="true">${indoor ? ICONS.one : ICONS.openair}</span><div><div class="mc-kind ${indoor ? 'in' : 'out'}">${indoor ? 'Indoor' : 'Outdoor'}</div><div class="mc-name">${indoor ? 'AirGradient ONE · main room' : 'AirGradient Open Air · street side'}</div></div></div>
      <div class="mc-status ${f.tone}" title="${m && m.timestamp ? 'Last reading ' + clock(m.timestamp) : 'No reading'}"><i class="live ${f.tone}"></i>${f.label}</div>
    </div>
    <div class="mc-hero ${pl.tone}">
      ${pmRing(r.pm, pl.tone)}
      <div><div class="mc-hero-k" style="color:${TONE[pl.tone]}">PM2.5 — ${pl.word}</div>
        <div class="mc-hero-s">Fine particles · aim under ${PM_FINE} µg/m³</div></div>
    </div>
    <div class="mc-grid">
      ${metric('CO₂', has(r.co2) ? Math.round(r.co2).toLocaleString() : '—', 'ppm', cl.tone === 'good' && !indoor ? null : TONE[cl.tone], has(r.co2) ? bar(r.co2 / 2000 * 100, cl.tone) : '', cl.word)}
      ${metric('Temp', tF, '°F', null, '', has(r.t) ? num(r.t) + '°C' : '')}
      ${metric('Humidity', has(r.rh) ? Math.round(r.rh) : '—', '%', indoor && hl.tone === 'warn' ? TONE.warn : null, has(r.rh) ? bar(r.rh, indoor ? (hl.tone === 'warn' ? 'warn' : 'good') : 'muted') : '', hl.word)}
      ${metric('VOC index', has(voc) ? voc : '—', '', has(voc) && voc > 150 && indoor ? TONE.warn : null, '', has(voc) ? (voc <= 100 ? 'Normal' : voc <= 200 ? 'Elevated' : 'High') : '')}
      ${metric('NOx index', has(nox) ? nox : '—', '', null, '', has(nox) ? (nox <= 20 ? 'Clean' : nox <= 100 ? 'Moderate' : 'High') : '')}
      ${metric('Wi‑Fi', has(wifi) ? wifi : '—', 'dBm', null, '', has(wifi) ? (wifi >= -50 ? 'Excellent' : wifi >= -65 ? 'Good' : wifi >= -75 ? 'Fair' : 'Weak') : '')}
    </div>
    <div class="mc-pm">
      <div><span>PM1</span><b>${num(m && m.pm01)}<small>µg/m³</small></b></div>
      <div><span>PM2.5 raw</span><b>${num(m && m.pm02)}<small>µg/m³</small></b></div>
      <div><span>PM10</span><b>${num(pick(m, 'pm10_corrected', 'pm10'))}<small>µg/m³</small></b></div>
      <div><span>0.3 µm count</span><b>${m && has(m.pm003Count) ? Math.round(m.pm003Count) : '—'}<small>/dL</small></b></div>
    </div>
  </article>`;
}

// Monitor status sits on the avatar as a dot; the words are its tooltip.
function updateStatus() {
  setTimeout(renderSources, 0);
  const okN = [freshness(state.indoor), freshness(state.outdoor)].filter(f => f.tone === 'good').length;
  monitorStatus('one', state.indoor); monitorStatus('openair', state.outdoor);
  const status = `${okN === 2 ? '2 monitors live' : okN + ' of 2 monitors live'} · ${sourceSummary()}`;
  $('avatar').dataset.tip = status; $('avatar').setAttribute('aria-label', 'Home · ' + status);
  $('dot-sum').className = 'av-dot ' + (okN === 2 ? 'good' : okN ? 'warn' : 'bad');
  const hw = $('vsum-hw');
  if (hw) hw.innerHTML = [[ICONS.one, state.indoor, 'Indoor · AirGradient ONE'], [ICONS.openair, state.outdoor, 'Outdoor · AirGradient Open Air']]
    .map(([ic, m, name]) => { const f = freshness(m); return `<span class="vhw" data-tip="${name}: ${f.label}">${ic}<i class="${f.tone}"></i></span>`; }).join('');
}

function renderMonitors() {
  $('monitors').innerHTML = monitorCard(state.indoor, true) + monitorCard(state.outdoor, false);
  if (state.read) { renderAgenda(state.read); renderActionVis(state.read); }
  if (typeof SKY !== 'undefined' && SKY) SKY.pm(reading(state.outdoor, false).pm);
  updateStatus();
  const stamps = [state.indoor, state.outdoor].filter(m => m && m.timestamp).map(m => new Date(m.timestamp));
  lastStamp = stamps.length ? Math.max(...stamps) : null;
  loadFailed = false;
  showUpdated();
}

// ── Local conditions ──────────────────────────────────

// Production's content: a headline value, one line on what it is, then labeled details.
function kv(rows) {
  return rows.filter(Boolean).map(([k, v, tone]) => `<div><dt>${k}</dt><dd${tone ? ` class="${tone}"` : ''}>${v}</dd></div>`).join('');
}

// Typical New York pollen seasons (day of year, approximately), so the card can say what's in season and what's next.
// Live levels come from Google; these dates are the usual calendar, not a forecast.
const POLLEN_SEASONS = [
  { name: 'Tree', start: [3, 10], peak: [[4, 1], [5, 10]], end: [5, 31] },
  { name: 'Grass', start: [5, 10], peak: [[6, 1], [6, 30]], end: [7, 31] },
  { name: 'Weed', start: [8, 15], peak: [[8, 25], [9, 20]], end: [10, 20] },
];
function renderPollenSeason(levels) {
  const box = $('pollen-season'); if (!box) return;
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: TZ })), y = now.getFullYear();
  const doy = d => Math.round((d - new Date(y, 0, 1)) / 864e5), at = ([m, dd], yr = y) => new Date(yr, m - 1, dd);
  const today = doy(now), pct = n => (n / 365 * 100).toFixed(2);
  const fmt = d => { const m = d.toLocaleDateString('en-US', { month: 'long' }), n = d.getDate(); return n <= 10 ? `early ${m}` : n <= 20 ? `mid-${m}` : `late ${m}`; };
  const active = POLLEN_SEASONS.filter(p => now >= at(p.start) && now <= at(p.end));
  // the next season to start (this year or next)
  const next = POLLEN_SEASONS.map(p => { const st = at(p.start), s2 = st > now ? st : at(p.start, y + 1); return { ...p, when: s2 }; }).sort((a, b) => a.when - b.when)[0];
  const weeks = Math.round((next.when - now) / 6048e5), months = Math.round((next.when - now) / (30.4 * 864e5));
  const inTime = weeks <= 6 ? `in about ${weeks} week${weeks === 1 ? '' : 's'}` : `in about ${months} months`;
  let line;
  if (active.length) {
    const p = active[0], inPeak = now >= at(p.peak[0]) && now <= at(p.peak[1]);
    line = `<b>Now: ${p.name.toLowerCase()} season</b>${inPeak ? ', at its peak' : now < at(p.peak[0]) ? `, peaks in ${at(p.peak[0]).toLocaleDateString('en-US', { month: 'long' })}` : ', easing off'}, until ${fmt(at(p.end))}. Next: ${next.name.toLowerCase()} from ${fmt(next.when)}.`;
  } else line = `<b>Next: ${next.name.toLowerCase()} pollen</b>, usually from ${fmt(next.when)} (${inTime}).`;
  const M = 'JFMAMJJASOND';
  const lvl = i => ['None', 'Very low', 'Low', 'Moderate', 'High', 'Very high'][i] || '—';
  const level = name => { const t = (levels || []).find(x => x.name === name), i = t ? (t.index || 0) : null; return i == null ? '—' : `<b class="${i >= 3 ? 'warn' : i ? 'good' : ''}">${lvl(i)}</b>`; };
  box.innerHTML = `<div class="ps-grid" title="Bars: the usual New York season, peak in amber. Right: today's level from Google.">${POLLEN_SEASONS.map(p => `<div class="ps-row"><span>${p.name}</span><div class="ps-track">
      <i class="ps-season" style="left:${pct(doy(at(p.start)))}%;width:${pct(doy(at(p.end)) - doy(at(p.start)))}%"></i>
      <i class="ps-peak" style="left:${pct(doy(at(p.peak[0])))}%;width:${pct(doy(at(p.peak[1])) - doy(at(p.peak[0])))}%"></i></div>${level(p.name)}</div>`).join('')}
      <div class="ps-row ps-months"><span></span><div class="ps-track">${[0, 3, 6, 9].map(i => `<em style="left:${pct(doy(new Date(y, i, 1)))}%">${new Date(y, i, 1).toLocaleDateString('en-US', { month: 'short' })}</em>`).join('')}</div><span></span></div>
      <div class="ps-today" style="--x:${pct(today)}" title="Today"></div></div>
    <p class="ps-line">${line}</p>`;
}

function setEdges() {
  for (const id of ['wx-hero', 'pollen-hero', 'bqe-hero', 'smoke-hero']) {
    const el = $(id), card = el && el.closest('.card');
    if (!card) continue;
    const c = el.style.getPropertyValue('--c');
    card.style.setProperty('--edge', c || 'var(--sky)');
    card.classList.toggle('has-status', !!c);
  }
}

function contextStatus(ctx) {
  const w = (ctx && ctx.weather) || {}, pollen = (ctx && ctx.pollen) || [], sm = (ctx && ctx.smoke) || {};
  setStatus('wx', has(w.temperature) ? 'good' : 'bad', has(w.temperature) ? 'Live' : 'No data', has(w.temperature) ? 'Current weather from Open-Meteo' : 'Open-Meteo did not answer');
  // Google returns every pollen type even out of season, so an empty list means no answer.
  setStatus('pollen', pollen.length ? 'good' : 'bad', pollen.length ? 'Today' : 'No data', pollen.length ? "Today's pollen from Google" : 'Google Pollen did not answer');
  setStatus('smoke', sm.checked ? 'good' : 'bad', sm.checked ? `${sm.date ? new Date(sm.date + 'T12:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Today'} map` : 'Not checked', sm.checked ? `NOAA smoke map${sm.date ? ' for ' + sm.date : ''}` : 'The NOAA smoke map did not load');
  setStatus('bqe', 'neutral', 'Estimated', 'Calculated from the hour and the wind; nothing to connect');
  updateStatus();
}

function renderContext(ctx) {
  const w = ctx.weather || {}, b = ctx.bqe || {}, pollen = ctx.pollen || [];
  window.__wx = w; window.__bqe = b; if (state.read) renderAgenda(state.read);
  if (state.neighbors && state.neighbors.length) renderNeighborhood();
  if (typeof SKY !== 'undefined' && SKY) SKY.weather(w);
  if (has(w.wind_speed)) {
    $('wx-hero').textContent = `${w.wind_cardinal} ${num(w.wind_speed)} km/h`;
    $('wx-sub').textContent = 'Wind direction and speed';
    const risk = String(w.dew_point_risk || '');
    const uv = has(w.uv_index) ? Math.round(w.uv_index) : null;
    $('wx-kv').innerHTML = kv([
      has(w.temperature) && ['Temperature', `${Math.round(w.temperature * 9 / 5 + 32)}°F · ${num(w.temperature)}°C`],
      has(w.dew_point) && ['Dew point', `${num(w.dew_point)}°C · ${w.dew_point >= 16 ? 'humid' : w.dew_point >= 10 ? 'comfortable' : w.dew_point >= 5 ? 'dry' : 'very dry'}`, w.dew_point < 10 ? 'warn' : ''],
      has(w.dew_point) && ['Sinus dryness', w.dew_point < 5 ? 'High' : w.dew_point < 10 ? 'Some' : 'None', w.dew_point < 10 ? 'warn' : ''],
      has(w.visibility) && ['Visibility', `${num(w.visibility / 1000)} km`],
      uv != null && ['UV index', `${uv} · ${uv <= 2 ? 'Low' : uv <= 5 ? 'Moderate' : uv <= 7 ? 'High' : 'Very high'}`, uv <= 2 ? 'good' : 'warn'],
    ]);
  } else {
    $('wx-hero').textContent = 'No reading';
    $('wx-sub').textContent = 'Open-Meteo did not answer.';
    $('wx-kv').innerHTML = '';
  }

  if (pollen.length) {
    const top = Math.max(...pollen.map(p => p.index || 0));
    const word = top === 0 ? 'None' : top <= 2 ? 'Low' : top === 3 ? 'Moderate' : 'High';
    $('pollen-hero').textContent = word;
    $('pollen-hero').style.setProperty('--c', top >= 3 ? 'var(--warn)' : 'var(--good)');
    const offSeason = pollen.every(p => !p.in_season);
    $('pollen-sub').textContent = (top === 0 ? 'Nothing in the air today' : top <= 2 ? 'All allergens low' : 'Expect congestion outdoors') + (offSeason ? ' · all out of season' : '');
    // one row per type: its season across the year (with today), and today's level from Google
    $('pollen-kv').innerHTML = '';
    renderPollenSeason(pollen);
  } else {
    $('pollen-hero').textContent = 'No data';
    $('pollen-hero').style.setProperty('--c', 'var(--soft)');
    $('pollen-sub').textContent = 'Google Pollen did not answer.';
    $('pollen-kv').innerHTML = '';
  }

  const hour = has(b.current_hour) ? b.current_hour : homeHour();
  const t = String(b.traffic || '');
  const peak = t.startsWith('PEAK'), high = t.startsWith('HIGH');
  $('bqe-hero').textContent = peak ? 'Peak' : high ? 'High' : 'Low';
  $('bqe-hero').style.setProperty('--c', peak || high ? 'var(--warn)' : 'var(--good)');
  $('bqe-sub').textContent = peak ? (t.includes('morning') ? 'Morning rush' : 'Evening rush') : high ? 'Rush shoulders' : 'Off-peak traffic';
  const pressure = b.pollution_pressure;
  $('bqe-kv').innerHTML = kv([
    has(pressure) && ['Pollution pressure', `${num(pressure)}×`, pressure > 1 ? 'warn' : 'good'],
    b.wind_impact && ['Wind', esc(b.wind_impact), b.wind_impact === 'Blowing toward Greenpoint' ? 'warn' : ''],
    ['Morning rush', '7–10 AM'],
    ['Evening rush', '4–8 PM'],
  ]);
  $('bqe-now').textContent = `Pressure is those two multiplied. Now, ${peak ? 'peak' : high ? 'high' : 'low'} traffic times ${has(w.wind_direction) ? 'a ' + w.wind_cardinal + ' wind' : 'an unknown wind'} is ${num(pressure)}.`;

  const sm = ctx.smoke || {};
  const mapped = sm.date ? new Date(sm.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : null;
  if (!sm.checked) {
    $('smoke-hero').textContent = 'Not checked';
    $('smoke-hero').style.setProperty('--c', 'var(--soft)');
    $('smoke-sub').textContent = 'NOAA\u2019s smoke map did not load';
  } else {
    $('smoke-hero').textContent = sm.detected ? `${sm.density} smoke` : 'Not detected';
    $('smoke-hero').style.setProperty('--c', sm.detected ? (sm.density === 'Light' ? 'var(--warn)' : 'var(--bad)') : 'var(--good)');
    $('smoke-sub').textContent = sm.detected ? 'Satellites mapped wildfire smoke over Greenpoint' : 'No wildfire smoke mapped over Greenpoint';
  }
  $('smoke-kv').innerHTML = kv([mapped && ['Map date', mapped], ['Source', 'NOAA satellite smoke map']]);
  setEdges();
}

// ── Neighborhood ──────────────────────────────────────

function barColor(v) {
  if (v > 35) return 'var(--bad)';
  if (v > PM_FINE) return 'var(--warn-fill)';
  const k = Math.min(v / PM_FINE, 1);               // light to deep green across the fine range
  return `color-mix(in srgb, var(--bar-hi) ${Math.round(k * 100)}%, var(--bar-lo))`;
}

// Neighborhood table rows highlight their dot on the map, and the other way around
document.addEventListener('mouseover', e => { const tr = e.target.closest && e.target.closest('#nb tr[data-id]'); if (tr && typeof NBMAP !== 'undefined') NBMAP.highlight(Number(tr.dataset.id)); });
document.addEventListener('mouseout', e => { const tr = e.target.closest && e.target.closest('#nb tr[data-id]'); if (tr && !tr.contains(e.relatedTarget) && typeof NBMAP !== 'undefined') NBMAP.highlight(null); });
$('nb-more') && $('nb-more').addEventListener('click', () => { state.nbAll = !state.nbAll; renderNeighborhood(); });

function growBars() {
  const table = document.querySelector('.nbt'); if (!table || reduceMotion.matches) return;
  const bars = [...table.querySelectorAll('.nbbar i')];
  bars.forEach(b => { b.style.transform = 'scaleX(0)'; });
  onVisible(table, () => bars.forEach((b, i) => { b.style.transform = '';
    b.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 800, delay: i * 35, easing: 'cubic-bezier(.2, .7, .2, 1)', fill: 'backwards' }); }));
}

function renderNeighborhood() {
  const own = new Set([state.indoor, state.outdoor].filter(Boolean).map(m => m.locationId));
  const live = state.neighbors.filter(n => !n.offline && has(n.pm02) && (!n.timestamp || Date.now() - new Date(n.timestamp) < 2 * 3600e3));
  const you = live.find(n => own.has(n.locationId));
  const others = live.filter(n => !own.has(n.locationId));
  const rows = (you ? [you] : []).concat(others);
  setStatus('nearby', others.length ? 'good' : 'bad', others.length ? `${others.length} reporting` : 'No answer', others.length ? `${others.length} nearby monitors sent a reading in the last 2 hours` : 'Nearby monitors did not answer');
  if (!rows.length) {
    $('nb-lead').textContent = 'Nearby monitors did not answer.';
    $('nb').innerHTML = '';
    return;
  }
  const peakRow = others.reduce((a, n) => (!a || n.pm02 > a.pm02 ? n : a), null);
  const scale = Math.max(peakRow ? peakRow.pm02 : 0, you ? you.pm02 : 0, PM_FINE);
  // Speak only when the comparison changes a decision; otherwise stay silent.
  const vals = others.map(n => n.pm02).sort((x, y) => x - y);
  const median = vals.length ? vals[Math.floor(vals.length / 2)] : null;
  const over = others.filter(n => n.pm02 > PM_FINE).sort((x, y) => x.distance_km - y.distance_km);
  let lead = '';
  if (has(median) && median > PM_FINE) {
    lead = `<b class="warn">The whole area is elevated</b> (typical nearby reading ${num(median)} µg/m³). That points to something regional, such as wildfire smoke, not a source near home.`;
  } else if (you && has(median) && you.pm02 > PM_FINE && you.pm02 > median * 2) {
    lead = `<b class="warn">Your block reads well above the area</b> (${num(you.pm02)} against a typical ${num(median)}). That points to a source close to home: traffic, construction, or a neighbor's smoke.`;
  } else if (over.length) {
    const n0 = over[0];
    lead = `<b class="warn">${over.length === 1 ? 'One nearby monitor is' : over.length + ' nearby monitors are'} over the ${PM_FINE} µg/m³ limit</b>: the nearest is ${esc(n0.locationName)}, ${num(n0.distance_km)} km away.${you && you.pm02 <= PM_FINE ? ' Your block is still clean.' : ''}`;
  }
  $('nb-lead').innerHTML = lead;
  $('nb-lead').hidden = !lead;
  $('nb-sub').textContent = `${others.length} public AirGradient monitors within 15 km · PM2.5 µg/m³`;
  const barMax = Math.max(55, Math.ceil(Math.max(...rows.map(n => n.pm02))));
  const limPct = (PM_FINE / barMax * 100).toFixed(1);
  $('nb-max').textContent = barMax; $('nb-limpos').style.left = limPct + '%';
  $('nb').innerHTML = rows.map(n => {
    const isYou = n === you, tone = n.pm02 > PM_FINE ? 'warn' : 'good';
    const tF = has(n.atmp) ? Math.round(n.atmp * 9 / 5 + 32) + '°F' : '—';
    return `<tr class="${isYou ? 'you' : ''}" data-id="${n.locationId}"><td class="dot"><i></i></td><td class="dist">${isYou ? 'You' : num(n.distance_km) + ' km'}</td>` +
      `<td class="loc" title="${esc(n.locationName)}">${esc(isYou ? 'Greenpoint' : n.locationName)}</td>` +
      `<td class="r pm ${tone}">${num(n.pm02)}</td><td class="r">${tF}</td><td class="r">${has(n.rhum) ? Math.round(n.rhum) + '%' : '—'}</td>` +
      `<td class="nbbar"><span style="--lim:${limPct}%"><i style="width:${Math.max(1.5, n.pm02 / barMax * 100).toFixed(1)}%" class="${tone}"></i></span></td></tr>`;
  }).join('');
  if (!growBars.done) { growBars.done = true; growBars(); }   // once, when the table first fills
  // the table shows the nearest 8 under the map; "Show all" opens the rest
  const more = $('nb-more'), extra = rows.length - 8;
  document.querySelector('.nb-card').classList.toggle('nb-all', !!state.nbAll);
  more.hidden = extra <= 0;
  more.innerHTML = state.nbAll ? 'Show the nearest 8 <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m18 15-6-6-6 6"/></svg>'
    : `Show ${extra} more monitor${extra === 1 ? '' : 's'} <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>`;
  more.setAttribute('aria-expanded', String(!!state.nbAll));
  [...$('nb').rows].forEach((tr, i) => { tr.classList.toggle('nb-extra', i >= 8); });
  // the map: same monitors, the BQE, and where the wind takes its exhaust
  const w = window.__wx || {}, b = window.__bqe || {};
  // what the map means for the block: the BQE runs about 1 km east to south, so east, south-east and south winds bring its exhaust here
  const imp = b.wind_impact;
  $('nb-wind').innerHTML = has(w.wind_direction) ? `<b>Wind ${esc(w.wind_cardinal || '')} ${num(w.wind_speed)} km/h:</b> ` + (
    imp === 'Blowing toward Greenpoint' ? '<b class="warn">the BQE\'s traffic exhaust drifts toward your block.</b> Worst in the rush hours; keep windows shut then.'
    : imp === 'Blowing away' ? 'the BQE\'s traffic exhaust drifts away from your block.'
    : 'the BQE\'s traffic exhaust passes beside your block, not over it.') +
    ' <span class="nb-why">The expressway runs about 1 km east to south of here, so it matters on east, south-east and south winds.</span>' : '';
  if (typeof NBMAP !== 'undefined') NBMAP.update(you, others, has(w.wind_direction) ? w.wind_direction : null);
}

// ── Charts ────────────────────────────────────────────

function bucket(rows, from, to, n, key) {
  const sums = new Array(n).fill(0), counts = new Array(n).fill(0);
  const span = to - from;
  for (const row of rows || []) {
    const v = key(row);
    if (!has(v)) continue;
    const i = Math.min(n - 1, Math.floor((new Date(row.timestamp) - from) / span * n));
    if (i < 0) continue;
    sums[i] += v; counts[i]++;
  }
  return sums.map((s, i) => counts[i] ? s / counts[i] : null);
}

function niceTicks(lo, hi) {
  const raw = (hi - lo) / 3, mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(k => k >= raw) || raw;
  const out = []; for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(6));
  return out;
}

// Smooth path through points (monotone cubic, no overshoot below zero).
function smooth(pts) {
  if (pts.length < 2) return pts.length ? `M${pts[0][0]},${pts[0][1]}` : '';
  const n = pts.length, dx = [], m = [], t = [];
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; m[i] = (pts[i + 1][1] - pts[i][1]) / dx[i]; }
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : 3 * (dx[i - 1] + dx[i]) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]);
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += `C${(pts[i][0] + h).toFixed(1)},${(pts[i][1] + h * t[i]).toFixed(1)} ${(pts[i + 1][0] - h).toFixed(1)},${(pts[i + 1][1] - h * t[i + 1]).toFixed(1)} ${pts[i + 1][0].toFixed(1)},${pts[i + 1][1].toFixed(1)}`;
  }
  return d;
}

function draw(id, a, b, times, range, spec) {
  const svg = $(id);
  let last = a.length - 1; while (last > 0 && !has(a[last]) && !has(b[last])) last--;
  a = a.slice(0, last + 1); b = b.slice(0, last + 1); times = times.slice(0, last + 1);
  const W = 560, H = 210, L = 42, R = 58, T = 30, B = 24;   // R: room for the limit's label
  const iw = W - L - R, ih = H - T - B;
  const values = [...a, ...b].filter(has);
  if (!values.length) { svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">No readings in this range</text>`; return; }
  let lo = Math.min(...values), hi = Math.max(...values);
  const limitNear = spec.limit <= hi * 1.35 && spec.limit >= lo;
  if (limitNear) hi = Math.max(hi, spec.limit);
  const pad = Math.max((hi - lo) * 0.1, spec.minSpan / 2);
  lo = Math.max(spec.floor, lo - pad); hi = hi + pad;
  const x = i => L + (a.length < 2 ? iw / 2 : i / (a.length - 1) * iw);
  const y = v => T + (1 - (v - lo) / (hi - lo)) * ih;
  const runs = ys => {           // continuous stretches of readings
    const out = []; let cur = [];
    ys.forEach((v, i) => { if (has(v)) cur.push([x(i), y(v)]); else if (cur.length) { out.push(cur); cur = []; } });
    if (cur.length) out.push(cur); return out;
  };
  const clip = id + '-over';
  // the part of a line over the limit is drawn again in amber, so entering the bad zone is visible
  const series = (ys, cls) => runs(ys).map(r => {
    const d = smooth(r);
    // area, then the over-the-limit shading (between the line and the limit, in amber), then the line in its own color on top
    return `<path d="${d}L${r[r.length - 1][0].toFixed(1)},${T + ih}L${r[0][0].toFixed(1)},${T + ih}Z" class="ts-area ${cls}"/>` +
      (limitNear ? `<path d="${d}L${r[r.length - 1][0].toFixed(1)},${y(spec.limit).toFixed(1)}L${r[0][0].toFixed(1)},${y(spec.limit).toFixed(1)}Z" class="ts-overfill" clip-path="url(#${clip})"/>` : '') +
      `<path d="${d}" class="ts-line ${cls}"/>`;
  }).join('');
  let g = limitNear ? `<defs><clipPath id="${clip}"><rect x="0" y="0" width="${W}" height="${y(spec.limit)}"/></clipPath></defs>` : '';
  niceTicks(lo, hi).forEach(t => {
    const yy = y(t).toFixed(1);
    g += `<line x1="${L}" y1="${yy}" x2="${L + iw}" y2="${yy}" class="ts-grid"/><text x="${L - 8}" y="${Number(yy) + 3.5}" text-anchor="end">${t.toLocaleString()}</text>`;
  });
  g += series(b, 'ts-out') + series(a, 'ts-in');
  if (limitNear) {
    const yy = y(spec.limit).toFixed(1);
    g += `<line x1="${L}" y1="${yy}" x2="${L + iw}" y2="${yy}" class="ts-guide"/>` +
      `<text class="ts-limword" x="${L + iw + 8}" y="${Number(yy) - 4}">${spec.word} ↑</text><text class="ts-limnum" x="${L + iw + 8}" y="${Number(yy) + 10}">${spec.limit.toLocaleString()}</text>`;
  }
  // legend, top right
  const over = limitNear && values.some(v => v > spec.limit), lx = over ? -112 : 0;
  g += `<g class="ts-legend" transform="translate(${L + iw + R - 4},12)"><rect x="${-150 + lx}" y="-5" width="14" height="4" rx="2" class="ts-sw ts-in"/><text x="${-131 + lx}" y="0">Indoor</text>` +
       `<rect x="${-76 + lx}" y="-5" width="14" height="4" rx="2" class="ts-sw ts-out"/><text x="${-57 + lx}" y="0">Outdoor</text>` +
       (over ? `<rect x="-100" y="-7" width="14" height="9" rx="2" class="ts-sw-over"/><text x="-81" y="0">Over the limit</text>` : '') + `</g>`;
  if (!limitNear) g += `<text class="ts-under" x="${L}" y="12">All under the limit of ${spec.limit.toLocaleString()}</text>`;
  // short axis labels that never collide: minutes for 1 h and 6 h, hours for 24 h, weekdays for 7 d
  const opt = range === '1h' || range === '6h' ? { timeZone: TZ, hour: 'numeric', minute: '2-digit' } : range === '24h' ? { timeZone: TZ, hour: 'numeric' } : { timeZone: TZ, weekday: 'short' };
  const ticks = 5;
  // evenly spaced along the axis (not by sample index, which bunches the last labels together)
  const t0 = +times[0], t1 = +times[times.length - 1];
  for (let k = 0; k <= ticks; k++) {
    const f = k / ticks;
    g += `<text x="${(L + f * iw).toFixed(1)}" y="${H - 6}" text-anchor="${k === 0 ? 'start' : k === ticks ? 'end' : 'middle'}">${new Date(t0 + f * (t1 - t0)).toLocaleString('en-US', opt)}</text>`;
  }
  g += `<g class="ts-hover" style="display:none"><line class="ts-xh" y1="${T}" y2="${T + ih}"/><circle class="ts-hd in" r="4"/><circle class="ts-hd out" r="4"/></g>`;
  svg.innerHTML = g;
  $(spec.noteId).textContent = RANGE_LABEL[range];
  svg.__hover = { kind: 'big', L, iw, x, y, a, b, times: times.map(Number), note: $(spec.noteId), label: RANGE_LABEL[range], spec };
  if (!reduceMotion.matches && svg.dataset.drawn !== range) {   // lines draw in when the range changes, once the chart is on screen
    svg.dataset.drawn = range;
    const lines = [...svg.querySelectorAll('.ts-line')], areas = [...svg.querySelectorAll('.ts-area')];
    lines.forEach(p => { const len = p.getTotalLength(); p.style.strokeDasharray = len; p.style.strokeDashoffset = len; });
    areas.forEach(p => { p.style.opacity = 0; });
    onVisible(svg, () => {
      lines.forEach(p => { const len = p.getTotalLength();
        p.animate([{ strokeDashoffset: `${len}` }, { strokeDashoffset: '0' }], { duration: 1400, easing: 'cubic-bezier(.65, 0, .35, 1)' })
          .finished.then(() => { p.style.strokeDasharray = ''; p.style.strokeDashoffset = ''; }, () => {}); p.style.strokeDashoffset = 0; });
      areas.forEach(p => { p.style.opacity = ''; const to = getComputedStyle(p).opacity;   // fade to the area's own light tint, not to solid
        p.animate([{ opacity: 0 }, { opacity: to }], { duration: 900, delay: 500, easing: 'ease-out', fill: 'backwards' }); });
    });
  }
  linkHover(svg);
}

// History is fetched once for 7 days, in the background; every shorter range is cut from it, so switching is instant.
// Until the week is in (or after it's 5 minutes old), the picked range is fetched on its own, with a loading state.
const hist = { week: null, at: 0, pending: null };
const fetchHist = (from, to) => Promise.all([state.indoor, state.outdoor].map(m =>
  m ? getJSON(`/api/history/${m.locationId}?from=${from.toISOString()}&to=${to.toISOString()}`).catch(() => null) : Promise.resolve([])));
function loadWeek() {   // once per visit, then at most every 30 minutes
  if (hist.pending) return hist.pending;
  if (hist.week && Date.now() - hist.at < 30 * 60e3) return Promise.resolve(hist.week);
  const to = new Date(), from = new Date(to - 168 * 3600e3);
  hist.pending = fetchHist(from, to).then(([ih, oh]) => { if (!ih || !oh) throw new Error('history'); hist.week = { ih, oh, to }; hist.at = Date.now(); return hist.week; }).finally(() => { hist.pending = null; });
  return hist.pending;
}
function chartsLoading(on) {
  document.querySelector('.chart-bar').classList.toggle('loading', on);
  document.querySelectorAll('#chart-pm, #chart-co2').forEach(svg => svg.closest('.card').classList.toggle('loading', on));
}

async function loadCharts({ fresh = false, quiet = false } = {}) {
  const range = state.range;
  document.querySelectorAll('#ranges button').forEach(btn => {
    const on = btn.dataset.range === range;
    btn.classList.toggle('on', on); btn.setAttribute('aria-checked', String(on));
  });
  // A range switch cuts from the saved week (instant); a refresh fetches only the range on screen.
  const week = !fresh && hist.week ? hist.week : null;
  const to = week ? week.to : new Date(), from = new Date(to - RANGE_HOURS[range] * 3600e3);
  let ih, oh;
  if (week) {
    const inRange = rows => (rows || []).filter(r => new Date(r.timestamp) >= from);
    ih = inRange(week.ih); oh = inRange(week.oh);
    if (Date.now() - hist.at > 5 * 60e3) setTimeout(() => { if (state.range === range) loadCharts({ fresh: true, quiet: true }); }, 0);   // then catch up on the newest readings
  } else {
    if (!quiet) chartsLoading(true);
    try { [ih, oh] = await fetchHist(from, to); } finally { if (range === state.range) chartsLoading(false); }
    loadWeek().catch(() => {});                     // the week for instant switching, once per visit
  }
  if (range !== state.range) return;                // a newer range was picked meanwhile
  if (!ih || !oh) {                                 // a fetch failed: keep what's drawn rather than blanking it
    if ($('chart-co2').childElementCount) return;
    ih = ih || []; oh = oh || [];
  }
  const n = Math.min(96, Math.max(ih.length, oh.length, 2));
  const times = Array.from({ length: n }, (_, i) => new Date(+from + (i + 0.5) * (to - from) / n));
  const pm = row => pick(row, 'pm02_corrected', 'pm02');
  const co2 = row => pick(row, 'rco2_corrected', 'rco2');
  draw('chart-pm', bucket(ih, from, to, n, pm), bucket(oh, from, to, n, pm), times, range,
    { limit: PM_FINE, word: 'polluted', floor: 0, minSpan: 2, unit: 'µg/m³', noteId: 'pm-note', fmt: v => num(v) });
  draw('chart-co2', bucket(ih, from, to, n, co2), bucket(oh, from, to, n, co2), times, range,
    { limit: CO2_OPEN, word: 'stale', floor: 0, minSpan: 100, unit: 'ppm', noteId: 'co2-note', fmt: v => Math.round(v).toLocaleString() });
}

// Run fn once when el is at least a third on screen (right away if it already is).
function onVisible(el, fn) {
  if (!el) return;
  if (!('IntersectionObserver' in window)) return fn();
  const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); fn(); } }, { threshold: .33 });
  io.observe(el);
}

// ── Linked hover: one moment, marked on every chart that covers it ──
const hoverCharts = new Set();
const atLabel = t => { const day = x => new Date(x).toLocaleDateString('en-US', { timeZone: TZ }), d = new Date(t);
  const pre = day(t) === day(Date.now()) ? '' : day(t) === day(Date.now() - 864e5) ? 'Yesterday ' : d.toLocaleDateString('en-US', { timeZone: TZ, weekday: 'short' }) + ' ';
  return pre + d.toLocaleTimeString('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' }); };
function linkHover(el) {
  hoverCharts.add(el);
  if (el.__wired) return; el.__wired = true;
  const at = e => { const h = el.__hover; if (!h) return null;
    const r = (h.kind === 'big' ? el : el.querySelector('svg')).getBoundingClientRect();
    if (h.kind === 'big') { const xs = (e.clientX - r.left) / r.width * 560, f = Math.min(1, Math.max(0, (xs - h.L) / h.iw)); return h.times[0] + f * (h.times[h.times.length - 1] - h.times[0]); }
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); return h.t0 + f * (h.t1 - h.t0); };
  // mouse: hover shows the moment, leaving hides it. Touch: a tap shows it and it stays; dragging sideways scrubs;
  // tapping anywhere else hides it (see the document listener below).
  el.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') broadcastHover(at(e)); });
  el.addEventListener('pointermove', e => { if (e.pointerType === 'mouse' || e.buttons || e.pressure) broadcastHover(at(e)); });
  el.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') broadcastHover(null); });
}
document.addEventListener('pointerdown', e => {
  if (e.pointerType !== 'mouse' && ![...hoverCharts].some(el => el.contains(e.target))) broadcastHover(null);
});
function broadcastHover(t) {
  for (const el of hoverCharts) {
    if (!el.isConnected) { hoverCharts.delete(el); continue; }
    const h = el.__hover; if (!h) continue;
    if (h.kind === 'big') {
      const g = el.querySelector('.ts-hover'), n = h.times.length;
      const inRange = t != null && t >= h.times[0] - 1 && t <= h.times[n - 1] + 1;
      if (!inRange) { g.style.display = 'none'; h.note.textContent = h.label; continue; }
      const i = Math.round((t - h.times[0]) / (h.times[n - 1] - h.times[0]) * (n - 1)), xx = h.x(i).toFixed(1);
      g.style.display = ''; g.querySelector('.ts-xh').setAttribute('x1', xx); g.querySelector('.ts-xh').setAttribute('x2', xx);
      for (const [cls, arr] of [['in', h.a], ['out', h.b]]) { const c = g.querySelector('.ts-hd.' + cls); if (has(arr[i])) { c.style.display = ''; c.setAttribute('cx', xx); c.setAttribute('cy', h.y(arr[i]).toFixed(1)); } else c.style.display = 'none'; }
      const f = v => has(v) ? h.spec.fmt(v) : '—';
      h.note.textContent = `${atLabel(h.times[i])} · Indoor ${f(h.a[i])} · Outdoor ${f(h.b[i])} ${h.spec.unit}`;
    } else {
      const inRange = t != null && t >= h.t0 && t <= h.t1;
      if (!inRange) { h.mark.style.display = 'none'; h.readout.textContent = h.label; continue; }
      const n = h.series.length, i = Math.min(n - 1, Math.max(0, Math.floor((t - h.t0) / (h.t1 - h.t0) * n))), v = h.series[i];
      const f = (i + .5) / n;
      h.mark.style.display = ''; h.mark.style.left = `calc((100% - var(--gut, 52px)) * ${f.toFixed(4)})`;
      const dot = h.mark.querySelector('i');
      if (has(v)) { dot.style.display = ''; dot.style.top = `${((1 - (v - h.lo) / (h.hi - h.lo)) * 100).toFixed(1)}%`; } else dot.style.display = 'none';
      const val = !has(v) ? 'no reading' : h.metric === 'pm' ? `${Number(v).toFixed(1)} ${h.unit}` : `${Math.round(v).toLocaleString()} ${h.unit}`;
      h.readout.textContent = `${atLabel(h.t0 + f * (h.t1 - h.t0))} · ${val}`;
    }
  }
}
// After the summary cards render: give each 24-hour chart its time scale and a crosshair.
function wireSparks() {
  document.querySelectorAll('#s-cards .n-card').forEach(card => {
    const sp = card.querySelector('.s-spark'); if (!sp) return;
    const t1 = Number(card.dataset.t1), readout = card.querySelector('.n-metric');
    sp.insertAdjacentHTML('beforeend', '<span class="s-xh" style="display:none"><i></i></span>');
    sp.__hover = { kind: 'spark', t0: t1 - 24 * 3600e3, t1, series: JSON.parse(sp.dataset.series), lo: Number(sp.dataset.lo), hi: Number(sp.dataset.hi),
      mark: sp.querySelector('.s-xh'), readout, label: readout.textContent, unit: card.dataset.unit, metric: card.dataset.metric };
    linkHover(sp);
  });
}

// ── The summary ──────────────────────────────────────────

function readPayload() {
  const i = reading(state.indoor, true), o = reading(state.outdoor, false);
  return {
    format: 'read',
    indoor_pm25: i.pm, indoor_co2: i.co2, indoor_humidity: i.rh, indoor_temp_c: i.t,
    outdoor_pm25: o.pm, outdoor_humidity: o.rh, outdoor_temp_c: o.t,
    indoor_location_id: state.indoor ? state.indoor.locationId : null,
    outdoor_location_id: state.outdoor ? state.outdoor.locationId : null
  };
}

function readKey(p) {
  const r = (v, s) => has(v) ? Math.round(v / s) : 'x';
  return [r(p.indoor_co2, 50), r(p.indoor_humidity, 3), r(p.outdoor_pm25, 1), homeHour()].join('|');
}

function splitFirst(text) {
  const m = String(text || '').match(/^(.+?[.!?])(\s[\s\S]*)?$/);
  return m ? [m[1], m[2] || ''] : [String(text || ''), ''];
}

function ftag(filter) {
  return filter && ICONS[filter] ? `<span class="ftags" title="${FILTER_NAME[filter]}">${ICONS[filter]}</span>` : '';
}

function setCheck(id, v, text) {
  const card = $(id);
  card.style.setProperty('--c', toneVar(v.tone));
  card.querySelector('.n').textContent = v.word;
  card.querySelector('.s').textContent = text;
}

// why: 'offline' or 'failed' when this is an earlier summary shown in place of a new one.
// Sparkline: gray line, colored only where it is over the limit; the limit is labeled at the end of its line.
let sparkN = 0;
// zone: words for the side above the limit (e.g. "Stale"), drawn as a faint tinted band so it's clear which side is bad.
// Chart: the line, its limit line, and in the right gutter the limit's number with one word for the bad side ("stale ↑").
// limit null: no upper limit (a dry-only humidity chart). low: { limit, word } for a second bad side below.
function sparkline(series, limit, tone, cross, word, low) {
  const pts = series.map((v, i) => [i, v]).filter(p => has(p[1]));
  if (pts.length < 2) return '';
  const top = limit != null, W = 260, H = 56, vals = [...pts.map(p => p[1]), ...(top ? [limit] : []), ...(low ? [low.limit] : [])];
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * .2 || 1; lo -= pad; hi += pad;
  const n = series.length - 1, x = i => i / n * W, y = v => H - (v - lo) / (hi - lo) * H;
  const d = pts.map((p, k) => (k && has(series[p[0] - 1]) ? 'L' : 'M') + x(p[0]).toFixed(1) + ',' + y(p[1]).toFixed(1)).join('');
  const id = 'sp-' + String(limit) + '-' + (word || ''), col = { warn: 'var(--warn-fill)', bad: 'var(--bad)' }[tone] || 'var(--soft)';
  const pct = v => (y(v) / H * 100).toFixed(1);
  const lim = v => `<line class="s-lim" x1="0" x2="${W}" y1="${y(v)}" y2="${y(v)}" vector-effect="non-scaling-stroke"/>`;
  // soft fill under the line: gray, and amber where the line is past a limit
  const x0 = x(pts[0][0]).toFixed(1), x1 = x(pts[pts.length - 1][0]).toFixed(1), area = `${d}L${x1},${H}L${x0},${H}Z`;
  return `<div class="s-spark" data-lo="${lo}" data-hi="${hi}" data-series="${esc(JSON.stringify(series))}"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><defs>
    <linearGradient id="${id}g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" class="s-fill-a"/><stop offset="1" class="s-fill-b"/></linearGradient>
    <linearGradient id="${id}w" x1="0" x2="0" y1="0" y2="1"><stop offset="0" class="s-warn-a"/><stop offset="1" class="s-warn-b"/></linearGradient>
    ${top ? `<clipPath id="${id}"><rect x="0" y="-10" width="${W}" height="${y(limit) + 10}"/></clipPath>` : ''}
    ${low ? `<clipPath id="${id}l"><rect x="0" y="${y(low.limit)}" width="${W}" height="${H - y(low.limit) + 10}"/></clipPath>` : ''}</defs>
    <path d="${area}" fill="url(#${id}g)"/>
    ${top && tone !== 'good' ? `<path d="${d}L${x1},${y(limit)}L${x0},${y(limit)}Z" fill="url(#${id}w)" clip-path="url(#${id})"/>` : ''}
    ${top ? lim(limit) : ''}${low ? lim(low.limit) : ''}
    <path class="s-base" d="${d}" vector-effect="non-scaling-stroke"/>
    ${top ? `<path class="s-hot" d="${d}" stroke="${col}" clip-path="url(#${id})" vector-effect="non-scaling-stroke"/>` : ''}
    ${low ? `<path class="s-hot" d="${d}" stroke="${col}" clip-path="url(#${id}l)" vector-effect="non-scaling-stroke"/>` : ''}</svg>
    ${top ? `<span class="s-lab up" style="top:${pct(limit)}%">${word ? `<em>${esc(word)} ↑</em> ` : ''}<b>${limit.toLocaleString()}</b></span>` : ''}
    ${low ? `<span class="s-lab down" style="top:${pct(low.limit)}%"><b>${low.limit}</b> <em>${esc(low.word)} ↓</em></span>` : ''}
    <span class="s-span">24 h</span>${(() => { const lp = pts[pts.length - 1]; return `<span class="s-end" style="left:calc((100% - var(--gut, 52px)) * ${(x(lp[0]) / W).toFixed(4)});top:${pct(lp[1])}%;--c:${col}"></span>`; })()}</div>`;
}

const CARD_ICON = { co2: '<span class="s-txt">CO₂</span>', humidity: null, pm: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="7" cy="8" r="1.6"/><circle cx="15" cy="6" r="1.2"/><circle cx="17" cy="14" r="1.8"/><circle cx="9" cy="16" r="1.3"/><circle cx="12" cy="11" r="1"/></svg>' };

function summaryCard(c) {
  const icon = c.id === 'humidity' ? ICONS.drop : CARD_ICON[c.id];
  const num = c.num == null ? '—' : (c.id === 'pm' ? Number(c.num).toFixed(1) : Number(c.num).toLocaleString());
  return `<div class="s-c ${c.tone}">
    <div class="s-k"><span class="s-tile">${icon}</span>${esc(c.name)}<span class="s-src">${esc(c.src)}</span></div>
    <div class="s-num"><b>${num}</b><span class="s-u">${esc(c.unit)}</span><span class="s-limt">${esc(c.limit_label)} <strong>${c.limit}</strong></span></div>
    <div class="s-st"><b>${esc(c.state)}</b>${c.fact ? ` <span>· ${esc(c.fact)}</span>` : ''}</div>
    ${sparkline(c.series || [], c.limit, c.tone, c.cross)}
    ${c.means ? `<div class="s-means">${esc(c.means)}</div>` : ''}
  </div>`;
}

// A need paired with the card that holds its evidence: the action first, then the number and its chart.
const TONE_ICON = {
  good: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
  warn: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
};
TONE_ICON.bad = TONE_ICON.warn;
const NEED_ICON = { toddler: 'toddler', sinus: 'sinus', runner: 'runner' };

function pollenBars(list, short, relief) {
  if (!list || !list.length) return '';
  if (list.every(p => !p.index && !p.in_season)) return '';   // nothing in the air: Local conditions already says so
  const order = ['Tree', 'Grass', 'Weed'], items = [...list].sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name));
  return `<div class="n-pollen" title="Google Pollen, 0 to 5${relief ? ' · ' + esc(relief) : ''}"><span class="n-pl">Pollen</span>${items.map(p =>
    `<span class="pb${p.index >= 3 ? ' hi' : p.index ? ' lo' : ''}"><em>${esc(p.name)}</em>${[1, 2, 3, 4, 5].map(k => `<i${k <= p.index ? ' class="on"' : ''}></i>`).join('')}</span>`).join('')}</div>
`;
}

// Humidity has two bad sides. Shade each only when the line comes within 10 points of it (the damp side by default),
// so a dry winter day shows "Too dry below" and the chart isn't squashed the rest of the time.
function humidityAware(c) {
  const word = { co2: 'stale', humidity: 'damp', pm: 'polluted' }[c.id];
  if (c.id !== 'humidity') return sparkline(c.series || [], c.limit, c.tone, c.cross, word);
  const v = (c.series || []).filter(has), lo = v.length ? Math.min(...v) : 50, hi = v.length ? Math.max(...v) : 50;
  const nearDry = lo < RH_LOW + 10, nearDamp = hi > RH_DAMP - 10 || !nearDry, dry = nearDry ? { limit: RH_LOW, word: 'dry' } : null;
  return sparkline(c.series || [], nearDamp ? c.limit : null, c.tone, c.cross, word, dry);
}

function needCard(n, c, r) {
  const num = c.num == null ? '—' : (c.id === 'pm' ? Number(c.num).toFixed(1) : Number(c.num).toLocaleString());
  return `<div class="s-c n-card ${c.tone}" data-need="${n.id}" data-t1="${Date.parse(r.generated_at) || Date.now()}" data-unit="${esc(c.unit)}" data-metric="${c.id}">
    <div class="s-k"><button type="button" class="n-need" data-open-home="needs" title="Change needs"><span class="n-ic">${ICONS[NEED_ICON[n.id]] || ''}</span>${esc(n.name)}</button><span class="n-metric">${esc(c.name)} · 24 h</span></div>
    <div class="s-num"><b>${num}</b><span class="s-u">${esc(c.unit)}</span><span class="n-word ${c.tone}">${esc(c.state)}</span></div>
    ${humidityAware(c)}
    ${c.means ? `<div class="s-means">${esc(c.means)}</div>` : ''}
    ${n.id === 'sinus' ? pollenBars(n.pollen, r.relief_short, r.relief) : ''}
  </div>`;
}

// ── Next to the headline: why, as a picture from the readings ──
// For "open a window": inside vs outside CO₂ on one scale with the limit, plus the last big CO₂ drop in the past 24 h
// (how fast the room clears). Hidden for other headlines until they have an honest picture.
function renderActionVis(r) {
  const box = $('s-vis'); if (!box) return;
  const key = r && r.headline && r.headline.key, inC = state.indoor ? reading(state.indoor, true).co2 : null, outC = state.outdoor ? reading(state.outdoor, false).co2 : null;
  if (key !== 'window') { box.hidden = true; box.innerHTML = ''; return; }
  if (!has(inC) || !has(outC)) {   // readings still loading: same size, placeholder bars
    box.hidden = false; delete box.dataset.real;
    box.innerHTML = `<div class="v-left"><div class="v-head">CO₂ inside vs outside</div><div class="v-bars v-skel" aria-hidden="true">
      <div class="v-row"><span>Inside</span><span class="v-track"><i></i></span><b></b></div>
      <div class="v-row"><span>Outside</span><span class="v-track"><i></i></span><b></b></div>
      <div class="v-row v-axis"><span></span><span class="v-track"></span><b></b></div></div></div><p class="v-note v-skel"><i></i><i></i></p>`;
    return;
  }
  const max = Math.max(inC, CO2_OPEN) * 1.12, w = v => (v / max * 100).toFixed(1);
  // the last big drop: at least 120 ppm within an hour (two half-hour steps), most recent first
  const card = (r.cards || []).find(c => c.id === 'co2'), ser = card ? card.series : [], t1 = Date.parse(r.generated_at) || Date.now();
  let drop = null;
  for (let i = ser.length - 2; i >= 0 && !drop; i--) for (const k of [1, 2]) {
    const a = ser[i], b = ser[i + k]; if (has(a) && has(b) && a - b >= 120) { drop = { from: a, to: b, mins: k * 30, at: t1 - 24 * 3600e3 + i * 30 * 60e3 }; break; }
  }
  box.hidden = false;
  const firstReal = !box.dataset.real && !revealNext;   // first real numbers animate in, unless the card's intro is about to
  box.dataset.real = '1';
  box.innerHTML = `<div class="v-left"><div class="v-head">CO₂ inside vs outside</div>
    <div class="v-bars" style="--lim:${w(CO2_OPEN)}%">
      <div class="v-row"><span>Inside</span><span class="v-track"><i class="${inC > CO2_OPEN ? 'over' : ''}" style="width:${w(inC)}%"></i></span><b>${Math.round(inC).toLocaleString()}</b></div>
      <div class="v-row"><span>Outside</span><span class="v-track"><i style="width:${w(outC)}%"></i></span><b>${Math.round(outC).toLocaleString()}</b></div>
      <div class="v-row v-axis"><span></span><span class="v-track"><em>limit ${CO2_OPEN}</em></span><b>ppm</b></div>
    </div></div>
    <p class="v-note">${drop ? `Last big drop: ${esc(atLabel(drop.at))}, from ${Math.round(drop.from).toLocaleString()} to ${Math.round(drop.to).toLocaleString()} ppm in ${drop.mins} min. Opening up works fast.` : 'Opening a window swaps the inside air for the outside air.'}</p>`;

  if (firstReal && !reduceMotion.matches) {
    const out = 'cubic-bezier(.2, .7, .2, 1)';
    box.querySelectorAll('.v-track i').forEach((bar, k) =>
      bar.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 1100, delay: 150 + k * 180, easing: out, fill: 'backwards' }));
    box.querySelectorAll('.v-row:not(.v-axis) b').forEach(b => { const to = parseFloat(b.textContent.replace(/,/g, '')); if (Number.isFinite(to)) rollNumber(b, to, 0, 0); });
    box.querySelectorAll('.v-axis, .v-note').forEach(el => el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 700, easing: out, fill: 'backwards' }));
  }}

// ── Coming up: an agenda of the next moments, built from the rules' needs, the BQE clock, the wind and the sun ──
const nyMinutes = () => { const p = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', minute: 'numeric', hour12: false }).formatToParts(new Date()); return (Number(p.find(x => x.type === 'hour').value) % 24) * 60 + Number(p.find(x => x.type === 'minute').value); };
const minLabel = m => { m = ((m % 1440) + 1440) % 1440; const h = Math.floor(m / 60), mm = m % 60; return `${h % 12 || 12}${mm ? ':' + String(mm).padStart(2, '0') : ''} ${h < 12 ? 'AM' : 'PM'}`; };
const hourRange = (a, b) => { const x = minLabel(a * 60), y = minLabel(b * 60); return x.split(' ')[1] === y.split(' ')[1] ? `${x.split(' ')[0]}–${y}` : `${x}–${y}`; };

function buildAgenda(r) {
  const out = [], now = nyMinutes(), h0 = Math.floor(now / 60), ahead = h => ((h * 60 - now) % 1440 + 1440) % 1440;
  const needs = Object.fromEntries((r.needs || []).map(n => [n.id, n])), key = r.headline && r.headline.key;
  const toward = (window.__bqe || {}).wind_impact === 'Blowing toward Greenpoint';
  const pm = state.outdoor ? reading(state.outdoor, false).pm : null;
  // the second half of tonight's headline, when airing has to be followed by drying
  if (key === 'window' && needs.sinus && /dry/i.test(needs.sinus.action)) out.push({ at: 1, time: 'After airing', title: 'Dry the room', sub: 'The outside air is wetter', tone: 'warn', needs: ['sinus'] });
  // the BQE rush windows in the next 12 hours
  let nextToward = null;
  for (const [a, e] of RUSH) {
    const inNow = h0 >= a && h0 < e, at = inNow ? 0 : ahead(a);
    if (at > 12 * 60) continue;
    if (toward && (nextToward == null || at < nextToward.at)) nextToward = { at, a, e, inNow };
    out.push({ at: at || 0, time: inNow ? `Now–${minLabel(e * 60)}` : hourRange(a, e), title: 'BQE rush hour',
      sub: toward ? 'The wind blows the traffic fumes here' : (window.__bqe || {}).wind_impact === 'Blowing away' ? 'The wind blows the fumes away' : 'The wind carries the fumes past the block', tone: toward ? 'warn' : '', needs: toward ? ['runner', 'toddler'] : ['runner'] });
  }
  // the run window, unless the headline is already about running
  if (key !== 'run' && has(pm)) {
    if (pm > PM_HIGH) out.push({ at: 0, time: 'Now', title: 'Skip the run', sub: `Outdoor PM2.5 is ${num(pm)}`, tone: 'bad', needs: ['runner'] });
    else if (pm > PM_FINE) out.push({ at: 0, time: 'Now', title: 'Keep runs short', sub: `Outdoor PM2.5 is ${num(pm)}`, tone: 'warn', needs: ['runner'] });
    else if (nextToward && nextToward.inNow) out.push({ at: ahead(nextToward.e), time: `From ${minLabel(nextToward.e * 60)}`, title: 'Good time to run', sub: 'Clean air, rush over', tone: 'good', needs: ['runner'] });
    else if (nextToward) out.push({ at: 0, time: `Now–${minLabel(nextToward.a * 60)}`, title: 'Good time to run', sub: 'Clean air, light traffic', tone: 'good', needs: ['runner'] });
    else out.push({ at: 0, time: 'Now', title: 'Fine to run', sub: 'Clean air', tone: 'good', needs: ['runner'] });
  }
  // sunrise or sunset in the next 12 hours
  const el = m => (typeof SKY !== 'undefined' && SKY && SKY.sunEl) ? SKY.sunEl(((m % 1440) + 1440) % 1440) : null;
  if (el(now) != null) for (let m = now + 5; m < now + 12 * 60; m += 5) {
    const e0 = el(m - 5), e1 = el(m);
    if ((e0 < 0) !== (e1 < 0)) { out.push({ at: m - now, time: minLabel(Math.round(m / 5) * 5 - 5), title: e1 >= 0 ? 'Sunrise' : 'Sunset', sub: '', tone: 'sun', needs: [] }); break; }
  }
  // airing the bedroom before the toddler's bedtime
  if (needs.toddler && needs.toddler.tone !== 'good' && needs.toddler.tone !== 'muted' && h0 >= 12 && h0 < 20)
    out.push({ at: ahead(20), time: '8 PM', title: 'Air the bedroom before sleep', sub: `If CO₂ is still over ${CO2_OPEN}`, tone: '', needs: ['toddler'] });
  return out.sort((x, y) => x.at - y.at).slice(0, 5);
}

function renderAgenda(r) {
  const box = $('s-ag'); if (!box || !r || !r.needs) return;
  // until the outdoor reading, the wind and the sky are in, show placeholder rows at full size (no partial list, no jump)
  const ready = state.outdoor && window.__bqe && typeof SKY !== 'undefined' && SKY;
  if (!ready) {
    box.hidden = false;
    box.innerHTML = `<h3>Coming up</h3><ol class="ag ag-skel" aria-hidden="true">${'<li><span class="ag-t"><i></i></span><span class="ag-d"></span><span class="ag-x"><i></i></span></li>'.repeat(4)}</ol>`;
    return;
  }
  const items = buildAgenda(r);
  box.hidden = !items.length;
  box.innerHTML = `<h3>Coming up</h3><ol class="ag">${items.map(it => `<li class="${it.tone}"${it.sub ? ` title="${esc(it.sub)}"` : ''}><span class="ag-t">${esc(it.time)}</span><span class="ag-d"></span><span class="ag-x"><b>${esc(it.title)}</b></span></li>`).join('')}</ol>`;
}


// After a refresh (and on first load): the headline fades in, Coming up appears moment by moment along its arrow,
// the CO₂ bars grow, each chart line draws from left to right and ends on a dot for the latest reading, and the numbers roll.
let revealNext = true;
const prevNums = {};
function rollNumber(el, to, from, digits) {
  const fmt = v => digits ? v.toFixed(digits) : Math.round(v).toLocaleString();
  el.animate([{ opacity: .6 }, { opacity: 1 }], { duration: 300 });
  const t0 = performance.now(), dur = 900, ease = t => 1 - Math.pow(1 - t, 3);
  const step = now => { const k = Math.min(1, (now - t0) / dur); el.textContent = fmt(from + (to - from) * ease(k)); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function reveal() {
  const cards = [...document.querySelectorAll('#s-cards .n-card')];
  const remember = () => cards.forEach(c => { const b = c.querySelector('.s-num b'); if (b) prevNums[c.dataset.metric] = parseFloat(b.textContent.replace(/,/g, '')); });
  if (reduceMotion.matches) { remember(); return; }
  const out = 'cubic-bezier(.2, .7, .2, 1)', draw = 'cubic-bezier(.65, 0, .35, 1)';
  for (const el of [$('lead'), $('why')]) el && el.animate([{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], { duration: 480, easing: out });
  document.querySelectorAll('#s-ag .ag li').forEach((li, i) =>
    li.animate([{ opacity: 0, transform: 'translateX(-8px)' }, { opacity: 1, transform: 'none' }], { duration: 520, delay: 180 + i * 140, easing: out, fill: 'backwards' }));
  document.querySelectorAll('#s-vis .v-row:not(.v-axis) b').forEach(b => { const to = parseFloat(b.textContent.replace(/,/g, '')); if (Number.isFinite(to)) rollNumber(b, to, 0, 0); });
  document.querySelectorAll('#s-vis .v-axis, #s-vis .v-note').forEach(el => el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 700, easing: out, fill: 'backwards' }));
  document.querySelectorAll('#s-vis .v-track i').forEach((bar, i) =>
    bar.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 1000, delay: 160 + i * 140, easing: out, fill: 'backwards' }));
  cards.forEach((c, i) => {
    const svg = c.querySelector('.s-spark svg'), end = c.querySelector('.s-end'), delay = 160 + i * 220;
    if (svg) svg.style.clipPath = 'inset(0 100% 0 0)';
    if (end) end.style.opacity = 0;
    onVisible(c, () => {
      if (svg) { svg.style.clipPath = ''; svg.animate([{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0 0 0)' }], { duration: 1700, delay, easing: draw, fill: 'backwards' }); }
      if (end) { end.style.opacity = ''; end.animate([{ transform: 'translate(-50%, -50%) scale(0)', opacity: 0 }, { transform: 'translate(-50%, -50%) scale(1.5)', opacity: 1, offset: .6 }, { transform: 'translate(-50%, -50%) scale(1)', opacity: 1 }],
        { duration: 520, delay: delay + 1600, easing: out, fill: 'backwards' }); }
    });
    const b = c.querySelector('.s-num b'), to = b && parseFloat(b.textContent.replace(/,/g, ''));
    if (b && Number.isFinite(to)) { const from = prevNums[c.dataset.metric]; rollNumber(b, to, Number.isFinite(from) ? from : 0, c.dataset.metric === 'pm' ? 1 : 0); }
  });
  remember();
}

function renderRead(r, stale, why) {
  shownSig = readSig(r);
  if (!r.headline) return;                      // a summary saved in the old format
  // in front of the headline: an alert triangle when there's something to do, a check when all is fine
  const urgent = r.headline.tone === 'warn' || r.headline.tone === 'bad';
  const key = urgent || r.headline.tone === 'good';
  $('s-act').hidden = true;
  document.querySelector('.s-main').className = 's-main' + (r.headline.tone === 'warn' || r.headline.tone === 'bad' ? ' alert ' + r.headline.tone : '');
  $('s-act').className = 's-act ' + r.headline.tone;
  $('s-act').innerHTML = key ? (urgent ? TONE_ICON.warn : TONE_ICON.good) : '';
  $('lead').textContent = r.headline.text;
  $('lead').className = 's-do ' + r.headline.tone;
  $('why').textContent = r.why || '';

  if (r.needs && r.needs.length) {
    const byId = Object.fromEntries((r.cards || []).map(c => [c.id, c]));
    $('s-cards').innerHTML = r.needs.filter(n => byId[n.metric]).map(n => needCard(n, byId[n.metric], r)).join('');
    wireSparks();
    renderAgenda(r);
    renderActionVis(r);
  } else $('s-cards').innerHTML = (r.cards || []).map(summaryCard).join('');   // a summary saved in the previous format
  if (revealNext) { revealNext = false; reveal(); }
  const by = r.source === 'model' ? `by ${r.model_name || r.model}` : 'from the rules';
  // the byline says who wrote the advice: Claude, or the rules when the model is off
  $('s-by').textContent = r.source === 'model' ? '· based on' : '· from the rules, based on';
  document.querySelector('.s-by b').textContent = r.source === 'model' ? 'AI advice' : 'Advice';
  const swaps = (r.replaced || []).length;
  const note = $('stale-note');
  note.hidden = !why;
  note.textContent = why === 'offline' ? `Earlier summary, written at ${r.clock}. It updates when the page is back online.`
    : why === 'failed' ? `Earlier summary, written at ${r.clock}. A new one could not be written just now.` : '';
  $('read-meta').textContent = `Written ${by} at ${r.clock}${stale ? ' (earlier summary)' : ''}.` +
    (swaps ? ` ${swaps === 1 ? 'One line' : swaps + ' lines'} replaced by the rules.` : '') +
    (r.source !== 'model' && r.note ? ' ' + r.note : '');
}

// ── Busy state ────────────────────────────────────────
// One counter so overlapping work (a manual refresh and the timer) shows one busy state.

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const TURN_MS = 900;
let busyCount = 0, spin = null, lastStamp = null, loadFailed = false;

// "Right now" only while the readings are fresh. Otherwise the title says when they are from.
const FRESH_MIN = 10;
function showUpdated() {
  const title = $('now-title'), meta = $('updated');
  const offline = navigator.onLine === false;
  const set = (t, m, stale) => {
    title.textContent = t; meta.textContent = busyCount ? '' : m;   // while busy, the button says Updating…
    title.classList.toggle('stale', stale); meta.classList.toggle('stale', stale && !busyCount);
  };
  if (lastStamp == null) return set(offline ? 'Offline' : 'Right now', loadFailed ? 'Readings did not load' : '', offline || loadFailed);
  const d = new Date(lastStamp);
  const day = t => new Date(t).toLocaleDateString('en-US', { timeZone: TZ });
  const at = day(d) === day(Date.now()) ? clock(d)
    : d.toLocaleString('en-US', { timeZone: TZ, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const mins = Math.round((Date.now() - lastStamp) / 60000);
  const age = mins < 60 ? `${mins} min old` : mins < 48 * 60 ? `${Math.round(mins / 60)} h old` : `${Math.round(mins / 1440)} days old`;
  if (offline) return set('Offline', `Last reading ${at}`, true);
  if (mins > FRESH_MIN) return set(`As of ${at}`, age, true);
  set('Right now', '', false);
}

function startSpin() {
  if (reduceMotion.matches) return;
  if (spin) { spin.effect.updateTiming({ iterations: Infinity }); return; }
  spin = $('read-refresh').querySelector('svg').animate(
    [{ transform: 'rotate(0turn)' }, { transform: 'rotate(1turn)' }],
    { duration: TURN_MS, iterations: Infinity, easing: 'linear' });
}

function stopSpin() {
  if (!spin) return;
  const a = spin;
  // Finish the turn in progress instead of snapping back to the start.
  a.effect.updateTiming({ iterations: Math.floor(a.currentTime / TURN_MS) + 1 });
  a.finished.then(() => { if (spin === a) spin = null; }, () => {});
}

// What the AI is doing, shown after the source icons at the real moments: reading the sources, then writing.
// It sits after the icons so nothing before it moves.
function setPhase(p) {
  const ai = document.querySelector('section.ai'), step = $('s-step'); if (!ai || !step) return;
  if (p) { ai.dataset.phase = p; step.textContent = p === 'read' ? '· reading your monitors and sources…' : '· writing advice…'; }
  else { delete ai.dataset.phase; step.textContent = ''; }
}

function setBusy(on) {
  busyCount = Math.max(0, busyCount + (on ? 1 : -1));
  const busy = busyCount > 0;
  for (const el of [document.querySelector('section.ai'), $('read-refresh')]) el.setAttribute('aria-busy', String(busy));
  busy ? startSpin() : stopSpin();
  if (!busy) setPhase(null);
  const lbl = $('read-refresh').querySelector('span'); if (lbl) lbl.textContent = busy ? 'Updating…' : 'Refresh';
  showUpdated();
}

// A short fade on the parts that changed, so a new read is noticed without hiding the old one.
function settle(el, before) {
  if (!el || reduceMotion.matches || el.innerHTML === before) return;
  el.animate([{ opacity: .35 }, { opacity: 1 }], { duration: 420, easing: 'cubic-bezier(.2, .7, .2, 1)' });
}

// What the advice says, without the parts that change on every write (time, cost, cache flag).
const readSig = r => JSON.stringify({ ...r, generated_at: 0, clock: 0, usage: 0, cached: 0, model: 0, model_name: 0 });
let shownSig = null;

async function loadRead(force) {
  const payload = readPayload();
  const key = readKey(payload);
  if (!force && state.read && Date.now() - state.readAt < READ_MAX_AGE && key === state.readKey) return;
  setBusy(true);
  try {
    if (busyCount) setPhase('write');
    const r = await getJSON('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, force: !!force })
    });
    Object.assign(state, { read: r, readAt: Date.now(), readKey: key });
    store.set({ at: Date.now(), read: r });
    // nothing new to show: leave the page alone (no re-render, no fade). A manual refresh always shows its result.
    if (!revealNext && readSig(r) === shownSig) { renderAgenda(r); return; }
    const parts = ['lead', 'why', 's-cards'].map(id => [$(id), $(id).innerHTML]);
    renderRead(r, false);
    parts.forEach(([el, before]) => settle(el, before));
  } catch (err) {
    console.error('read', err);
    const why = navigator.onLine === false ? 'offline' : 'failed';
    const saved = store.get();
    if (!state.read && saved && saved.read) renderRead(saved.read, true, why);
    else if (!state.read) $('lead').innerHTML = '<span class="pending">The summary did not load. The readings below are from the last update.</span>';
    else renderRead(state.read, true, why);
  } finally {
    setBusy(false);
  }
}

// ── Refresh ───────────────────────────────────────────

let inFlight = null, lastRefresh = 0;

// manual: the person pressed refresh, so show the busy state from the first request and write a new read.
// busy: show the updating state without asking for a new summary (the first load)
function refresh({ manual = false, busy = false } = {}) {
  if (inFlight) return inFlight;
  const showBusy = manual || busy;
  if (showBusy) setBusy(true);
  if (manual) revealNext = true;
  inFlight = (async () => {
    try {
      if (showBusy) setPhase('read');
      forceNext = manual;
      const nbP = getJSON('/api/neighborhood').catch(() => null);   // the slowest source; the rest doesn't wait for it
      const [current, ctx] = await Promise.all([getJSON('/api/current'), getJSON('/api/context').catch(() => null)]);
      state.indoor = current.find(m => m.locationType === 'indoor') || null;
      state.outdoor = current.find(m => m.locationType === 'outdoor') || null;
      renderMonitors();
      showBootRead();
      nbP.then(nb => { if (Array.isArray(nb)) { state.neighbors = nb; renderNeighborhood(); } });
      if (ctx) renderContext(ctx);
      contextStatus(ctx);
      await Promise.all([loadRead(manual), loadCharts({ fresh: true }), nbP]);
      forceNext = false;
    } catch (err) {
      console.error('refresh', err);
      loadFailed = true;
    } finally {
      forceNext = false;
      if (showBusy) setBusy(false);
      showUpdated();
      lastRefresh = Date.now();
      inFlight = null;
    }
  })();
  return inFlight;
}

$('ranges').addEventListener('click', e => {
  const btn = e.target.closest('button');
  if (btn) { state.range = btn.dataset.range; loadCharts(); }
});
$('read-refresh').addEventListener('click', () => refresh({ manual: true }));

// Show the last summary at once. Offline, any age will do; online, only a recent one.
const cached = store.get();
// The saved summary waits for the monitors' readings (usually < 0.5 s), so the whole card, CO₂ bars included,
// animates in together. At most 1.5 s; offline it shows at once.
let bootRead = null;
function showBootRead() {
  if (!bootRead) return;
  const c = bootRead; bootRead = null;
  Object.assign(state, { read: c.read, readAt: 0 });   // shown now; refreshed in the background
  renderRead(c.read, true, navigator.onLine === false ? 'offline' : undefined);
}
if (cached && cached.read && (navigator.onLine === false || Date.now() - cached.at < 30 * 60 * 1000)) {
  bootRead = cached;
  if (navigator.onLine === false) showBootRead(); else setTimeout(showBootRead, 1500);
}
refresh({ busy: true });   // the first load shows the updating state; the saved summary stays readable meanwhile
setInterval(() => { if (!document.hidden) refresh(); }, 60000);   // background tabs don't poll
document.addEventListener('visibilitychange', () => { if (!document.hidden && Date.now() - lastRefresh > 60000) refresh(); });
window.addEventListener('offline', showUpdated);
window.addEventListener('online', () => { showUpdated(); refresh(); });

// ── Theme ─────────────────────────────────────────────

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.querySelector('meta[name="theme-color"]').setAttribute('content', theme === 'dark' ? '#0b131c' : '#f4f6f8');
  let saved = null; try { saved = localStorage.getItem('aq-theme'); } catch {}
  document.querySelectorAll('[data-theme-pick]').forEach(b => {
    const on = b.dataset.themePick === (saved || 'system');
    b.classList.toggle('on', on); b.setAttribute('aria-checked', String(on));
  });
  const tb = $('theme-toggle'); if (tb) tb.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  if (typeof SKY !== 'undefined' && SKY) SKY.theme();
  if (typeof NBMAP !== 'undefined') NBMAP.theme();
}
applyTheme(document.documentElement.getAttribute('data-theme') || 'light');
// A theme change is one cross-fade of the whole page. Per-element fades are switched off meanwhile,
// so the title, cards and sky can't change at different speeds.
function switchTheme(theme) {
  const root = document.documentElement;
  if (root.getAttribute('data-theme') === theme) { applyTheme(theme); return; }
  const swap = () => { root.classList.add('theme-swap'); applyTheme(theme); };
  const done = () => requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove('theme-swap')));
  if (document.startViewTransition && !reduceMotion.matches) document.startViewTransition(swap).finished.finally(done);
  else { swap(); done(); }
}
document.querySelectorAll('[data-theme-pick]').forEach(b => b.addEventListener('click', () => {
  const pick = b.dataset.themePick;
  try { pick === 'system' ? localStorage.removeItem('aq-theme') : localStorage.setItem('aq-theme', pick); } catch {}
  switchTheme(pick === 'system' ? (darkQuery.matches ? 'dark' : 'light') : pick);
}));
$('theme-toggle').addEventListener('click', e => {
  e.preventDefault(); e.stopPropagation();
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('aq-theme', next); } catch {}
  switchTheme(next);
});
// Follow the system until the viewer picks a theme.
darkQuery.addEventListener('change', e => {
  let saved = null;
  try { saved = localStorage.getItem('aq-theme'); } catch {}
  if (!saved) switchTheme(e.matches ? 'dark' : 'light');
});

// ── Install and offline ───────────────────────────────

if ('serviceWorker' in navigator) {
  const local = ['localhost', '127.0.0.1'].includes(location.hostname);
  if (local) {
    // Local development: drop any old worker so edits show up on refresh.
    navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
  } else {
    navigator.serviceWorker.register('/sw.js').then(reg => setInterval(() => reg.update(), 60 * 60 * 1000))
      .catch(err => console.error('Service worker registration failed:', err));
  }
}

// Saved-view popover: standard dropdown behavior.
(() => {
  const view = document.querySelector('.bar details.custom');
  if (!view) return;
  const trigger = view.querySelector('summary');
  const sync = () => trigger.setAttribute('aria-expanded', String(view.open));
  const close = (refocus) => { if (!view.open) return; view.open = false; sync(); if (refocus) trigger.focus(); };
  view.addEventListener('toggle', sync); sync();
  $('view-close').addEventListener('click', e => { e.preventDefault(); close(true); });
  document.addEventListener('click', e => { if (view.open && !view.contains(e.target)) close(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && view.open) close(true); });
})();

// The summary byline shows its sources as a small stack of the Home panel's icons: gray at rest, in color and fanned out on hover,
// with a dot on any source that isn't answering, and a card listing each source with its live status.
const SOURCES = [['AirGradient ONE', 'one', 'Your indoor monitor'], ['AirGradient Open Air', 'openair', 'Your outdoor monitor'],
  ['Open-Meteo', 'wx', 'Weather · Open-Meteo'], ['Google Pollen', 'pollen', 'Pollen · Google'], ['NOAA HMS', 'smoke', 'Smoke · NOAA'], ['BQE estimate', 'bqe', 'Traffic · BQE estimate']];
function renderSources() {
  const box = $('s-src'); if (!box) return;
  const rows = [...document.querySelectorAll('.blocks .pr')];
  const icon = name => { const li = rows.find(r => { const b = r.querySelector('.pr-t b'); return b && b.textContent === name; }); return li ? li.querySelector('.pr-ic').innerHTML : ''; };
  const st = id => { const el = $('st-' + id); return el ? { tone: (el.className.match(/\b(good|warn|bad|neutral)\b/) || [])[1] || '', text: el.textContent.trim() } : { tone: '', text: '' }; };
  box.innerHTML = SOURCES.map(([name, id]) => { const t = st(id).tone; return `<span class="s-src-i${t === 'warn' || t === 'bad' ? ' ' + t : ''}" style="--i:${SOURCES.findIndex(x => x[1] === id)}">${icon(name)}</span>`; }).join('') +
    `<span class="s-src-card" role="tooltip"><strong>Sources</strong>${SOURCES.map(([name, id, label]) => { const x = st(id);
      return `<span class="s-src-row"><span class="s-src-ic">${icon(name)}</span><span>${label}</span><em class="${x.tone}">${esc(x.text || '…')}</em></span>`; }).join('')}</span>`;
}
renderSources();

// Links from the advice into the Home panel: a card's need opens it at "Specific needs", the byline's sources at the sources.
function openHome(where) {
  const home = document.querySelector('.bar details.custom'), dsp = $('dsp'); if (!home) return;
  if (dsp) dsp.open = false;
  home.open = true;
  window.scrollTo({ top: 0, behavior: reduceMotion.matches ? 'auto' : 'smooth' });
  const heads = [...home.querySelectorAll('.blocks section.pg h4')];
  const targets = where === 'needs' ? heads.filter(h => /needs/i.test(h.textContent)) : heads.filter(h => /monitors|outside/i.test(h.textContent));
  targets.forEach(h => { const sec = h.closest('section');
    if (!reduceMotion.matches) sec.animate([{ backgroundColor: 'var(--accent-soft)' }, { backgroundColor: 'transparent' }], { duration: 1600, delay: 250, easing: 'ease-out' }); });
}
document.addEventListener('click', e => {
  const t = e.target.closest('[data-open-home]'); if (!t) return;
  e.preventDefault(); e.stopPropagation(); openHome(t.dataset.openHome);
}, true);
$('s-src') && $('s-src').addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openHome('sources'); } });

// Dev and local only: the build and a Clear cache button (the dev site registers a service worker that caches files).
(() => {
  if (location.hostname === 'air-quality-dashboard.up.railway.app' || /[?&]shot\b/.test(location.search)) return;   // never on production or in screenshots
  const bar = $('devbar'); if (!bar) return;
  $('build').textContent = document.body.dataset.build || 'local';
  bar.hidden = false;
  $('clear-cache').addEventListener('click', async () => {
    $('clear-cache').textContent = 'Clearing…';
    try {
      if ('serviceWorker' in navigator) for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
      if ('caches' in window) await Promise.all((await caches.keys()).map(k => caches.delete(k)));
      try { localStorage.removeItem(CACHE_KEY); } catch {}
    } finally { location.reload(); }
  });
})();

// The address opens the map; it must not also toggle the Home panel.
document.querySelectorAll('a.addr').forEach(a => a.addEventListener('click', e => e.stopPropagation()));
