// Home Air Quality: the demo's top area (the name and pitch, then three ways in: the made-up home's samples 1 2 3, a public
// monitor near you, your own monitor) and its monitor picker. Demo only: app.js draws it where showsTop says (window.APP has
// `now`, a sample, or `public`, a monitor's page; never in screenshots). Also gives every /api call its URL (apiUrl).
// Mocks: internal/design-archive/93-demo-top-area (concept E), public-monitor/ (the picker, README round 4).
(function (root) {
  'use strict';

  const SAMPLES = [1, 2, 3];        // the sample numbers, when APP.now doesn't list them (a monitor's page has no APP.now)
  const ROWS_SHOWN = 6;             // rows the picker shows before "Show N more"
  const COORD_DECIMALS = 2;         // decimals kept from a location before it leaves the browser: about 1 km
  const KM_WHOLE_FROM = 10;         // km: distances from here up show as whole kilometres (12 km), below with one decimal
  const PM_WHOLE_FROM = 10;         // µg/m³: as the page's rings, one decimal below 10 (3.9), whole numbers from 10 up
  const GEO_TIMEOUT_MS = 10000;     // how long "Near me" waits for the browser's location before saying it's off
  const GEO_MAX_AGE_MS = 600000;    // a location the browser found in the last 10 minutes is good enough
  const REPO_URL = 'https://github.com/sguyon/home-air-quality';
  const SOURCE_URL = `${REPO_URL}#installation`;   // the README's setup steps: the "Setup" button
  // GitHub's mark (Octicons mark-github, MIT), drawn before "Setup" so the button says where it goes
  const GH_MARK = '<svg class="dt-gh" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>';
  const GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search';
  const DEFAULT_PLACE = 'New York';   // demo/public.py DEFAULT_LIST: the list before anyone gives a location
  const PICKER_PARTS = '#db-pickwrap, [aria-controls="db-pop"]';   // the picker and every button that opens it

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // the page's PM2.5 words (home.js), so the picker and the cards use one scale
  const HOME = typeof module !== 'undefined' && module.exports ? require('./home.js') : root;
  const pmLevel = (...a) => HOME.pmLevel(...a);
  const MAP_URL = HOME.MAP_PAGE;   // AirGradient's public map (home.js), the credit's link here and on the monitor card

  const ICON = {
    chev: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>',
    near: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11 22 2l-9 19-2-8z"/></svg>',
    search: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
    close: '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  };

  // ── pure parts (tested in tests/picker.test.mjs) ──

  // Every /api call's URL: a monitor's page names the monitor, a sample its moment, a real home nothing.
  function apiUrl(app, url) {
    const add = (k, v) => `${url}${url.includes('?') ? '&' : '?'}${k}=${encodeURIComponent(v)}`;
    if (app.public && app.public.id) return add('monitor', app.public.id);
    return app.now ? add('moment', app.now.moment) : url;
  }

  const roundCoord = x => Number(Number(x).toFixed(COORD_DECIMALS));

  // The top area's drawn marks: a text arrow like ↗ shows as an emoji on iOS (Sacha, 2026-11-12)
  // The logo (index.html's .now-mark, mock 94 round 8 a), always the live one here: the demo's readings are always fresh
  const MARK = '<svg class="dt-mark" viewBox="0 0 32 32" aria-hidden="true"><mask id="dt-lg-m"><path d="M13.8 3.2Q16 1.4 18.2 3.2L30.1 12.8Q31 13.5 31 14.7V25Q31 31 25 31H7Q1 31 1 25V14.7Q1 13.5 1.9 12.8Z" fill="#fff"/>' +
    '<path d="M0 17.5h32M16 17.5v15" stroke="#000" stroke-width="2.6"/></mask><g mask="url(#dt-lg-m)"><rect class="lg-house" width="32" height="32"/><rect class="lg-roof" width="32" height="17.5"/>' +
    '<path class="lg-glow" d="M8.6 16.2A7.4 7.4 0 0 1 23.4 16.2Z"/><path class="lg-dot" d="M11.6 16.2A4.4 4.4 0 0 1 20.4 16.2Z"/></g></svg>';
  const WAY_ICON = {
    home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V21H3z"/><path d="M9 21v-6h6v6"/></svg>',
    pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
    monitor: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="3"/><path d="M9 8h6M9 12h6"/></svg>',
  };
  const OUT_ICON = '<svg class="dt-bi" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg>';
  const FOLD_KEY = 'aq-demo-top';   // localStorage: 'folded' once the visitor hid the top area
  // The fold button's words: Hide with a chevron up while open, Show with a chevron down once folded
  const foldLabel = folded => `${folded ? 'Show' : 'Hide'}<svg class="dt-fi" viewBox="0 0 24 24" aria-hidden="true"><path d="${folded ? 'm6 9 6 6 6-6' : 'm18 15-6-6-6 6'}"/></svg>`;

  // The demo's top area (mock 93, E): the name and pitch, then the three ways in, each a title, one line and its control.
  // See a demo: the samples (the shown one marked and named; none on a monitor's page). See a live monitor near you: the
  // picker's button (the chosen monitor's name, or "Select a monitor"). Set up your own monitor: the README's setup steps.
  // Folded ({folded: true}, Sacha, 2026-11-13): one slim line, the logo, the name, DEMO and Show (app.css, .is-folded).
  function topHTML(app, { folded = false } = {}) {
    const pub = app.public || null;
    const listed = (app.now && app.now.moments) || [];
    const samples = listed.length ? listed : SAMPLES.map(n => ({ n }));
    const shown = (!pub || pub.error) && app.now ? app.now.moment : null;   // an unknown monitor's page ({id, error}) shows the sample
    const links = samples.map(m => `<a href="?sample=${m.n}"${m.label ? ` title="${esc(m.label)}"` : ''}${m.key && m.key === shown ? ' aria-current="page"' : ''}>${m.n}</a>`).join('');
    const name = pub && !pub.error && pub.name ? esc(pub.name) : '';
    const way = (cls, tone, icon, title, line, control) => `<div class="dt-way${cls}"><p class="dt-t"><span class="dt-ico dt-${tone}">${WAY_ICON[icon]}</span>${title}</p>` +
      `<p class="dt-s">${line}</p><div class="dt-ctl">${control}</div></div>`;
    return `<div class="dt-in">
  <button type="button" class="dt-fold" id="dt-fold" aria-expanded="${!folded}" aria-label="${folded ? 'Show the demo\'s top area' : 'Hide the demo\'s top area'}">${foldLabel(folded)}</button>
  <div class="dt-brand"><h1 class="dt-name">${MARK}Home Air Quality <span class="dt-tag">Demo</span></h1>
    <p class="dt-pitch">An <a href="${REPO_URL}">open-source</a> app for your AirGradient monitors. <span>It adds the weather forecast, pollen and more, and tells you what to do for profiles like young kids, allergies or running.</span></p></div>
  ${way(' dt-w1', 'ink', 'home', 'See a demo',
    '<span class="dt-gen">Sample data from a made\u2011up home.</span>',   // \u2011: a hyphen that never ends a line
    `<span class="dt-lab" id="dt-lab">Sample</span><nav class="dt-seg" aria-labelledby="dt-lab">${links}</nav>`)}
  ${way('', 'sky', 'pin', 'See a live monitor near you', 'Real readings from a public AirGradient monitor.',
    `<span class="dt-pickwrap" id="db-pickwrap"><button type="button" class="dt-pick${name ? ' is-chosen' : ''}" id="db-pick"${name ? ` aria-label="Monitor: ${name}. Change monitor"` : ''} aria-haspopup="dialog" aria-expanded="false" aria-controls="db-pop"><i class="live" aria-hidden="true"></i><span class="dt-pick-t">${name || 'Select a monitor'}</span>${ICON.chev}</button></span>`)}
  ${way('', 'good', 'monitor', 'Set up your own monitor', 'You install it, with a coding agent or Docker.',
    `<a class="dt-btn" href="${SOURCE_URL}" target="_blank" rel="noopener" aria-label="Setup, on GitHub">${GH_MARK}Setup${OUT_ICON}</a>`)}
</div>`;
  }

  // Where the top area shows: every demo page (the made-up home, a sample, a moment, a monitor's page), whatever other
  // parameters the URL carries (?utm_source=). Never in screenshots (?shot: the README's images), on a real home or the token card.
  function showsTop(app, search) {
    if (!app || !(app.now || app.public) || app.state === 'no_token') return false;
    return !new URLSearchParams(search || '').has('shot');
  }

  const kmText = km => !Number.isFinite(km) ? '' : `${km >= KM_WHOLE_FROM ? Math.round(km) : (Math.round(km * 10) / 10).toFixed(1)} km`;
  const pmText = v => { const r = Math.round(v * 10) / 10; return Math.abs(r) >= PM_WHOLE_FROM ? String(Math.round(v)) : r.toFixed(1); };

  // The picker's rows (GET /api/monitors' `monitors`): name, street · distance, owner (the credit), PM2.5 now and its word.
  // limits: the page's (APP.limits) unless given; without any (Node, no page) the rows show the number with no word.
  function rowsHTML(monitors, currentId, limits = (root.APP && root.APP.limits) || null) {
    return (monitors || []).map(m => {
      const id = Number(m.locationId);
      const pm = m.pm02 == null || Number.isNaN(Number(m.pm02)) ? null : Number(m.pm02);
      const lv = m.offline ? { word: 'Offline', tone: 'muted' } : limits ? pmLevel(pm, limits) : { word: '', tone: 'muted' };
      const value = m.offline || pm == null ? '—' : pmText(pm);
      const where = [m.street ? esc(m.street) : '', kmText(Number(m.distance_km))].filter(Boolean).join(' · ');
      return `<li><a class="pm-row" href="?monitor=${encodeURIComponent(id)}"${id === Number(currentId) ? ' aria-current="page"' : ''}>` +
        `<span class="pm-t"><b>${esc(m.name || `Monitor ${id}`)}</b>${where ? `<em>${where}</em>` : ''}${m.contributor ? `<em class="pm-by">Shared by ${esc(m.contributor)}</em>` : ''}</span>` +
        `<span class="pm-v ${lv.tone}"><b>${value}</b><em>${esc(lv.word)}</em></span></a></li>`;
    }).join('');
  }

  // A click on the picker or on a button that opens it: the click-outside handler leaves the picker open.
  const insidePicker = el => !!(el && el.closest && el.closest(PICKER_PARTS));

  // A typed place's first match (Open-Meteo's free geocoder, from the browser), or null.
  async function geocode(q) {
    const r = await fetch(`${GEOCODE_URL}?name=${encodeURIComponent(q)}&count=1`);
    if (!r.ok) throw new Error(`geocode ${r.status}`);
    const hit = ((await r.json()).results || [])[0];
    return hit ? { name: hit.name, lat: hit.latitude, lon: hit.longitude } : null;
  }

  // Near me failed (location off or refused): the list still shows the default place's monitors, so say so; it read as
  // the visitor's own location (Sacha, 2026-11-12: "if location is off why does it show my nearby places still?")
  const offNote = place => `Location is off, so this list is around ${place}. Type a place to see another.`;

  const api = { apiUrl, roundCoord, topHTML, showsTop, rowsHTML, geocode, insidePicker, offNote };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  // ── the page ──
  const $ = id => document.getElementById(id);
  const st = { app: null, rows: null, all: false, near: DEFAULT_PLACE, defaultRows: null, seq: 0, loading: false };

  const panelHTML = () => `<div class="pm-pop" id="db-pop" role="dialog" aria-label="Public AirGradient monitors" hidden>
  <p class="pm-note pm-error" id="pm-error" hidden></p>
  <div class="pop-head"><div><b>Public AirGradient monitors</b><span>Live readings from monitors their owners share on AirGradient's map. Pick one to see its readings on this page.</span></div>
    <button type="button" class="pop-close" id="pm-close" aria-label="Close">${ICON.close}</button></div>
  <div class="pm-find">
    <button type="button" class="pm-near" id="pm-near" aria-pressed="false">${ICON.near}Near me</button>
    <form class="pm-place" id="pm-place" role="search">${ICON.search}<input type="text" id="pm-q" placeholder="Or type a place" aria-label="Find monitors near a place" autocomplete="off" enterkeyhint="search"></form>
  </div>
  <p class="pm-note" id="pm-note" hidden></p>
  <div class="pm-head"><span id="pm-near-h">Nearest to ${esc(DEFAULT_PLACE)}</span><span>PM2.5 now</span></div>
  <ul class="pm-list" id="pm-list"></ul>
  <p class="pm-msg" id="pm-msg" hidden></p>
  <button type="button" class="pm-more" id="pm-more" hidden></button>
  <p class="pm-credit">From <a href="${MAP_URL}" target="_blank" rel="noopener">AirGradient's public map</a>. Each owner shares their readings under CC BY-SA; the name on each row is the credit.</p>
</div>`;

  const note = (id, text) => { const el = $(id); el.textContent = text || ''; el.hidden = !text; };

  function draw() {
    const rows = st.rows || [];
    const shown = st.all ? rows : rows.slice(0, ROWS_SHOWN);
    $('pm-near-h').textContent = `Nearest to ${st.near}`;
    $('pm-near-h').parentElement.hidden = false;   // a failed first load hid the list's header
    $('pm-list').innerHTML = rowsHTML(shown, st.app.public && st.app.public.id, st.app.limits);
    $('pm-list').hidden = !rows.length;
    const more = rows.length - shown.length;
    $('pm-more').hidden = more <= 0;
    $('pm-more').innerHTML = more > 0 ? `Show ${more} more ${ICON.chev}` : '';
  }

  // GET /api/monitors (around lat/lon, or New York), then draw it under "Nearest to <near>". A newer request wins.
  async function load(near, lat, lon) {
    const seq = ++st.seq;
    st.loading = true;
    note('pm-msg', st.rows ? '' : 'Loading monitors…');
    try {
      const q = lat == null ? '' : `?lat=${roundCoord(lat)}&lon=${roundCoord(lon)}`;
      const r = await fetch(`/api/monitors${q}`);
      const body = await r.json().catch(() => ({}));
      if (seq !== st.seq) return;
      if (!r.ok) throw new Error(body.error || "AirGradient's public map didn't answer");
      st.rows = body.monitors || []; st.near = near; st.all = false;
      if (lat == null) st.defaultRows = st.rows;
      draw();
      note('pm-msg', st.rows.length ? '' : 'No public outdoor monitors found.');
    } catch (e) {
      if (seq !== st.seq) return;
      const msg = e.message || "AirGradient's public map didn't answer";
      if (!st.rows) { $('pm-list').hidden = true; $('pm-near-h').parentElement.hidden = true; }
      // a monitor's page that already says the map didn't answer doesn't say it twice
      note('pm-msg', st.app.public && st.app.public.error === msg ? '' : msg);
    } finally {
      if (seq === st.seq) st.loading = false;
    }
  }

  function nearMe() {
    const off = () => { note('pm-note', offNote(st.near || DEFAULT_PLACE)); $('pm-near').setAttribute('aria-pressed', 'false'); $('pm-q').focus(); };
    if (!navigator.geolocation) return off();
    note('pm-note', '');
    navigator.geolocation.getCurrentPosition(p => {
      $('pm-near').setAttribute('aria-pressed', 'true');
      load('you', p.coords.latitude, p.coords.longitude);
    }, off, { timeout: GEO_TIMEOUT_MS, maximumAge: GEO_MAX_AGE_MS });
  }

  async function findPlace(q) {
    q = q.trim();
    if (!q) return;
    note('pm-note', '');
    try {
      const hit = await geocode(q);
      if (!hit) return note('pm-note', `No place called "${q}" found. Try another name.`);
      $('pm-near').setAttribute('aria-pressed', 'false');
      load(hit.name, hit.lat, hit.lon);
    } catch {
      note('pm-note', "The place search didn't answer. Try again in a moment.");
    }
  }

  function isOpen() { const p = $('db-pop'); return !!p && !p.hidden; }

  // The buttons that open the picker say whether it's open.
  const expanded = on => document.querySelectorAll('[aria-controls="db-pop"]').forEach(b => b.setAttribute('aria-expanded', String(on)));

  // focus: true when a person opened it (keyboard focus moves in); the page opening it on load leaves focus alone.
  function open({ focus = true } = {}) {
    if (!$('db-pop')) return;
    $('db-pop').hidden = false;
    expanded(true);
    if (!st.rows && !st.loading) load(DEFAULT_PLACE);   // the first open, or again after a load that failed
    if (focus) $('pm-near').focus();
  }

  function close({ focus = true } = {}) {
    if (!isOpen()) return;
    $('db-pop').hidden = true;
    expanded(false);
    if (focus) $('db-pick').focus();
  }

  // Draw the top area (index.html #demo-top) and wire the picker: it opens under the top area, from its button.
  function mount(top, app) {
    st.app = app;
    let folded = false;
    try { folded = localStorage.getItem(FOLD_KEY) === 'folded'; } catch {}
    top.innerHTML = topHTML(app, { folded });
    top.classList.toggle('is-folded', folded);
    top.hidden = false;
    $('dt-fold').addEventListener('click', () => {
      folded = !folded;
      if (folded && isOpen()) close({ focus: false });
      top.classList.toggle('is-folded', folded);
      const b = $('dt-fold');
      b.setAttribute('aria-expanded', String(!folded));
      b.setAttribute('aria-label', folded ? "Show the demo's top area" : "Hide the demo's top area");
      b.innerHTML = foldLabel(folded);
      try { folded ? localStorage.setItem(FOLD_KEY, 'folded') : localStorage.removeItem(FOLD_KEY); } catch {}
    });
    $('db-pickwrap').insertAdjacentHTML('beforeend', panelHTML());
    $('db-pick').addEventListener('click', () => (isOpen() ? close() : open()));
    $('pm-close').addEventListener('click', () => close());
    $('pm-near').addEventListener('click', nearMe);
    $('pm-place').addEventListener('submit', e => { e.preventDefault(); findPlace($('pm-q').value); });
    $('pm-more').addEventListener('click', () => { st.all = true; draw(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && isOpen()) close(); });
    // a click outside closes it; a click on something the panel just redrew (Show N more) is no longer in the page, so it's inside
    document.addEventListener('click', e => { if (isOpen() && e.target.isConnected && !insidePicker(e.target)) close({ focus: false }); });
    // a monitor that can't be shown: say why at the top of the open picker
    if (app.public && app.public.error) { note('pm-error', app.public.error); open({ focus: false }); }
  }

  root.Picker = { ...api, mount, open, close };
})(typeof window !== 'undefined' ? window : globalThis);
