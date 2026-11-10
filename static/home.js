// Home Air Quality: the home's profiles and road in words, and compass bearings. app.js, sky.js and map.js use these; the home itself
// comes from the server as window.APP (config.public_view). Twin of config.bearing_in in Python: change both together.
(function (root) {
  // True if a compass bearing lies in the arc [lo, hi]; lo > hi means the arc crosses north.
  function bearingIn(deg, [lo, hi]) {
    const d = ((deg % 360) + 360) % 360;
    return lo <= hi ? d >= lo && d <= hi : d >= lo || d <= hi;
  }

  const POINTS = [['north', 0], ['north-east', 45], ['east', 90], ['south-east', 135], ['south', 180], ['south-west', 225], ['west', 270], ['north-west', 315]];
  const cw = (from, deg) => ((deg - from) % 360 + 360) % 360;   // degrees clockwise from `from` to `deg`
  // The eight compass points inside the arc, clockwise from its start; an arc too narrow for any gets the nearest one.
  function compassIn([lo, hi]) {
    const inside = POINTS.filter(([, d]) => bearingIn(d, [lo, hi])).sort((a, b) => cw(lo, a[1]) - cw(lo, b[1]));
    if (inside.length) return inside.map(([n]) => n);
    const mid = (lo + cw(lo, hi) / 2) % 360, off = d => Math.min(cw(mid, d), cw(d, mid));
    return [POINTS.reduce((a, b) => off(b[1]) < off(a[1]) ? b : a)[0]];
  }
  // The four main points outside the arc, clockwise from its end: where the wind carries the exhaust away.
  function compassAway([lo, hi]) {
    return POINTS.filter(([, d]) => d % 90 === 0 && !bearingIn(d, [lo, hi])).sort((a, b) => cw(hi, a[1]) - cw(hi, b[1])).map(([n]) => n);
  }
  const list = (xs, word) => xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} ${word} ${xs[xs.length - 1]}`;

  // 7, 10 → "7 to 10 AM"; 11, 13 → "11 AM to 1 PM"; sep "–" → "7–10 AM"
  function hourRange(a, b, sep = ' to ') {
    const h = x => (x % 24) % 12 || 12, m = x => (x % 24) < 12 ? 'AM' : 'PM';
    return m(a) === m(b) ? `${h(a)}${sep}${h(b)} ${m(b)}` : `${h(a)} ${m(a)}${sep}${h(b)} ${m(b)}`;
  }
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

  // "BQE expressway": the name alone means little outside the city
  function roadLabel(road) {
    return `${road.name} ${road.kind || 'highway'}`;
  }
  // "The BQE expressway runs about 1 km east to south of here"
  function roadRuns(road) {
    const pts = compassIn(road.toward), span = pts.length > 1 ? `${pts[0]} to ${pts[pts.length - 1]}` : pts[0];
    return `The ${roadLabel(road)} runs ${road.distance_km ? `about ${road.distance_km} km ` : ''}${span} of here`;
  }
  function roadClockText(road) {
    const rush = road.rush || [];
    if (!rush.length) return 'Traffic is only the clock: no rush hours are set, so it reads low all day.';
    return `Traffic is only the clock. Low most of the day, peak ${rush.map(([a, b]) => 'from ' + hourRange(a, b)).join(' and ')}, and a step higher in the hours next to those.`;
  }
  function roadWindText(road) {
    const away = compassAway(road.toward);
    return `Wind is Open-Meteo’s direction. ${roadRuns(road)}, so wind from the ${list(compassIn(road.toward), 'or')} blows its exhaust toward the block` +
      (away.length ? `, and wind from the ${list(away, 'or')} blows it away.` : '.');
  }
  function roadWhyText(road) {
    return `${roadRuns(road)}, so it matters on ${list(compassIn(road.toward), 'and')} winds.`;
  }

  // The summary's "For:" line: the household's profiles that are on, in the page's words ("" when none).
  function profilesFor(profiles) {
    const words = { toddler: 'toddler', sinus: 'sinus & allergy', runner: 'running' };
    return Object.keys(words).filter(k => profiles && profiles[k]).map(k => words[k]).join(', ');
  }

  // Sentences that name the home's region (config place.region) when it has one, else read neutrally.
  const smokeText = region => `Wildfire smoke over ${region || 'this area'}. When it is detected, outdoor PM2.5 is the risk.`;
  const smokeMapText = region => `NOAA Hazard Mapping: wildfire smoke over ${region || 'this area'}.`;
  const pollenBarsTitle = region => `Bars: the usual ${region ? region + ' ' : ''}season, peak in amber. Right: today's level from Google.`;

  // What each optional source adds, for its card and menu row when it's off (the page never mentions the config).
  const ADDS = {
    pollen: 'Adds daily pollen levels from Google.',
    smoke: 'Adds wildfire smoke from NOAA\u2019s satellite map.',
    nearby: 'Adds readings from public AirGradient monitors nearby.',
  };
  // A source that is off, or on but not set up: its card and status word, and one line on what it adds.
  // null when it is on and set up (its card then shows the reading, or an error). `pub`: a public monitor's page, where
  // pollen has no key, smoke is off outside North America and there is no road.
  // calendar: the card keeps its season calendar, greyed (pollen without a key).
  function sourceOff(id, state, pub = false) {
    if (id === 'pollen' && (state === 'not_set_up' || (state === 'off' && pub))) return { word: 'Off', line: 'Needs a Google Pollen key', calendar: true };
    if (id === 'smoke' && state === 'off' && pub) return { word: 'Off', line: 'NOAA\u2019s smoke map covers North America only.' };
    if (id === 'road' && state === 'off' && pub) return { word: 'Off', line: 'Not available for public monitors yet.' };
    if (state === 'off') return { word: 'Off', line: id === 'road' ? 'No road set up.' : ADDS[id] || '' };
    return null;
  }

  // The sources this home uses, by id: pollen and smoke follow the config, the road follows the road, the indoor monitor
  // whether the view has one (a public monitor's page doesn't).
  function sourcesOn(sources, hasRoad, hasIndoor = true) {
    const s = sources || {};
    return [...(hasIndoor ? ['one'] : []), 'openair', 'wx', ...(s.pollen !== false ? ['pollen'] : []), ...(s.smoke !== false ? ['smoke'] : []), ...(hasRoad ? ['bqe'] : [])];
  }

  // hasIndoor/hasOutdoor: the monitors the view has; pub: a public monitor's page ("this monitor"), by default one
  // without an indoor monitor, as before homes could have one monitor.
  function sourcesLabel(sources, hasRoad, hasIndoor = true, hasOutdoor = true, pub = !hasIndoor) {
    const s = sources || {};
    const names = ['weather', ...(s.pollen !== false ? ['pollen'] : []), ...(s.smoke !== false ? ['smoke'] : []), ...(hasRoad ? ['traffic'] : [])];
    const list = names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}` : names[0];
    const mine = pub ? 'this monitor' : hasIndoor && hasOutdoor ? 'your 2 monitors' : 'your monitor';
    return `Sources: ${mine}${names.length > 1 ? ', ' : ' and '}${list}. Open to see them.`;
  }

  // How fresh a monitor's latest reading is at `now`: Online up to 10 min, Late up to an hour, then Offline.
  // absent: the view has no such monitor (a public monitor's page has no indoor one): disabled, "Not set up", never red.
  function freshness(m, now, absent = false) {
    if (absent) return { tone: 'off', label: 'Not set up' };
    if (!m || !m.timestamp) return { tone: 'bad', label: 'Offline' };
    const mins = Math.round((now - new Date(m.timestamp)) / 60000);
    if (mins <= 10) return { tone: 'good', label: 'Online' };
    if (mins <= 60) return { tone: 'warn', label: `Late · ${mins} min` };
    return { tone: 'bad', label: 'Offline' };
  }

  // The Home pill's two monitor pictures, each with its freshness dot. `place` is APP.place (indoor null: the view has
  // no indoor monitor, drawn disabled); `icons` the pictures by id ('one', 'openair'). An indoor-only home (outdoor null)
  // greys the outdoor picture too and names where its outdoor PM2.5 comes from (`outWords`, sourceLine's menu words).
  function monitorPill(place, indoor, outdoor, now, icons, outWords) {
    const noOut = place.outdoor === null;
    // an indoor-only home's outdoor slot is its source: live when a chosen public monitor reports, greyed for an estimate
    return [['one', 'Indoor · AirGradient ONE', indoor, place.indoor === null], ['openair', noOut ? 'Outdoor PM2.5' : 'Outdoor · AirGradient Open Air', outdoor, noOut && !(outdoor && outdoor.timestamp)]]
      .map(([id, name, m, absent]) => { const f = freshness(m, now, absent), label = id === 'openair' && noOut && outWords ? outWords : f.label;
        return `<span class="vhw${f.tone === 'off' ? ' off' : ''}" data-tip="${name}: ${label}">${(icons && icons[id]) || ''}<i class="${f.tone}"></i></span>`; }).join('');
  }

  // How many of the view's monitors are live, in words and as a tone for the avatar's dot: "2 monitors live" (good),
  // "1 of 2 monitors live" (warn), "1 monitor, not live" (bad). A disabled monitor (tone off) isn't counted.
  function monitorsLive(states) {
    const have = states.filter(f => f.tone !== 'off'), ok = have.filter(f => f.tone === 'good').length, n = have.length;
    const tone = ok === n ? 'good' : ok ? 'warn' : 'bad';
    if (ok === n) return { text: `${n} monitor${n === 1 ? '' : 's'} live`, tone };
    return { text: n === 1 ? '1 monitor, not live' : `${ok} of ${n} monitors live`, tone };
  }

  // A monitor's row in the open Home menu: its status words and tooltip, and whether the row is greyed (`off`: the view
  // has no such monitor). `tz` is the home's timezone for the tooltip's time.
  function monitorRow(m, now, absent, tz) {
    const f = freshness(m, now, absent);
    if (f.tone === 'off') return { tone: 'off', text: f.label, title: f.label, off: true };
    const mins = m && m.timestamp ? Math.max(0, Math.round((now - new Date(m.timestamp)) / 60000)) : null;
    const text = f.tone === 'good' ? `Live · ${mins < 1 ? 'just now' : mins + ' min ago'}` : f.label;
    const title = m && m.timestamp ? 'Last reading ' + new Date(m.timestamp).toLocaleString('en-US', { timeZone: tz, hour: 'numeric', minute: '2-digit', month: 'short', day: 'numeric' }) : 'No reading';
    return { tone: f.tone, text, title, off: false };
  }

  // ── A home with one monitor ──
  const NO_OUT_YET = 'No outdoor reading yet';   // an indoor-only home's outdoor card before its source arrives
  const NB_USED = 'used for your outdoor PM2.5';   // the tag on the public monitor an indoor-only home reads
  const ESTIMATE_NOW_MIN = 90;   // minutes: how old the summary's last model hour may be and still read as now (the model is hourly)
  const NEEDS_INDOOR = 'Needs an indoor monitor';   // the summary's state for Toddler on an outdoor-only home (summary.py)

  // "2", "1.1": a distance in km with at most one decimal and no trailing ".0", as the summary's sentences print it.
  const kmText = d => String(Math.round(d * 10) / 10);

  // Where an indoor-only home's outdoor PM2.5 comes from, in the page's words: `source` is /api/current's outdoor entry's
  // "source" ({kind: monitor|area|model, name, distance_km, area_count, fallback}). name/sub: the outdoor card's name line;
  // menu: the Home menu's words; estimate: the card shows an estimate, not a monitor's readings; down: the card's status
  // when the chosen monitor's reading isn't used (fallback: kind is then the estimate, name and distance still the
  // monitor's): "monitor" (or true), it isn't reporting; "list", AirGradient didn't answer, so the monitor isn't blamed.
  // Plain text: the public monitor's name is its owner's, so whoever puts it in HTML escapes it. null without a source.
  function sourceLine(source) {
    if (!source || !source.kind) return null;
    const name = typeof source.name === 'string' ? source.name.trim() : '';
    const d = typeof source.distance_km === 'number' && Number.isFinite(source.distance_km) ? `${kmText(source.distance_km)} km` : '';
    const chosen = ['Nearby public monitor', d].filter(Boolean).join(', ');
    if (source.kind === 'monitor' && !source.fallback) return { name: 'Nearby public monitor', sub: [name, d].filter(Boolean).join(', '), menu: chosen, estimate: false, down: null };
    const n = source.area_count;
    return {
      name: source.kind === 'model' ? 'Estimate for your area (Open‑Meteo)' : 'Estimate for your area',   // a non-breaking hyphen: one word on a phone
      sub: source.kind === 'area' && n > 0 ? `from ${n} public monitor${n === 1 ? '' : 's'}` : '',
      menu: source.fallback ? chosen : 'Estimate for your area', estimate: true,
      down: source.fallback === 'list' ? "AirGradient didn't answer · showing an estimate for your area"
        : source.fallback ? `${name || 'The nearby public monitor'} isn't reporting · showing an estimate for your area` : null,
    };
  }

  // The source's status on the outdoor card (`card`, like freshness()) and in the Home menu (`row`, like monitorRow()):
  // a public monitor's freshness; an estimate in grey ("Estimate"); a chosen monitor that isn't reporting (or AirGradient
  // not answering for it) in amber, never red.
  // No source entry (/api/current didn't send one): grey, "No outdoor reading yet", never red.
  function sourceStatus(source, m, now, tz) {
    if (!source) return { card: { tone: 'off', label: NO_OUT_YET }, row: { tone: 'neutral', text: 'No reading yet', title: NO_OUT_YET, off: false } };
    const w = sourceLine(source);
    if (w && w.down) return { card: { tone: 'warn', label: w.down }, row: { tone: 'warn', text: source.fallback === 'list' ? 'No answer' : 'Not reporting', title: w.down, off: false } };
    if (w && w.estimate) return { card: { tone: 'neutral', label: 'Estimate' }, row: { tone: 'neutral', text: 'Estimate', title: w.name, off: false } };
    return { card: freshness(m, now), row: monitorRow(m, now, false, tz) };
  }

  // A monitor's History request, or null for an outdoor entry with no history of its own (an estimate has no locationId).
  function histUrl(m, from, to) {
    if (!m || m.locationId === null || m.locationId === undefined) return null;
    return `/api/history/${m.locationId}?from=${from.toISOString()}&to=${to.toISOString()}`;
  }

  // An estimate's PM2.5 now: the summary's last model hour (its day chart's past, `tl` = summary.timeline) when it is
  // this hour's, as {pm, at: that hour}; null otherwise (the card then shows "—"). The page never makes up a number.
  function estimateNow(tl, now) {
    const past = tl && tl.pm && tl.pm.source === 'model' && Array.isArray(tl.pm.past) ? tl.pm.past : [];
    const last = past[past.length - 1];
    if (!last) return null;
    const mins = (now - Date.parse(last[0])) / 60000;
    return mins >= 0 && mins <= ESTIMATE_NOW_MIN && typeof last[1] === 'number' ? { pm: last[1], at: last[0] } : null;
  }

  // The one line under an estimate's card: what it covers, so the greyed rows read as expected (rule 11).
  const estimateNote = weather => 'The estimate covers PM2.5 only.' + (weather ? ' Temperature and humidity are Open‑Meteo’s weather.' : '');

  // The page's two entries from /api/current: the home's indoor and outdoor ones. A view without an indoor monitor takes
  // none (whatever the token sees); an indoor-only home takes the source entry the server added, not a monitor's row.
  function pickEntries(current, noIndoor, noOutdoor) {
    const rows = Array.isArray(current) ? current : [];
    return { indoor: noIndoor ? null : rows.find(m => m && m.locationType === 'indoor') || null,
      outdoor: (noOutdoor ? rows.find(m => m && m.source) : rows.find(m => m && m.locationType === 'outdoor')) || null };
  }

  // Whether a Home menu row is greyed: a monitor the view doesn't have (tone off), or a source that is off or not set up.
  function rowOff(tone, text) {
    return tone === 'off' || (tone === 'neutral' && /^(Off|Not set up)$/.test(text));
  }

  // The neighborhood's rows: `you` is the home's own outdoor monitor (its ids in `ownIds`; an indoor-only home has none,
  // so no You row), `others` the rest. The public monitor an indoor-only home uses (`usedId`) stays among the others,
  // marked `used` so its row and its map label say so.
  function nbSplit(live, ownIds, usedId) {
    const own = new Set((ownIds || []).filter(id => id !== null && id !== undefined));
    return { you: live.find(n => own.has(n.locationId)) || null,
      others: live.filter(n => !own.has(n.locationId)).map(n => usedId !== null && usedId !== undefined && n.locationId === usedId ? { ...n, used: true } : n) };
  }

  // A profile the home picked that can't work with its monitors: its reason (the Home menu's tip), else null.
  function profileOff(id, hasIndoor) {
    return id === 'toddler' && !hasIndoor ? NEEDS_INDOOR : null;
  }

  // The greyed indoor card's status line and label: a home without an indoor monitor, or a public monitor's page.
  function ghostWords(pub) {
    return pub ? { status: 'Public monitors are outdoor only', aria: 'Indoor: none, this is a public outdoor monitor' }
      : { status: 'Not set up', aria: 'Indoor: no indoor monitor' };
  }

  // A link from AirGradient's data, made safe to put in an href: https:// added when it has no scheme; '' unless http(s).
  function safeUrl(raw) {
    let url = raw ? String(raw).trim() : '';
    if (url && !/^[a-z][a-z0-9+.-]*:/i.test(url)) url = 'https://' + url.replace(/^\/\//, '');
    return /^https?:\/\/[^\s"'<>]+$/i.test(url) ? url : '';
  }

  // The credit AirGradient's public data (CC-BY-SA 4.0) asks for, under the neighborhood table. Each monitor's owner
  // is named in its open row (nbDetailHTML). The demo's monitors are made up.
  function creditHtml(isDemo) {
    if (isDemo) return 'Made-up monitors for the demo';
    const a = (href, text) => `<a href="${href}" target="_blank" rel="noopener">${text}</a>`;
    return `Data provided by ${a('https://www.airgradient.com', 'AirGradient')} · Licensed under ${a('https://creativecommons.org/licenses/by-sa/4.0/', 'CC-BY-SA 4.0')}`;
  }

  // ── A public monitor's page (the demo's ?monitor=<id>) ──
  const MAP_PAGE = 'https://www.airgradient.com/map/';
  const icon = d => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;

  // The monitor card's last line: its owner (linked to their page when they have one), the map, the licence (CC BY-SA).
  function monitorCredit(pub, esc) {
    const name = pub && typeof pub.contributor === 'string' ? pub.contributor.trim() : '', url = safeUrl(pub && pub.url);
    const who = !name ? '' : url ? `<a href="${esc(url)}" target="_blank" rel="noopener"><b>${esc(name)}</b></a>` : `<b>${esc(name)}</b>`;
    return `Shared ${who ? `by ${who} ` : ''}on <a href="${MAP_PAGE}" target="_blank" rel="noopener">AirGradient's public map</a> · CC BY-SA`;
  }

  // The indoor monitor's slot when the view has none: what would go there, and how to get it.

  // History for a public monitor that AirGradient's map has no past readings for: one line instead of empty charts.
  function noHistoryHTML() {
    return `<span class="mc-ph-ic">${icon('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>')}</span>` +
      `<div><b>No past readings for this monitor</b><span>AirGradient's map has none for it right now. Today's forecast is in the summary.</span></div>`;
  }

  // The neighborhood's words for the monitor the page shows: "This" on a public monitor's page, "You" at home.
  function selfWords(pub) {
    return pub ? { row: 'This', map: 'This monitor', legend: 'This monitor', block: 'this monitor', near: 'this monitor' }
      : { row: 'You', map: 'You', legend: 'Your monitor', block: 'your block', near: 'home' };
  }

  // A neighbor's PM2.5: AirGradient's corrected reading (the server adds it, server._fetch_nearby), else the raw one.
  // The same basis as the home's own monitors (app.js reads pm02_corrected first), so the table compares like with like.
  function nbPm(n) {
    const has = v => v !== null && v !== undefined && !Number.isNaN(v);
    return n && has(n.pm02_corrected) ? n.pm02_corrected : n && has(n.pm02) ? n.pm02 : null;
  }

  // The shown monitor's row reads what its card reads: when it is the view's outdoor monitor, the card's PM2.5 (`cardPm`,
  // app.js reading()), so the row, the lead and the map label match the card. Any other row comes back as it came.
  function nbYou(you, outdoor, cardPm) {
    return you && outdoor && you.locationId === outdoor.locationId ? { ...you, pm02_corrected: cardPm } : you;
  }

  // The neighborhood's lead: said only when the comparison changes a decision ('' otherwise). `you` is the shown
  // monitor's row (or null), `others` the nearby ones, `limit` the PM2.5 limit, `self` selfWords(), f.esc/pm/num formatters.
  function nbLead(you, others, limit, self, f) {
    const vals = others.map(nbPm).sort((x, y) => x - y);
    const median = vals.length ? vals[Math.floor(vals.length / 2)] : null;
    const over = others.filter(n => pmOver(nbPm(n), limit)).sort((x, y) => x.distance_km - y.distance_km);
    const mine = you ? nbPm(you) : null;
    if (median != null && pmOver(median, limit)) {
      return `<b class="warn">The whole area is elevated</b> (typical nearby reading ${f.num(median)} µg/m³). That points to something regional, such as wildfire smoke, not a source near ${self.near}.`;
    }
    if (you && median != null && pmOver(mine, limit) && mine > median * 2) {
      return `<b class="warn">${cap(self.block)} reads well above the area</b> (${f.pm(mine)} against a typical ${f.pm(median)}). That points to a source close to ${self.near}: traffic, construction, or a neighbor's smoke.`;
    }
    if (over.length) {
      const n0 = over[0];
      return `<b class="warn">${over.length === 1 ? 'One nearby monitor is' : over.length + ' nearby monitors are'} over the ${limit} µg/m³ limit</b>: the nearest is ${f.esc(n0.locationName)}, ${f.pm(n0.distance_km)} km away.${you && mine <= limit ? ` ${cap(self.block)} is still clean.` : ''}`;
    }
    return '';
  }

  const NB_RADIUS_KM = 15;   // how far the public monitors are listed (the server's nearby radius)
  // The table's "Show more" button, collapsed: how many more rows, and how many public monitors there are in all.
  function nbMoreText(extra, total) {
    return `Show ${extra} more of ${total} within ${NB_RADIUS_KM} km`;
  }
  // Without a "Show more" button (8 monitors or fewer), the count goes in front of the credit line under the table
  function nbCountText(total) {
    return total > 0 ? `${total} public monitor${total === 1 ? '' : 's'} within ${NB_RADIUS_KM} km` : '';
  }

  const NB_COLS = 8;   // the neighborhood table's columns (dot, dist, location, PM2.5, temp, humidity, bar, toggle): the open band spans them
  const MIN_PER_H = 60;   // minutes in an hour: a last reading over an hour old reads "1 h 25 min ago"
  const ARROW = icon('<path d="M7 17 17 7"/><path d="M8 7h9v9"/>'), CHEVRON = icon('<path d="m6 9 6 6 6-6"/>');

  // One neighborhood row. `isYou`: the shown monitor's own row (named `name`, labelled self.row); `scale` has the
  // PM2.5 limit, the bar's full scale (barMax) and the limit's place on it (limPct); f.esc/pm/num/temp format values.
  // A real monitor (one with the server's map_url) gets a small link to it on AirGradient's map, and a chevron that opens
  // it in place (`open`: the band follows the row, nbDetailHTML). The shown monitor and the demo's made-up ones don't open.
  function nbRowHTML(n, isYou, self, name, scale, f, open = false) {
    const pm = nbPm(n);
    const tone = pmOver(pm, scale.limit) ? 'warn' : 'good';
    const has = v => v !== null && v !== undefined && !Number.isNaN(v);
    const url = safeUrl(n.map_url), can = !isYou && !!url;
    const ext = url ? ` <a class="nb-ext" href="${f.esc(url)}" target="_blank" rel="noopener" title="Open on AirGradient's map" aria-label="Open ${f.esc(n.locationName)} on AirGradient's map">${ARROW}</a>` : '';
    const cls = [isYou ? 'you' : '', can ? 'nb-can' : '', can && open ? 'nb-open' : ''].filter(Boolean).join(' ');
    const toggle = can ? `<button type="button" class="nb-tgb" aria-expanded="${!!open}" aria-controls="${nbDetailId(n)}" aria-label="Details: ${f.esc(n.locationName)}">${CHEVRON}</button>` : '';
    return `<tr class="${cls}" data-id="${Number(n.locationId)}"><td class="dot"><i></i></td><td class="dist">${isYou ? self.row : f.num(n.distance_km) + ' km'}</td>` +
      `<td class="loc" title="${f.esc(n.locationName)}">${f.esc(isYou ? name : n.locationName)}${n.used ? `<span class="nb-used"> · ${NB_USED}</span>` : ''}${ext}</td>` +
      `<td class="r pm ${tone}">${f.pm(pm)}</td><td class="r">${has(n.atmp) ? f.temp(n.atmp) : '—'}</td><td class="r">${has(n.rhum) ? Math.round(n.rhum) + '%' : '—'}</td>` +
      `<td class="nbbar"><span style="--lim:${scale.limPct}%"><i style="width:${Math.max(1.5, pm / scale.barMax * 100).toFixed(1)}%" class="${tone}"></i></span></td>` +
      `<td class="nb-tg">${toggle}</td></tr>` + (can && open ? nbDetailHTML(n, scale, f) : '');
  }

  // The open band's id, which its row's toggle names in aria-controls. locationId is AirGradient's number.
  const nbDetailId = n => `nbd-${Number(n.locationId)}`;

  // An open neighbor row's band. On a phone: PM2.5 now with its word, humidity and temperature (the columns a phone
  // hides), the owner and the last reading, then the action full width. On a wide screen (app.css) one line: the word,
  // the owner, the last reading, the action at the right. One action: the monitor on AirGradient's map.
  // `scale.limit`/`scale.high` are the home's PM2.5 limits; f.when(timestamp) is lastReadingText at the page's clock.
  function nbDetailHTML(n, scale, f) {
    const has = v => v !== null && v !== undefined && !Number.isNaN(v);
    const pm = nbPm(n), lvl = pmLevel(pm, { pm: scale.limit, pm_high: scale.high });
    const owner = typeof n.publicContributorName === 'string' ? n.publicContributorName.trim() : '';
    const when = f.when ? f.when(n.timestamp) : '';
    const meta = [owner && `Shared by ${f.esc(owner)}`, when && `${owner ? 'last' : 'Last'} reading ${f.esc(when)}`].filter(Boolean).join(' · ');
    return `<tr class="nb-detail" id="${nbDetailId(n)}"><td colspan="${NB_COLS}"><div class="nbd">` +
      `<dl class="nbd-kv"><div><dt>PM2.5 now</dt><dd class="${lvl.tone}">${f.pm(pm)} <small>µg/m³</small> · ${lvl.word}</dd></div>` +
      `<div><dt>Humidity</dt><dd>${has(n.rhum) ? Math.round(n.rhum) + '%' : '—'}</dd></div>` +
      `<div><dt>Temperature</dt><dd>${has(n.atmp) ? f.temp(n.atmp) : '—'}</dd></div></dl>` +
      `<p class="nbd-meta"><b class="nbd-band ${lvl.tone}">${lvl.word}</b>${meta ? `<span class="nbd-sep"> · </span>${meta}` : ''}</p>` +
      `<a class="nbd-q" href="${f.esc(safeUrl(n.map_url))}" target="_blank" rel="noopener">${ARROW}Open on AirGradient's map</a></div></td></tr>`;
  }

  // A neighbor's last reading for its open row: "7:38 AM, 7 min ago" in the home's timezone `tz`, at `now`. '' without one.
  function lastReadingText(ts, now, tz) {
    const t = ts ? new Date(ts) : null;
    if (!t || Number.isNaN(t.getTime())) return '';
    const mins = Math.max(0, Math.round((now - t) / 60000)), h = Math.floor(mins / MIN_PER_H), m = mins % MIN_PER_H;
    const ago = mins < 1 ? 'just now' : !h ? `${mins} min ago` : m ? `${h} h ${m} min ago` : `${h} h ago`;
    return `${t.toLocaleTimeString('en-US', { timeZone: tz, hour: 'numeric', minute: '2-digit' })}, ${ago}`;
  }

  // The pollen card's season calendar: the home's usual seasons (config dates, [month, day]) across the year, today's
  // mark, today's level per type from Google (`levels`; "—" without one) and a line on what's in season and what's next.
  // `now` is the home's local date and time. '' when there are no seasons.
  function pollenSeasonHTML(seasons, levels, now, limits, region, esc) {
    if (!seasons || !seasons.length) return '';
    const y = now.getFullYear();
    const doy = d => Math.round((d - new Date(y, 0, 1)) / 864e5), at = ([m, dd], yr = y) => new Date(yr, m - 1, dd);
    const today = doy(now), pct = n => (n / 365 * 100).toFixed(2);
    const fmt = d => { const m = d.toLocaleDateString('en-US', { month: 'long' }), n = d.getDate(); return n <= 10 ? `early ${m}` : n <= 20 ? `mid-${m}` : `late ${m}`; };
    const active = seasons.filter(p => now >= at(p.start) && now <= at(p.end));
    // the next season to start (this year or next)
    const next = seasons.map(p => { const st = at(p.start), s2 = st > now ? st : at(p.start, y + 1); return { ...p, when: s2 }; }).sort((a, b) => a.when - b.when)[0];
    const weeks = Math.round((next.when - now) / 6048e5), months = Math.round((next.when - now) / (30.4 * 864e5));
    const inTime = weeks <= 6 ? `in about ${weeks} week${weeks === 1 ? '' : 's'}` : `in about ${months} months`;
    let line;
    if (active.length) {
      const p = active[0], inPeak = now >= at(p.peak[0]) && now <= at(p.peak[1]);
      line = `<b>Now: ${p.name.toLowerCase()} season</b>${inPeak ? ', at its peak' : now < at(p.peak[0]) ? `, peaks in ${at(p.peak[0]).toLocaleDateString('en-US', { month: 'long' })}` : ', easing off'}, until ${fmt(at(p.end))}. Next: ${next.name.toLowerCase()} from ${fmt(next.when)}.`;
    } else line = `<b>Next: ${next.name.toLowerCase()} pollen</b>, usually from ${fmt(next.when)} (${inTime}).`;
    const lvl = i => ['None', 'Very low', 'Low', 'Moderate', 'High', 'Very high'][i] || '—';
    const level = name => { const t = (levels || []).find(x => x.name === name), i = t ? (t.index || 0) : null; return i == null ? '—' : `<b class="${pollenHigh(i, limits) ? 'warn' : i ? 'good' : ''}">${lvl(i)}</b>`; };
    return `<div class="ps-grid" title="${esc(pollenBarsTitle(region))}">${seasons.map(p => `<div class="ps-row"><span>${p.name}</span><div class="ps-track">
      <i class="ps-season" style="left:${pct(doy(at(p.start)))}%;width:${pct(doy(at(p.end)) - doy(at(p.start)))}%"></i>
      <i class="ps-peak" style="left:${pct(doy(at(p.peak[0])))}%;width:${pct(doy(at(p.peak[1])) - doy(at(p.peak[0])))}%"></i></div>${level(p.name)}</div>`).join('')}
      <div class="ps-row ps-months"><span></span><div class="ps-track">${[0, 3, 6, 9].map(i => `<em style="left:${pct(doy(new Date(y, i, 1)))}%">${new Date(y, i, 1).toLocaleDateString('en-US', { month: 'short' })}</em>`).join('')}</div><span></span></div>
      <div class="ps-today" style="--x:${pct(today)}" title="Today"></div></div>
    <p class="ps-line">${line}</p>`;
  }

  // Whether a pollen level (0 to 5) reaches the home's pollen limit (APP.limits.pollen, [limits] pollen in the config).
  function pollenHigh(index, limits) {
    return index != null && index >= limits.pollen;
  }

  // PM2.5 against a limit as the server does it (summary.py: round(v) > limit): the page shows the reading rounded,
  // so 15.3 reads "15", which isn't over 15.
  function pmOver(v, limit) {
    return Math.round(v) > limit;
  }

  const PM_AQI_UNHEALTHY = 55.4;   // µg/m³: top of the US AQI band "Unhealthy for sensitive groups"; a display scale, not a limit
  // The outdoor card's word for a PM2.5 reading: the home's limits (APP.limits pm and pm_high), then the AQI band.
  function pmLevel(pm, limits) {
    if (pm == null || Number.isNaN(pm)) return { word: 'No reading', tone: 'muted' };
    if (!pmOver(pm, limits.pm)) return { word: 'Good', tone: 'good' };
    if (!pmOver(pm, limits.pm_high)) return { word: 'Moderate', tone: 'warn' };
    if (!pmOver(pm, PM_AQI_UNHEALTHY)) return { word: 'Unhealthy for sensitive groups', tone: 'warn' };
    return { word: 'Unhealthy', tone: 'bad' };
  }

  const api = { nbCountText, MAP_PAGE, NB_USED, NO_OUT_YET, pickEntries, rowOff, nbSplit, sourceLine, sourceStatus, histUrl, estimateNow, estimateNote, profileOff, ghostWords, pmOver, pmLevel, pollenHigh, creditHtml, freshness, monitorPill, monitorsLive, monitorRow, safeUrl, monitorCredit, noHistoryHTML, selfWords, nbPm, nbYou, nbLead, nbMoreText, nbRowHTML, nbDetailHTML, lastReadingText, pollenSeasonHTML, sourceOff, sourcesOn, sourcesLabel, smokeText, smokeMapText, pollenBarsTitle, profilesFor, bearingIn, compassIn, compassAway, hourRange, cap, roadClockText, roadWindText, roadWhyText, roadLabel };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }
  Object.assign(root, api);
})(typeof window !== 'undefined' ? window : globalThis);
