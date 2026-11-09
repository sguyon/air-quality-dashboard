// Home Air Quality: the home's needs and road in words, and compass bearings. app.js, sky.js and map.js use these; the home itself
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

  // The summary's "For:" line: the household's needs that are on, in the page's words ("" when none).
  function needsFor(needs) {
    const words = { toddler: 'toddler', sinus: 'sinus & allergy', runner: 'running' };
    return Object.keys(words).filter(k => needs && needs[k]).map(k => words[k]).join(', ');
  }

  // Sentences that name the home's region (config place.region) when it has one, else read neutrally.
  const smokeText = region => `Wildfire smoke over ${region || 'this area'}. When it is detected, outdoor PM2.5 is the risk.`;
  const smokeMapText = region => `NOAA Hazard Mapping: wildfire smoke over ${region || 'this area'}.`;
  const pollenBarsTitle = region => `Bars: the usual ${region ? region + ' ' : ''}season, peak in amber. Right: today's level from Google.`;

  // A source that is off in the config, or on but not set up: its card and status word, and one line on what it adds.
  // null when it is on and set up (its card then shows the reading, or an error).
  function sourceOff(id, state) {
    if (state === 'not_set_up' && id === 'pollen') return { word: 'Not set up', line: 'Add a Google Pollen key to see daily pollen.' };
    if (state === 'off') return { word: 'Off', line: id === 'road' ? 'No road set up.' : 'Turned off in the config.' };
    return null;
  }

  // The sources this home uses, by id: pollen and smoke follow the config, the road follows the road.
  function sourcesOn(sources, hasRoad) {
    const s = sources || {};
    return ['one', 'openair', 'wx', ...(s.pollen !== false ? ['pollen'] : []), ...(s.smoke !== false ? ['smoke'] : []), ...(hasRoad ? ['bqe'] : [])];
  }

  function sourcesLabel(sources, hasRoad) {
    const s = sources || {};
    const names = ['weather', ...(s.pollen !== false ? ['pollen'] : []), ...(s.smoke !== false ? ['smoke'] : []), ...(hasRoad ? ['traffic'] : [])];
    const list = names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}` : names[0];
    return `Sources: your 2 monitors${names.length > 1 ? ', ' : ' and '}${list}. Open to see them.`;
  }

  // How fresh a monitor's latest reading is at `now`: Online up to 10 min, Late up to an hour, then Offline.
  function freshness(m, now) {
    if (!m || !m.timestamp) return { tone: 'bad', label: 'Offline' };
    const mins = Math.round((now - new Date(m.timestamp)) / 60000);
    if (mins <= 10) return { tone: 'good', label: 'Online' };
    if (mins <= 60) return { tone: 'warn', label: `Late · ${mins} min` };
    return { tone: 'bad', label: 'Offline' };
  }

  // The credit AirGradient's public data (CC-BY-SA 4.0) asks for, under the neighborhood table.
  // `neighbors` are the public monitors shown; `esc` escapes every value from the API. The demo's monitors are made up.
  function creditHtml(neighbors, isDemo, esc) {
    if (isDemo) return 'Made-up monitors for the demo';
    const a = (href, text) => `<a href="${href}" target="_blank" rel="noopener">${text}</a>`;
    const seen = new Map();
    for (const n of neighbors || []) {
      const name = n && typeof n.publicContributorName === 'string' ? n.publicContributorName.trim() : '';
      if (!name) continue;
      let url = n.publicPlaceUrl ? String(n.publicPlaceUrl).trim() : '';
      if (url && !/^[a-z][a-z0-9+.-]*:/i.test(url)) url = 'https://' + url.replace(/^\/\//, '');
      if (!/^https?:\/\/[^\s"'<>]+$/i.test(url)) url = '';
      if (!seen.has(name) || (!seen.get(name) && url)) seen.set(name, url);
    }
    const who = [...seen].map(([name, url]) => url ? a(esc(url), esc(name)) : esc(name));
    return `Data provided by ${a('https://www.airgradient.com', 'AirGradient')} · Licensed under ${a('https://creativecommons.org/licenses/by-sa/4.0/', 'CC-BY-SA 4.0')}` +
      (who.length ? ` · Contributors: ${who.join(', ')}` : '');
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

  const api = { pmOver, pmLevel, pollenHigh, creditHtml, freshness, sourceOff, sourcesOn, sourcesLabel, smokeText, smokeMapText, pollenBarsTitle, needsFor, bearingIn, compassIn, compassAway, hourRange, cap, roadClockText, roadWindText, roadWhyText, roadLabel };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }
  Object.assign(root, api);
})(typeof window !== 'undefined' ? window : globalThis);
