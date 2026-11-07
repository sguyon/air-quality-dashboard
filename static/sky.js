// Home Air Quality: the live sky behind the page and the Weather pill. Uses $, TZ, has, state and reading from app.js.
// ── Sky band: real sun position, cloud cover, wind and PM2.5. Preview overrides from the Customize panel. ──
var SKY = (() => {
  const LAT = 40.73, LON = -73.95, reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Start from the last real weather this browser saw, so a reload never shows made-up defaults.
  const live = { dir: 200, spd: 0, cloud: 0, pm: 0, rain: 0, thunder: false, temp: null, loaded: false };
  try {
    const saved = JSON.parse(localStorage.getItem('aq-sky-live') || 'null');
    if (saved && Date.now() - saved.at < 6 * 3600e3) Object.assign(live, saved.v, { loaded: true });
  } catch {}
  const remember = () => { try { localStorage.setItem('aq-sky-live', JSON.stringify({ at: Date.now(), v: { dir: live.dir, spd: live.spd, cloud: live.cloud, pm: live.pm, rain: live.rain, thunder: live.thunder, temp: live.temp } })); } catch {} };
  let preview = null;
  const on = /[?&]shot\b/.test(location.search) ? { sky: false, wind: false, haze: false }   // screenshot mode
    : (() => { try { return JSON.parse(localStorage.getItem('aq-fx') || 'null') || { sky: true, wind: true, haze: true }; } catch { return { sky: true, wind: true, haze: true }; } })();
  const save = () => { if (/[?&]shot\b/.test(location.search)) return; try { localStorage.setItem('aq-fx', JSON.stringify(on)); } catch {} };
  const nyMinutes = () => { const p = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', minute: 'numeric', hour12: false }).formatToParts(new Date()); const g = t => Number(p.find(x => x.type === t).value); return (g('hour') % 24) * 60 + g('minute'); };
  function sunPos(minutes) {
    const now = new Date();
    const tz = new Intl.DateTimeFormat('en-US', { timeZone: TZ, timeZoneName: 'shortOffset' }).formatToParts(now).find(x => x.type === 'timeZoneName').value;
    const offset = -60 * Number((tz.match(/GMT([+-]\d+)/) || [0, -5])[1]);
    const day = Math.floor((now - Date.UTC(now.getUTCFullYear(), 0, 0)) / 864e5);
    const g = 2 * Math.PI / 365 * (day - 1 + (minutes / 60 - 12) / 24);
    const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    const eqt = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    const ha = ((minutes + offset + eqt + 4 * LON) / 4 - 180) * Math.PI / 180, lat = LAT * Math.PI / 180;
    const cosz = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(ha), zen = Math.acos(Math.max(-1, Math.min(1, cosz)));
    let az = Math.acos(Math.max(-1, Math.min(1, (Math.sin(lat) * Math.cos(zen) - Math.sin(decl)) / (Math.cos(lat) * Math.sin(zen) || 1e-6)))) * 180 / Math.PI;
    az = ha > 0 ? (az + 180) % 360 : (540 - az) % 360;   // degrees clockwise from north
    return { el: 90 - zen * 180 / Math.PI, az };
  }
  const STOPS = [[-18, [12, 18, 34], [22, 30, 52]], [-8, [22, 34, 70], [70, 72, 112]], [-2, [52, 72, 128], [236, 146, 112]],
                 [3, [104, 146, 204], [252, 196, 140]], [10, [126, 178, 232], [214, 228, 240]], [40, [110, 170, 236], [222, 236, 248]]];
  const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
  const gray = (c, k) => { const l = Math.round(c[0] * .3 + c[1] * .59 + c[2] * .11); return mix(c, [l, l, l], k); };
  function skyAt(el) {
    const i = STOPS.findIndex(s => el < s[0]);
    if (i === -1) return [STOPS[5][1], STOPS[5][2]];
    if (i === 0) return [STOPS[0][1], STOPS[0][2]];
    const [e0, t0, h0] = STOPS[i - 1], [e1, t1, h1] = STOPS[i], t = (el - e0) / (e1 - e0);
    return [mix(t0, t1, t), mix(h0, h1, t)];
  }
  const st = () => preview || { minutes: nyMinutes(), ...live };
  let elev = 0, azim = 180;
  // Colors and wind ease toward their targets instead of snapping.
  const cur = { top: null, hor: null, dir: null, spd: 0 }, tgt = { top: [12, 18, 34], hor: [22, 30, 52] };
  const ease = (a, b, k) => a + (b - a) * k;
  const angEase = (a, b, k) => { const d = ((b - a + 540) % 360) - 180; return (a + d * k + 360) % 360; };
  const ICO = {
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    rise: '<path d="M12 2v6M8.5 5.5 12 2l3.5 3.5"/><path d="M5 18a7 7 0 0 1 14 0"/><path d="M2 22h20"/>',
    set: '<path d="M12 2v6M8.5 4.5 12 8l3.5-3.5"/><path d="M5 18a7 7 0 0 1 14 0"/><path d="M2 22h20"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 1 1 0 9Z"/>',
    therm: '<path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    arrow: '<path d="M12 19V5M6 11l6-6 6 6"/>',
    rain: '<path d="M17.5 15H9a6 6 0 1 1 5.8-7.5h1.7a3.75 3.75 0 0 1 1 7.5Z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
    bolt: '<path d="M17.5 14H9a6 6 0 1 1 5.8-7.5h1.7a3.75 3.75 0 0 1 1 7.5Z"/><path d="m12 14-2 4h3l-2 4"/>',
  };
  const ic = (d, extra = '') => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true"${extra}>${d}</svg>`;
  const words = v => {
    // golden hour: sun below ~6° (the usual definition); dawn and dusk: just below the horizon
    const morning = azim < 180;
    const phase = elev > 6 ? 'Day' : elev > 0 ? (morning ? 'Sunrise' : 'Golden hour') : elev > -6 ? (morning ? 'Dawn' : 'Dusk') : 'Night';
    const c = v.cloud || 0, skyW = c >= 90 ? 'Overcast' : c >= 60 ? 'Mostly cloudy' : c >= 25 ? 'Partly cloudy' : 'Clear sky';
    const pm = v.pm || 0, air = pm > 35 ? ['Smoky air', 'bad'] : pm > 12 ? ['Hazy air', 'warn'] : ['Air clear', 'good'];
    // drop: the order items hide in when the line is too narrow (1 first). The sky itself already shows time of day and clouds.
    const seg = (icon, text, cls = '', drop = 0, title = '') => `<span class="cap-i ${cls}"${drop ? ` data-drop="${drop}"` : ''}${title ? ` title="${title}"` : ''}>${icon}${text}</span>`;
    const out = [];
    if (preview) out.push('<span class="cap-tag">Preview</span>');
    else out.push(`<span class="cap-i cap-live${live.fresh ? '' : ' cached'}" title="${live.fresh ? 'Live: weather from Open-Meteo, updated now' : 'Last known weather; live data is loading'}"><i></i>${live.fresh ? '' : 'Last known · '}${label(nyMinutes())}</span>`);
    out.push(seg(ic(elev > 6 ? ICO.sun : elev > -6 ? (morning ? ICO.rise : ICO.set) : ICO.moon), phase, elev > 6 ? 'sun' : elev > -6 ? 'dusk' : 'night', 1));
    out.push(v.thunder ? seg(ic(ICO.bolt), 'Thunderstorm', 'storm') : (v.rain || 0) > .05 ? seg(ic(ICO.rain), (v.rain > .65 ? 'Heavy rain' : v.rain > .4 ? 'Rain' : 'Drizzle'), 'rainy') : seg(ic(ICO.cloud), skyW, '', 2));
    if (!preview && has(live.temp)) out.push(seg(ic(ICO.therm), `${Math.round(live.temp * 9 / 5 + 32)}°F`, '', 3));
    out.push((v.spd || 0) < 2 ? seg(ic(ICO.arrow, ' style="opacity:.4"'), 'Calm')
      : seg(ic(ICO.arrow, ` style="transform:rotate(${(v.dir + 180) % 360}deg)"`), `${card(v.dir)} ${v.spd} km/h`, 'wind', 0, `Wind from the ${card(v.dir)}${v.dir >= 80 && v.dir <= 200 ? ', carrying BQE exhaust this way' : ''}`));
    if (air[1] !== 'good') out.push(seg(ic(ICO.alert), air[0], 'air ' + air[1]));   // only when the outside air is not clean
    return out.join('');
  };
  // Keep the weather on one line: hide items by their drop order until it fits.
  function fitCap() {
    const cap = $('sky-cap'), items = [...cap.querySelectorAll('[data-drop]')].sort((a, b) => a.dataset.drop - b.dataset.drop);
    items.forEach(e => e.classList.remove('drop'));
    for (const e of items) { if (cap.scrollWidth <= cap.clientWidth + 1) break; e.classList.add('drop'); }
  }
  function paint() {
    const v = st(), sp = sunPos(v.minutes); elev = sp.el; azim = sp.az;
    const sky = $('sky'), dark = document.documentElement.dataset.theme === 'dark';
    sky.classList.toggle('off', !on.sky && !on.wind && !on.haze);
    let [top, hor] = skyAt(elev);
    const k = (v.cloud || 0) / 100 * .32; top = gray(top, k); hor = gray(hor, k);
    const rain = on.sky ? (v.rain || 0) : 0;
    if (rain) { top = mix(top, [34, 40, 54], rain * .72); hor = mix(hor, [72, 80, 96], rain * .62); }
    if (dark) { top = mix(top, [10, 16, 26], .5); hor = mix(hor, [14, 22, 34], .5); }
    tgt.top = top; tgt.hor = hor;
    // the monitor cards read these: the outdoor card shows this sky, the indoor card's window looks out on it
    const rs = document.documentElement.style, outLum = (top[0] * .3 + top[1] * .59 + top[2] * .11 + hor[0] * .3 + hor[1] * .59 + hor[2] * .11) / 2;
    rs.setProperty('--sky-top', `rgb(${top.map(Math.round)})`); rs.setProperty('--sky-hor', `rgb(${hor.map(Math.round)})`);
    // a light pastel of the same hue, for tints: keeps the sky's color (indigo at night, warm at dusk) without its darkness
    const pastel = (c, L) => { const [r, g, b] = c.map(v => v / 255), mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
      let h = 0; if (d) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h = (h * 60 + 360) % 360;
      const sat = Math.max(.45, Math.min(.75, d / (1 - Math.abs(mx + mn - 1) || 1))); return `hsl(${Math.round(h)} ${Math.round(sat * 100)}% ${L}%)`; };
    rs.setProperty('--sky-tint', pastel(top, 90)); rs.setProperty('--sky-tint2', pastel(hor, 93));
    // the header scenes follow the sky in the page's soft palette: same hue, lighter; a little deeper at night
    rs.setProperty('--scene-top', pastel(top, elev > -2 ? 84 : 72)); rs.setProperty('--scene-hor', pastel(hor, elev > -2 ? 90 : 80));
    rs.setProperty('--mark-top', pastel(top, elev > -2 ? 70 : 62)); rs.setProperty('--mark-hor', pastel(hor, elev > -2 ? 74 : 66));   // the logo's panes: same sky, richer
    document.documentElement.classList.toggle('outside-dark', outLum < 140);
    document.documentElement.classList.toggle('outside-night', elev < -6);
    // the header scenes follow the weather too (rain on the glass, clouds, light behind the doors at night)
    document.documentElement.classList.toggle('wx-rain', (v.rain || 0) > .05 || !!v.thunder);
    document.documentElement.classList.toggle('wx-cloud', (v.cloud || 0) >= 60);
    cloudCover = on.sky ? (v.cloud || 0) / 100 : 0;
    cloudTint = elev > 8 ? [255, 255, 255] : elev > -2 ? [255, 214, 196] : elev > -8 ? [150, 150, 180] : (dark ? [58, 68, 92] : [74, 84, 110]);
    if (rain) cloudTint = mix(cloudTint, [68, 74, 90], rain * .8);
    rainAmt = on.wind ? rain : 0; thunder = !!v.thunder && on.sky && !reduce;
    if (!cur.top || reduce) { cur.top = top.slice(); cur.hor = hor.slice(); }
    $('sky-grad').style.opacity = on.sky ? 1 : 0;
    const topLum = top[0] * .3 + top[1] * .59 + top[2] * .11;
    // clouds lighten what's behind the text: blend in their tint before choosing light or dark text
    const tintLum = cloudTint[0] * .3 + cloudTint[1] * .59 + cloudTint[2] * .11, ck = Math.min(.6, cloudCover * .6);
    const seenLum = topLum * (1 - ck) + tintLum * ck;
    document.documentElement.classList.toggle('sky-dark', on.sky && seenLum < 150);
    document.documentElement.classList.toggle('sky-on', on.sky);
    $('sky-haze').style.opacity = on.haze ? Math.min((v.pm || 0) / 55, 1) * .75 : 0;
    // sun glow: horizontal place from azimuth (east left, west right), height from elevation
    const clear = 1 - (v.cloud || 0) / 100 * .85;
    const glow = on.sky ? Math.max(0, Math.min(1, (elev + 5) / 6)) * (elev > 25 ? Math.max(.25, 1 - (elev - 25) / 40) : 1) * clear : 0;
    const sun = $('sky-sun');
    sun.style.left = `${Math.max(4, Math.min(96, 50 + (azim - 180) / 120 * 50))}%`;
    sun.style.top = `${Math.max(6, Math.min(78, 70 - elev * 1.4))}%`;
    sun.style.opacity = glow.toFixed(2);
    sun.classList.toggle('warm', elev < 12);
    // stars: only when it is dark and the sky is not covered
    $('sky-stars').style.opacity = on.sky ? (Math.max(0, Math.min(1, (-elev - 4) / 8)) * (1 - (v.cloud || 0) / 100 * .65)).toFixed(2) : 0;
    starsOn = on.sky && elev < -4;
    $('needle') && ($('needle').style.transform = `rotate(${(live.dir + 180) % 360}deg)`);
    $('sky-cap').innerHTML = preview || live.loaded ? words(v) : '<span class="cap-i">Loading the weather…</span>';
    fitCap();   // the weather line stays when the effects are off, so the layout never shifts
    syncPanel();
    kick();
  }
  // layers
  const cv = $('sky-wind'), ctx = cv.getContext('2d'), sc = $('sky-stars'), sctx = sc.getContext('2d'), cc = $('sky-clouds'), cctx = cc.getContext('2d');
  let clouds = [], sprites = [], cloudCover = 0, cloudTint = [255, 255, 255];
  const rc = $('sky-rain'), rctx = rc.getContext('2d'), bc = $('sky-bolt'), bctx = bc.getContext('2d'); let drops = [], rainAmt = 0, thunder = false, nextBolt = 0, bolt = null;
  let W = 0, H = 0, lines = [], stars = [], starsOn = false, last = 0, raf = 0, visible = true;
  const spawn = (p, anywhere) => {
    p.z = .35 + Math.random() * .65;                  // depth: far lines are thinner, slower, fainter
    p.x = Math.random() * W; p.y = Math.random() * H;
    p.l = (110 + Math.random() * 150) * p.z; p.life = anywhere ? Math.random() : 0; p.span = 4 + Math.random() * 6; p.seed = Math.random() * 1000;
    return p;
  };
  function resize() {
    const dpr = window.devicePixelRatio || 1;
    W = innerWidth; H = innerHeight;
    for (const [c, x] of [[cv, ctx], [sc, sctx], [cc, cctx], [rc, rctx], [bc, bctx]]) { c.width = W * dpr; c.height = H * dpr; x.setTransform(dpr, 0, 0, dpr, 0, 0); }
    // cloud sprites: soft clusters of white puffs, drawn once and reused
    sprites = Array.from({ length: 5 }, () => {
      const w = 520 + Math.random() * 360, h = w * (.32 + Math.random() * .1), o = document.createElement('canvas'); o.width = w; o.height = h;
      const g = o.getContext('2d');
      for (let i = 0; i < 16; i++) {
        const px = w * (.15 + Math.random() * .7), py = h * (.45 + Math.random() * .3), r = h * (.22 + Math.random() * .3);
        const rg = g.createRadialGradient(px, py, 0, px, py, r);
        rg.addColorStop(0, 'rgba(255,255,255,.55)'); rg.addColorStop(.6, 'rgba(255,255,255,.22)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = rg; g.beginPath(); g.arc(px, py, r, 0, Math.PI * 2); g.fill();
      }
      return o;
    });
    clouds = Array.from({ length: 16 }, (_, i) => ({ s: sprites[i % sprites.length], x: Math.random() * (W + 800) - 400, y: Math.random() * H * .7 - 60,
      z: .5 + Math.random() * .5, k: (i + .5) / 16, a: 0 }));
    lines = Array.from({ length: Math.round(W * H / 11000) }, () => spawn({}, true));
    drops = Array.from({ length: Math.round(W * H / 1800) }, () => ({ x: Math.random() * W, y: Math.random() * H, z: .35 + Math.random() * .65, k: Math.random() }));
    stars = Array.from({ length: Math.round(W * H / 6500) }, () => {
      const big = Math.random() < .07;
      return { x: Math.random() * W, y: Math.random() * H * .8, r: big ? 1.4 + Math.random() * .5 : .6 + Math.random() * .5,
               a: big ? .85 : .4 + Math.random() * .45, tw: Math.random() < .35, ph: Math.random() * 6.28, sp: .0006 + Math.random() * .0012 };
    });
    drawStars(0);
  }
  function drawStars(t) {
    sctx.clearRect(0, 0, W, H);
    for (const st2 of stars) {
      const a = st2.tw && !reduce ? st2.a * (.6 + .4 * Math.sin(t * st2.sp + st2.ph)) : st2.a;
      sctx.fillStyle = `rgba(236,243,255,${a.toFixed(3)})`; sctx.beginPath(); sctx.arc(st2.x, st2.y, st2.r, 0, Math.PI * 2); sctx.fill();
      if (st2.r > 1.3) { sctx.fillStyle = `rgba(200,220,255,${(a * .18).toFixed(3)})`; sctx.beginPath(); sctx.arc(st2.x, st2.y, st2.r * 3, 0, Math.PI * 2); sctx.fill(); }
    }
  }
  // A jagged path by midpoint displacement: reads as lightning, not as a zigzag.
  const jag = (x1, y1, x2, y2, d, out) => {
    if (d < 6) { out.push([x2, y2]); return out; }
    const mx = (x1 + x2) / 2 + (Math.random() - .5) * d, my = (y1 + y2) / 2 + (Math.random() - .5) * d * .25;
    jag(x1, y1, mx, my, d / 2, out); jag(mx, my, x2, y2, d / 2, out); return out;
  };
  function strike(t) {
    const cards = [...document.querySelectorAll('.card, section.ai')].map(el => [el, el.getBoundingClientRect()])
      .filter(([, r]) => r.width > 0 && r.top > 70 && r.top < H * .75);
    const front = cards.length > 0 && Math.random() < .7;
    let x0 = W * (.15 + Math.random() * .7), ex = x0 + (Math.random() - .5) * 220, ey = H * (.3 + Math.random() * .3), hit = null;
    if (front) { const [el, r] = cards[Math.floor(Math.random() * cards.length)]; hit = el; ex = r.left + r.width * (.15 + Math.random() * .7); ey = r.top + 1; x0 = ex + (Math.random() - .5) * Math.min(420, W * .35); }
    const pts = jag(x0, -20, ex, ey, Math.max(120, ey * .35), [[x0, -20]]), branches = [];
    for (let i = 3; i < pts.length - 4; i += 2) if (Math.random() < .09) {
      const [bx, by] = pts[i], dir = Math.random() < .5 ? -1 : 1;
      branches.push(jag(bx, by, bx + dir * (40 + Math.random() * 110), by + 50 + Math.random() * 90, 40, [[bx, by]]));
    }
    // light: the sky flashes behind; a front strike also lights the page and throws the cards' shadows away from it
    $('sky-flash').animate([{ opacity: 0 }, { opacity: front ? .9 : .6 }, { opacity: .1 }, { opacity: front ? .7 : .4 }, { opacity: 0 }], { duration: 700, easing: 'ease-out' });
    if (front) {
      const ff = $('front-flash'); ff.style.setProperty('--bx', `${(ex / W * 100).toFixed(1)}%`);
      ff.animate([{ opacity: 0 }, { opacity: .55 }, { opacity: .05 }, { opacity: .4 }, { opacity: 0 }], { duration: 700, easing: 'ease-out' });
      for (const [el, r] of [...document.querySelectorAll('.card, section.ai, .bar .custom, .bar .dsp')].map(el => [el, el.getBoundingClientRect()])) {
        if (r.bottom < 0 || r.top > H) continue;
        const dx = Math.max(-18, Math.min(18, (r.left + r.width / 2 - ex) / 30)), dy = Math.max(6, Math.min(22, (r.top - ey) / 25 + 10));
        const lit = `${dx.toFixed(1)}px ${dy.toFixed(1)}px 26px rgba(4, 10, 30, .38)`, rest = getComputedStyle(el).boxShadow;
        const shadow = el === hit ? `0 -1px 0 rgba(225,235,255,.95), 0 -6px 34px rgba(170,195,255,.75), ${lit}` : lit;
        el.animate([{ boxShadow: rest }, { boxShadow: shadow, offset: .08 }, { boxShadow: rest, offset: .2 }, { boxShadow: shadow, offset: .3 }, { boxShadow: rest }], { duration: 760, easing: 'ease-out' });
      }
      if (hit) hit.animate([{ transform: 'none' }, { transform: 'translateY(1.5px)', offset: .25 }, { transform: 'none' }], { duration: 260, delay: 120, easing: 'ease-out' });
    }
    return { pts, branches, t0: t, front };
  }
  function frame(t) {
    raf = 0; const dt = Math.min(50, t - last || 16); last = t; const v = st();
    const kk = 1 - Math.exp(-dt / 450);                 // ~1 s to settle
    let moving = false;
    if (cur.top) {
      cur.top = cur.top.map((c, i) => ease(c, tgt.top[i], kk)); cur.hor = cur.hor.map((c, i) => ease(c, tgt.hor[i], kk));
      moving = cur.top.some((c, i) => Math.abs(c - tgt.top[i]) > .5) || cur.hor.some((c, i) => Math.abs(c - tgt.hor[i]) > .5);
      const r = a => a.map(Math.round).join(',');
      $('sky-grad').style.background = `linear-gradient(180deg, rgb(${r(cur.top)}) 0%, rgb(${r(cur.hor)}) 100%)`;
    }
    cur.dir = cur.dir == null ? (v.dir || 0) : angEase(cur.dir, v.dir || 0, kk);
    cur.spd = ease(cur.spd, v.spd || 0, kk);
    ctx.clearRect(0, 0, W, H);
    if (on.wind) {
      const lightSky = elev > -2 && document.documentElement.dataset.theme !== 'dark' && on.sky;
      const base = lightSky ? '255,255,255' : '214,228,255', boost = lightSky ? 2.6 : 1.15;
      ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
      const strength = Math.min(1, .35 + cur.spd / 12);
      ctx.lineCap = 'round';
      const share = Math.min(1, .25 + cur.spd / 26);   // calm: a few lines; strong wind: all of them
      const head = (cur.dir + 180) * Math.PI / 180;
      // Side view: wind crosses the screen almost level, so it never reads as falling rain.
      let hx = Math.sin(head); if (Math.abs(hx) < .45) hx = hx < 0 ? -.45 : .45;
      const vy = -Math.cos(head) * .05, dark = !lightSky;
      for (let li = 0; li < lines.length; li++) {
        const p = lines[li]; if (li / lines.length > share) continue;
        const bend = Math.sin(p.y * .005 + p.seed + t * .0002) * .07;
        const ux = hx, uy = vy + bend;
        if (!reduce) { const step = cur.spd * .03 * dt * p.z; p.x += ux * step; p.y += uy * step; p.life += dt / 1000 / p.span; }
        if (p.life >= 1 || p.x < -260 || p.x > W + 260 || p.y < -150 || p.y > H + 150) { spawn(p, false); continue; }
        // gusts: a slow wave sweeps across the screen in the wind's direction
        const gust = .35 + .65 * Math.max(0, Math.sin(p.x * .0028 * Math.sign(hx) - t * .0011 + p.y * .0009));
        const fade = Math.sin(Math.PI * Math.min(1, p.life)), a = Math.min(.85, (.14 + .4 * p.z) * fade * strength * boost * gust * (dark ? .8 : 1));
        if (a < .01) continue;
        const len = p.l * Math.min(1, .35 + cur.spd / 16), n = 10, amp = (1.5 + p.z * 3) * Math.min(1, .4 + cur.spd / 20);
        // a ribbon with a gentle ripple that travels along it
        ctx.beginPath(); ctx.moveTo(p.x, p.y);
        let x = p.x, y = p.y;
        for (let s2 = 1; s2 <= n; s2++) {
          const f = s2 / n, rip = Math.sin(f * 5.2 + p.seed - t * .004) * amp * f;
          ctx.lineTo(p.x - ux * len * f, p.y - uy * len * f + rip); x = p.x - ux * len * f; y = p.y - uy * len * f;
        }
        const g = ctx.createLinearGradient(p.x, p.y, x, y);
        g.addColorStop(0, `rgba(${base},${(a * .35).toFixed(3)})`); g.addColorStop(.2, `rgba(${base},${a.toFixed(3)})`); g.addColorStop(1, `rgba(${base},0)`);
        if (lightSky) {   // a darker blue edge under the white core keeps ribbons visible on a bright sky
          const e = ctx.createLinearGradient(p.x, p.y, x, y);
          e.addColorStop(0, 'rgba(28,74,140,0)'); e.addColorStop(.2, `rgba(28,74,140,${(a * .38).toFixed(3)})`); e.addColorStop(1, 'rgba(28,74,140,0)');
          ctx.strokeStyle = e; ctx.lineWidth = (.7 + p.z) * 3; ctx.stroke();
        }
        ctx.strokeStyle = g; ctx.lineWidth = (.6 + p.z * .9) * (lightSky ? 1.4 : 1); ctx.stroke();
      }
    }
    if (starsOn) drawStars(t);
    // rain: slanted by the wind, three depths; only the share of drops that matches the intensity is drawn
    rctx.clearRect(0, 0, W, H);
    if (rainAmt > .02) {
      const tilt = Math.sin((cur.dir + 180) * Math.PI / 180) * Math.min(.6, cur.spd / 40);
      rctx.lineCap = 'round';
      for (const d of drops) {
        if (d.k > rainAmt) continue;
        const fall = (.9 + d.z * 1.3) * dt * 1.1;
        if (!reduce) { d.y += fall; d.x += fall * tilt; }
        if (d.y > H + 20) { d.y = -20 - Math.random() * 60; d.x = Math.random() * (W + 200) - 100; }
        if (d.x > W + 40) d.x -= W + 80; if (d.x < -40) d.x += W + 80;
        const len = 10 + d.z * 16;
        rctx.strokeStyle = `rgba(206,220,240,${(.18 + d.z * .38).toFixed(3)})`; rctx.lineWidth = .7 + d.z * .9;
        rctx.beginPath(); rctx.moveTo(d.x, d.y); rctx.lineTo(d.x - tilt * len, d.y - len); rctx.stroke();
      }
    }
    // lightning: sheet flashes behind the page, and now and then a strike in front of it that lands on a card
    if (bolt || thunder) bctx.clearRect(0, 0, W, H);
    if (thunder && visible) {
      if (!nextBolt) nextBolt = t + 1200;
      if (t > nextBolt) { nextBolt = t + 4000 + Math.random() * 6000; bolt = strike(t); }
    } else { nextBolt = 0; }
    if (bolt) {
      const age = t - bolt.t0;
      // a strike flickers: on, off, a brighter re-strike, then it fades
      const a = age < 90 ? 1 : age < 150 ? 0 : age < 520 ? 1 - (age - 150) / 370 : -1;
      if (a < 0) { bolt = null; bctx.clearRect(0, 0, W, H); }
      else if (a > 0) {
        const c = bolt.front ? bctx : rctx;
        c.save(); c.lineJoin = 'round'; c.lineCap = 'round';
        const path = pts => { c.beginPath(); pts.forEach(([px, py], i) => i ? c.lineTo(px, py) : c.moveTo(px, py)); };
        for (const [w, col, blur] of [[12, `rgba(150,180,255,${(.16 * a).toFixed(3)})`, 30], [4.5, `rgba(190,210,255,${(.5 * a).toFixed(3)})`, 12], [1.9, `rgba(255,255,255,${a.toFixed(3)})`, 4]]) {
          c.shadowColor = 'rgba(170,195,255,.9)'; c.shadowBlur = blur; c.strokeStyle = col;
          c.lineWidth = w; path(bolt.pts); c.stroke();
          c.lineWidth = w * .45; for (const br of bolt.branches) { path(br); c.stroke(); }
        }
        if (bolt.front) {   // the impact glows on the card's top edge
          const [ix, iy] = bolt.pts[bolt.pts.length - 1], rg = c.createRadialGradient(ix, iy, 0, ix, iy, 70);
          rg.addColorStop(0, `rgba(235,242,255,${(.9 * a).toFixed(3)})`); rg.addColorStop(1, 'rgba(200,215,255,0)');
          c.shadowBlur = 0; c.fillStyle = rg; c.beginPath(); c.arc(ix, iy, 70, 0, Math.PI * 2); c.fill();
        }
        c.restore();
      }
    }
    const cloudsMoving = cloudCover > .01;
    cctx.clearRect(0, 0, W, H);
    if (cloudCover > 0.01 || clouds.some(c => c.a > .01)) {
      const to = (cur.dir + 180) * Math.PI / 180, drift = Math.sin(to) * (cur.spd || 0) * .004 * dt;
      // an even veil when it is mostly or fully overcast
      if (cloudCover > .5) { cctx.fillStyle = `rgba(${cloudTint},${((cloudCover - .5) * .5).toFixed(3)})`; cctx.fillRect(0, 0, W, H); }
      for (const c of clouds) {
        const want = Math.min(1, Math.max(0, Math.min(1, (cloudCover - c.k * .9) * 4)) * (1 + rainAmt * .6));   // more clouds as cover rises; heavier in rain
        c.a += (want - c.a) * kk;
        if (!reduce) c.x += drift * c.z;
        const w = c.s.width * c.z * 1.4, h = c.s.height * c.z * 1.4;
        if (c.x > W + 50) c.x = -w; if (c.x < -w - 50) c.x = W;
        if (c.a < .01) continue;
        cctx.globalAlpha = c.a * (.55 + .45 * c.z);
        cctx.drawImage(c.s, c.x, c.y, w, h);
      }
      cctx.globalAlpha = 1;
      // tint the white sprites to the light of the moment
      cctx.globalCompositeOperation = 'source-atop'; cctx.fillStyle = `rgb(${cloudTint})`; cctx.fillRect(0, 0, W, H); cctx.globalCompositeOperation = 'source-over';
    }
    if ((on.wind || moving || starsOn || cloudsMoving || rainAmt > .02 || thunder || bolt) && visible && !reduce && !document.hidden) raf = requestAnimationFrame(frame);
  }
  function kick() { if (!raf) raf = requestAnimationFrame(t => { last = t; frame(t); }); }
  new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible) kick(); }).observe($('sky'));
  document.addEventListener('visibilitychange', kick);
  window.addEventListener('resize', () => { resize(); fitCap(); kick(); });
  // panel
  const label = m => new Date(2000, 0, 1, Math.floor(m / 60), m % 60).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const card = d => ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][Math.round(d / 22.5) % 16];
  function syncPanel() {
    const v = st();
    $('fx-time').value = v.minutes; $('fx-dir').value = v.dir; $('fx-spd').value = v.spd; $('fx-cloud').value = v.cloud; $('fx-pm').value = v.pm; $('fx-rain').value = Math.round((v.rain || 0) * 100); $('fx-v-rain').textContent = !v.rain ? 'None' : v.thunder ? 'Thunderstorm' : v.rain > .65 ? 'Heavy' : v.rain > .4 ? 'Rain' : 'Drizzle';
    const phase = elev > 6 ? 'day' : elev > 0 ? (azim < 180 ? 'sunrise' : 'golden hour') : elev > -6 ? (azim < 180 ? 'dawn' : 'dusk') : 'night';
    $('fx-v-time').textContent = `${label(v.minutes)} · ${phase}`; $('fx-v-dir').textContent = card(v.dir);
    $('fx-v-spd').textContent = `${v.spd} km/h`; $('fx-v-cloud').textContent = `${Math.round(v.cloud)}%`; $('fx-v-pm').textContent = `${v.pm} µg/m³`;
    $('fx-mode').textContent = preview ? 'Preview' : 'Live'; $('fx-mode').classList.toggle('is-preview', !!preview); $('fx-live').hidden = !preview;
    for (const k of ['sky', 'wind', 'haze']) $('fx-on-' + k).checked = on[k];
    const any = on.sky || on.wind || on.haze, q = $('sky-quick');
    q.setAttribute('aria-pressed', String(any)); q.title = any ? 'Turn the live sky off' : 'Turn the live sky on'; q.classList.toggle('off', !any);
  }
  const PRE = {
    dawn: { minutes: 395, dir: 40, spd: 2, cloud: 10, pm: 2 }, noon: { minutes: 750, dir: 300, spd: 22, cloud: 5, pm: 3 },
    dusk: { minutes: 1010, dir: 250, spd: 14, cloud: 30, pm: 6 }, night: { minutes: 1380, dir: 200, spd: 8, cloud: 5, pm: 1 },
    smoke: { minutes: 840, dir: 290, spd: 10, cloud: 20, pm: 48 },
    storm: { minutes: 1035, dir: 265, spd: 34, cloud: 100, pm: 4, rain: 1, thunder: true },
  };
  function setPreview(p) { preview = p; paint(); kick(); }
  window.skyPreview = p => setPreview(p);   // used by the menu's Random cycle (app.js)
  ['time', 'dir', 'spd', 'cloud', 'pm', 'rain'].forEach(id => $('fx-' + id).addEventListener('input', e => {
    const v = { ...st() }; v[id === 'time' ? 'minutes' : id] = id === 'rain' ? Number(e.target.value) / 100 : Number(e.target.value); if (id === 'rain') v.thunder = v.rain > .85; setPreview(v);
  }));
  document.querySelectorAll('[data-fx]').forEach(b => b.addEventListener('click', () => setPreview({ rain: 0, thunder: false, ...PRE[b.dataset.fx] })));
  $('fx-live').addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); setPreview(null); });
  ['sky', 'wind', 'haze'].forEach(k => $('fx-on-' + k).addEventListener('change', e => { on[k] = e.target.checked; save(); paint(); kick(); }));
  $('sky-quick').addEventListener('click', e => {
    e.preventDefault(); e.stopPropagation();
    const any = on.sky || on.wind || on.haze;
    on.sky = on.wind = on.haze = !any; save(); paint(); kick();
  });
  if (window.__wx) { live.loaded = true; const w = window.__wx; if (has(w.temperature)) live.temp = w.temperature; if (has(w.wind_direction)) live.dir = w.wind_direction; if (has(w.wind_speed)) live.spd = Math.round(w.wind_speed * 2) / 2; if (has(w.cloud_cover)) live.cloud = w.cloud_cover; }
  if (state.outdoor) { const v = reading(state.outdoor, false).pm; if (has(v)) live.pm = Math.round(v * 2) / 2; }
  resize(); paint(); kick();
  setTimeout(() => { if (typeof state !== 'undefined' && state.read && typeof renderAgenda === 'function') renderAgenda(state.read); }, 0);   // the agenda's sunrise needs the sky
  setInterval(() => { if (!preview) paint(); }, 60000);
  return {
    sunEl: m => sunPos(m).el,
    weather(w) { live.loaded = true; live.fresh = true; if (has(w.temperature)) live.temp = w.temperature; if (has(w.wind_direction)) live.dir = w.wind_direction; if (has(w.wind_speed)) live.spd = Math.round(w.wind_speed * 2) / 2; if (has(w.cloud_cover)) live.cloud = w.cloud_cover;
      const code = w.weather_code;   // WMO codes from Open-Meteo
      live.thunder = code >= 95;
      live.rain = !has(code) ? 0 : code >= 95 ? 1 : code >= 80 ? .7 : code >= 61 ? (code >= 65 ? .9 : .6) : code >= 51 ? .3 : 0;
      remember(); paint(); kick(); },
    pm(v) { if (has(v)) live.pm = Math.round(v * 2) / 2; if (live.loaded) remember(); paint(); },
    // A theme switch jumps straight to the new sky colors; the page-wide cross-fade does the easing.
    theme() { cur.top = null; paint(); const r = a => a.map(Math.round).join(','); $('sky-grad').style.background = `linear-gradient(180deg, rgb(${r(cur.top)}) 0%, rgb(${r(cur.hor)}) 100%)`; },
  };
})();

// Display dropdown: same behavior as the Home panel; opening one closes the other.
(() => {
  const d = $('dsp'), u = document.querySelector('.bar details.custom');
  const close = (el, refocus) => { if (el && el.open) { el.open = false; if (refocus) el.querySelector('summary').focus(); } };
  $('dsp-close').addEventListener('click', e => { e.preventDefault(); close(d, true); });
  d.addEventListener('toggle', () => { d.querySelector('summary').setAttribute('aria-expanded', String(d.open)); if (d.open) close(u); });
  if (u) u.addEventListener('toggle', () => { if (u.open) close(d); });
  document.addEventListener('click', e => { if (d.open && !d.contains(e.target)) close(d); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && d.open) close(d, true); });
})();
