// Home Air Quality: the Neighborhood map. Loaded only when the section nears the screen.
// MapLibre (open source) draws OpenFreeMap tiles: free, no key. The road's path is the config's route file (/api/road/route),
// from OpenStreetMap routing. Without a road: no route, no plume.
// Uses $, APP, apiUrl, state, has, PM_FINE, TZ and the table rows (data-id) from app.js, and bearingIn, selfWords and nbPm from home.js.
var NBMAP = (() => {
  const MAPLIBRE = 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min';
  const STYLE = { light: 'https://tiles.openfreemap.org/styles/positron', dark: 'https://tiles.openfreemap.org/styles/dark' };
  // the first view: the nearest FIT_NEAREST neighbors in view (the server sends them nearest first), FIT_PAD px inside
  // the map's edge, never wider than FIT_MIN_ZOOM (about the 15 km radius the server searches) and never closer than
  // the neighborhood scale the map always opened at (ZOOM_PHONE under 600 px wide, ZOOM_WIDE above)
  const FIT_NEAREST = 6, FIT_PAD = 40, FIT_MIN_ZOOM = 10.5;
  const ZOOM_PHONE = 12.1, ZOOM_WIDE = 12.7, PHONE_PX = 600;
  // the shown monitor's label: "You", or "This monitor" on a public monitor's page (not on an unknown monitor's, {id, error},
  // which shows the default sample instead)
  const YOU = selfWords(!!(APP.public && !APP.public.error)).map;
  const ROAD = APP.road;   // its toward arc: wind from these directions carries the road's exhaust toward home (same as server.py)
  const toward = () => !!ROAD && data.wind != null && bearingIn(data.wind, ROAD.toward);
  let map = null, bqe = null, data = null, hoverId = null, loading = null;
  const fc = f => ({ type: 'FeatureCollection', features: f });
  const pmLabel = v => (Math.round(v * 10) / 10 >= 10 ? String(Math.round(v)) : v.toFixed(1));   // as the table writes it (app.js pmNum)
  // the nearby monitors' dots, on the corrected PM2.5 like the table (nbPm, home.js)
  const monitors = () => fc(data.others.map(n => ({ type: 'Feature', id: n.id, properties: { pm: nbPm(n), label: pmLabel(nbPm(n)) }, geometry: { type: 'Point', coordinates: [n.longitude, n.latitude] } })));
  const theme = () => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';

  function load() {
    if (loading) return loading;
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = MAPLIBRE + '.css'; document.head.appendChild(css);
    loading = Promise.all([
      new Promise((ok, no) => { const s = document.createElement('script'); s.src = MAPLIBRE + '.js'; s.onload = ok; s.onerror = no; document.head.appendChild(s); }),
      ROAD ? fetch(apiUrl('/api/road/route')).then(r => r.json()).then(j => { bqe = Array.isArray(j) ? j : null; }) : null,
    ]);
    return loading;
  }

  function plume(deg) {
    if (deg == null || !bqe) return fc([]);
    // degrees per km: a degree of longitude shrinks with the home's latitude
    const to = (deg + 180) * Math.PI / 180, kLat = 1 / 111.1, kLon = 1 / (111.1 * Math.cos(APP.place.lat * Math.PI / 180));
    return fc([[0.6, .22], [1.2, .14], [1.9, .08]].map(([d, op]) => {
      const moved = bqe.map(([lo, la]) => [lo + Math.sin(to) * d * kLon, la + Math.cos(to) * d * kLat]);
      return { type: 'Feature', properties: { op }, geometry: { type: 'Polygon', coordinates: [[...bqe, ...moved.reverse(), bqe[0]]] } };
    }));
  }

  function addLayers() {
    const dark = theme() === 'dark', ink = dark ? '#ececef' : '#18181b', halo = dark ? '#17181c' : '#ffffff';
    if (bqe) {   // the road and its plume, when the home has one
      map.addSource('plume', { type: 'geojson', data: plume(data.wind) });
      map.addLayer({ id: 'plume', type: 'fill', source: 'plume', paint: { 'fill-color': '#f59e0b', 'fill-opacity': ['*', ['get', 'op'], toward() ? 1.15 : .75] } });
      map.addSource('bqe', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: bqe } } });
      map.addLayer({ id: 'bqe-case', type: 'line', source: 'bqe', paint: { 'line-color': halo, 'line-width': 8 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      map.addLayer({ id: 'bqe', type: 'line', source: 'bqe', paint: { 'line-color': dark ? '#a1a1aa' : '#71717a', 'line-width': 4 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      map.addLayer({ id: 'bqe-label', type: 'symbol', source: 'bqe', layout: { 'symbol-placement': 'line', 'text-field': ROAD.name, 'text-size': 11, 'text-font': ['Noto Sans Bold'], 'symbol-spacing': 500 },
        paint: { 'text-color': dark ? '#d4d4d8' : '#52525b', 'text-halo-color': halo, 'text-halo-width': 2 } });
    }
    map.addSource('mons', { type: 'geojson', data: monitors() });
    map.addLayer({ id: 'mons', type: 'circle', source: 'mons', paint: {
      'circle-radius': ['+', 6, ['min', 10, ['*', ['get', 'pm'], .9]]],
      // over the limit as the server counts it: the rounded reading (home.js pmOver)
      'circle-color': ['case', ['>', ['round', ['get', 'pm']], PM_FINE], '#f59e0b', '#22a55a'], 'circle-opacity': .9,
      'circle-stroke-color': ['case', ['boolean', ['feature-state', 'hl'], false], ink, halo],
      'circle-stroke-width': ['case', ['boolean', ['feature-state', 'hl'], false], 3, 2] } });
    map.addLayer({ id: 'mons-label', type: 'symbol', source: 'mons', layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-font': ['Noto Sans Bold'], 'text-offset': [0, -1.6], 'text-allow-overlap': true },
      paint: { 'text-color': ink, 'text-halo-color': halo, 'text-halo-width': 2 } });
    if (data.you) {
      map.addSource('you', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [data.you.longitude, data.you.latitude] } } });
      map.addLayer({ id: 'you', type: 'circle', source: 'you', paint: { 'circle-radius': 9, 'circle-color': '#3a5fc8', 'circle-stroke-color': halo, 'circle-stroke-width': 3 } });
      map.addLayer({ id: 'you-label', type: 'symbol', source: 'you', layout: { 'text-field': YOU + ' · ' + pmLabel(nbPm(data.you)), 'text-size': 12, 'text-font': ['Noto Sans Bold'], 'text-offset': [0, 1.5], 'text-allow-overlap': true },
        paint: { 'text-color': dark ? '#9db4ff' : '#3a5fc8', 'text-halo-color': halo, 'text-halo-width': 2.5 } });
    }
  }

  function create() {
    const box = $('nb-map');
    // centered on the block, at a neighborhood scale: the nearby road and the closest monitors in view
    const home = data.you ? [data.you.longitude, data.you.latitude] : [APP.place.lon, APP.place.lat];
    const zoom = box.clientWidth < PHONE_PX ? ZOOM_PHONE : ZOOM_WIDE;
    try {
      map = new maplibregl.Map({ container: box, style: STYLE[theme()], center: home, zoom, attributionControl: false, dragRotate: false });
    } catch (e) {
      box.innerHTML = '<p class="nb-map-msg">The map needs WebGL, which this browser has turned off. The table below has every monitor.</p>';
      document.body.dataset.mapReady = 'none'; map = null; return;
    }
    fitNearest(home, zoom);
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    map.on('load', () => box.querySelectorAll('.maplibregl-compact-show').forEach(el => el.classList.remove('maplibregl-compact-show')));   // credits folded into the ⓘ
    map.scrollZoom.disable();
    map.on('style.load', addLayers);
    map.once('idle', () => { document.body.dataset.mapReady = '1'; });   // scripts/screenshot.sh waits for this
    map.on('mousemove', 'mons', e => { const id = e.features[0].id; if (hoverId !== id) highlight(id); });
    map.on('mouseleave', 'mons', () => highlight(null));
  }

  // zoom out until the nearest neighbors are in view, still centered on the block: each one's mirror through home goes
  // in the box too, so the box stays centered. Only create() sets the camera; refresh() and a theme switch keep it.
  function fitNearest(home, zoom) {
    const near = data.others.slice(0, FIT_NEAREST).filter(n => Number.isFinite(n.longitude) && Number.isFinite(n.latitude));
    if (!near.length) return;
    const b = new maplibregl.LngLatBounds(home, home);
    near.forEach(n => { b.extend([n.longitude, n.latitude]); b.extend([2 * home[0] - n.longitude, 2 * home[1] - n.latitude]); });
    const cam = map.cameraForBounds(b, { padding: FIT_PAD, maxZoom: zoom });
    if (cam) map.jumpTo({ center: home, zoom: Math.max(FIT_MIN_ZOOM, cam.zoom) });
  }

  function highlight(id) {
    if (hoverId != null && map && map.getSource('mons')) map.setFeatureState({ source: 'mons', id: hoverId }, { hl: false });   // before the style loads there is no source
    document.querySelectorAll('#nb tr.hl').forEach(r => r.classList.remove('hl'));
    hoverId = id;
    if (id == null) return;
    if (map && map.getSource('mons')) map.setFeatureState({ source: 'mons', id }, { hl: true });
    const row = document.querySelector(`#nb tr[data-id="${id}"]`); if (row) row.classList.add('hl');
  }

  // called by renderNeighborhood with the monitors on the table and the wind
  function update(you, others, wind) {
    data = { you, others: others.map(n => ({ ...n, id: n.locationId })), wind };
    const box = $('nb-map'); if (!box) return;
    if (!('IntersectionObserver' in window)) return draw();
    if (!update.watching) { update.watching = true; onVisible(box, draw); }
    else if (map) refresh();
  }
  function draw() { load().then(() => { if (!map) create(); else refresh(); }).catch(() => { $('nb-map').innerHTML = '<p class="nb-map-msg">The map did not load. The table below has every monitor.</p>'; }); }
  // every minute: new readings and wind, same map (no reload, no flash)
  function refresh() {
    if (!map || !map.getSource('mons')) return;
    if (map.getSource('plume')) {
      map.getSource('plume').setData(plume(data.wind));
      map.setPaintProperty('plume', 'fill-color', '#f59e0b');
      map.setPaintProperty('plume', 'fill-opacity', ['*', ['get', 'op'], toward() ? 1.15 : .75]);
    }
    map.getSource('mons').setData(monitors());
  }
  function theme_() { if (map) { map.setStyle(STYLE[theme()]); } }
  return { update, highlight, theme: theme_ };
})();
