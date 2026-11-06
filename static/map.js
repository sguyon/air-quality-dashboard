// Home Air Quality: the Neighborhood map. Loaded only when the section nears the screen.
// MapLibre (open source) draws OpenFreeMap tiles: free, no key. The BQE path comes from OpenStreetMap routing (static/bqe.json).
// Uses $, state, has, PM_FINE, TZ and the table rows (data-id) from app.js.
var NBMAP = (() => {
  const MAPLIBRE = 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min';
  const STYLE = { light: 'https://tiles.openfreemap.org/styles/positron', dark: 'https://tiles.openfreemap.org/styles/dark' };
  const BQE_TOWARD = [80, 200];          // wind from these directions carries BQE exhaust toward home (same as server.py)
  let map = null, bqe = null, data = null, hoverId = null, loading = null;
  const fc = f => ({ type: 'FeatureCollection', features: f });
  const theme = () => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';

  function load() {
    if (loading) return loading;
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = MAPLIBRE + '.css'; document.head.appendChild(css);
    loading = Promise.all([
      new Promise((ok, no) => { const s = document.createElement('script'); s.src = MAPLIBRE + '.js'; s.onload = ok; s.onerror = no; document.head.appendChild(s); }),
      fetch('/static/bqe.json').then(r => r.json()).then(j => { bqe = j; }),
    ]);
    return loading;
  }

  function plume(deg) {
    if (deg == null || !bqe) return fc([]);
    const to = (deg + 180) * Math.PI / 180, kLat = 1 / 111.1, kLon = 1 / 84.2;
    return fc([[0.6, .22], [1.2, .14], [1.9, .08]].map(([d, op]) => {
      const moved = bqe.map(([lo, la]) => [lo + Math.sin(to) * d * kLon, la + Math.cos(to) * d * kLat]);
      return { type: 'Feature', properties: { op }, geometry: { type: 'Polygon', coordinates: [[...bqe, ...moved.reverse(), bqe[0]]] } };
    }));
  }

  function addLayers() {
    const dark = theme() === 'dark', ink = dark ? '#ececef' : '#18181b', halo = dark ? '#17181c' : '#ffffff';
    const toward = data.wind != null && data.wind >= BQE_TOWARD[0] && data.wind <= BQE_TOWARD[1];
    map.addSource('plume', { type: 'geojson', data: plume(data.wind) });
    map.addLayer({ id: 'plume', type: 'fill', source: 'plume', paint: { 'fill-color': '#f59e0b', 'fill-opacity': ['*', ['get', 'op'], toward ? 1.15 : .75] } });
    map.addSource('bqe', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: bqe } } });
    map.addLayer({ id: 'bqe-case', type: 'line', source: 'bqe', paint: { 'line-color': halo, 'line-width': 8 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
    map.addLayer({ id: 'bqe', type: 'line', source: 'bqe', paint: { 'line-color': dark ? '#a1a1aa' : '#71717a', 'line-width': 4 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
    map.addLayer({ id: 'bqe-label', type: 'symbol', source: 'bqe', layout: { 'symbol-placement': 'line', 'text-field': 'BQE', 'text-size': 11, 'text-font': ['Noto Sans Bold'], 'symbol-spacing': 500 },
      paint: { 'text-color': dark ? '#d4d4d8' : '#52525b', 'text-halo-color': halo, 'text-halo-width': 2 } });
    map.addSource('mons', { type: 'geojson', data: fc(data.others.map(n => ({ type: 'Feature', id: n.id, properties: { pm: n.pm02, label: (Math.round(n.pm02 * 10) / 10).toFixed(1) }, geometry: { type: 'Point', coordinates: [n.longitude, n.latitude] } }))) });
    map.addLayer({ id: 'mons', type: 'circle', source: 'mons', paint: {
      'circle-radius': ['+', 6, ['min', 10, ['*', ['get', 'pm'], .9]]],
      'circle-color': ['case', ['>', ['get', 'pm'], PM_FINE], '#f59e0b', '#22a55a'], 'circle-opacity': .9,
      'circle-stroke-color': ['case', ['boolean', ['feature-state', 'hl'], false], ink, halo],
      'circle-stroke-width': ['case', ['boolean', ['feature-state', 'hl'], false], 3, 2] } });
    map.addLayer({ id: 'mons-label', type: 'symbol', source: 'mons', layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-font': ['Noto Sans Bold'], 'text-offset': [0, -1.6], 'text-allow-overlap': true },
      paint: { 'text-color': ink, 'text-halo-color': halo, 'text-halo-width': 2 } });
    if (data.you) {
      map.addSource('you', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [data.you.longitude, data.you.latitude] } } });
      map.addLayer({ id: 'you', type: 'circle', source: 'you', paint: { 'circle-radius': 9, 'circle-color': '#3a5fc8', 'circle-stroke-color': halo, 'circle-stroke-width': 3 } });
      map.addLayer({ id: 'you-label', type: 'symbol', source: 'you', layout: { 'text-field': 'You · ' + (Math.round(data.you.pm02 * 10) / 10).toFixed(1), 'text-size': 12, 'text-font': ['Noto Sans Bold'], 'text-offset': [0, 1.5], 'text-allow-overlap': true },
        paint: { 'text-color': dark ? '#9db4ff' : '#3a5fc8', 'text-halo-color': halo, 'text-halo-width': 2.5 } });
    }
  }

  function create() {
    const box = $('nb-map');
    try {
      // centered on the block, at a neighborhood scale: the nearby BQE (~1 km) and the closest monitors in view
      const home = data.you ? [data.you.longitude, data.you.latitude] : [-73.95, 40.73];
      map = new maplibregl.Map({ container: box, style: STYLE[theme()], center: home, zoom: box.clientWidth < 600 ? 12.1 : 12.7, attributionControl: false, dragRotate: false });
    } catch (e) {
      box.innerHTML = '<p class="nb-map-msg">The map needs WebGL, which this browser has turned off. The table below has every monitor.</p>';
      document.body.dataset.mapReady = 'none'; map = null; return;
    }
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    map.on('load', () => box.querySelectorAll('.maplibregl-compact-show').forEach(el => el.classList.remove('maplibregl-compact-show')));   // credits folded into the ⓘ
    map.scrollZoom.disable();
    map.on('style.load', addLayers);
    map.once('idle', () => { document.body.dataset.mapReady = '1'; });   // scripts/screenshot.sh waits for this
    map.on('mousemove', 'mons', e => { const id = e.features[0].id; if (hoverId !== id) highlight(id); });
    map.on('mouseleave', 'mons', () => highlight(null));
  }

  function highlight(id) {
    if (hoverId != null && map) map.setFeatureState({ source: 'mons', id: hoverId }, { hl: false });
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
    const dark = theme() === 'dark', toward = data.wind != null && data.wind >= BQE_TOWARD[0] && data.wind <= BQE_TOWARD[1];
    map.getSource('plume').setData(plume(data.wind));
    map.setPaintProperty('plume', 'fill-color', '#f59e0b');
    map.setPaintProperty('plume', 'fill-opacity', ['*', ['get', 'op'], toward ? 1.15 : .75]);
    map.getSource('mons').setData(fc(data.others.map(n => ({ type: 'Feature', id: n.id, properties: { pm: n.pm02, label: (Math.round(n.pm02 * 10) / 10).toFixed(1) }, geometry: { type: 'Point', coordinates: [n.longitude, n.latitude] } }))));
  }
  function theme_() { if (map) { map.setStyle(STYLE[theme()]); } }
  return { update, highlight, theme: theme_ };
})();
