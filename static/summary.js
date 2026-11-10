// Home Air Quality: the summary card (items, profiles, day chart, hover readout), drawn from /api/analyze's
// `summary` object. The rules in summary.py decide everything; this file only draws it.
// Spec: internal/specs/summary-redesign-spec.md · visual reference: internal/design-archive/49-summary-needs-row.html, profiles as in 52 (B9 without the underline)
(function (root) {
  'use strict';

  // ── pure helpers (tested in tests/summary.test.mjs) ──
  // An ISO time as hours on the chart's axis: the hour of t0 plus the hours since t0 (so midnight is 24, not 0).
  const hourOfIso = iso => { const m = /T(\d\d):(\d\d)/.exec(iso); return m ? +m[1] + +m[2] / 60 : 0; };
  const hoursOf = (iso, t0) => hourOfIso(t0) + (Date.parse(iso) - Date.parse(t0)) / 3.6e6;
  const lerp = (pts, t) => {
    if (!pts || !pts.length || t < pts[0][0] || t > pts[pts.length - 1][0]) return null;
    for (let i = 1; i < pts.length; i++) if (t <= pts[i][0]) {
      const [a, va] = pts[i - 1], [b, vb] = pts[i]; return va + (vb - va) * (t - a) / (b - a || 1);
    }
    return pts[pts.length - 1][1];
  };
  const shareOfLimit = (v, lim) => v / lim;
  const hourLabel = t => { const h = ((Math.floor(t) % 24) + 24) % 24; return ((h + 11) % 12 + 1) + (h >= 12 ? ' PM' : ' AM'); };
  const fmtClock = t => {   // 15.5 -> '3:30 PM', to 10 minutes
    let h = ((Math.floor(t) % 24) + 24) % 24, m = Math.round((t - Math.floor(t)) * 6) * 10;
    if (m === 60) { m = 0; h = (h + 1) % 24; }
    return ((h + 11) % 12 + 1) + ':' + String(m).padStart(2, '0') + (h >= 12 ? ' PM' : ' AM');
  };
  const isoClock = iso => fmtClock(hourOfIso(iso)).replace(':00 ', ' ');
  // a "before 4 PM" whose moment has passed is dropped, so a page left open never shows a stale time
  const staleWhen = (action, now) => (!action || !action.when) ? null
    : (action.when_end && Date.parse(action.when_end) <= +now) ? null : action.when;
  const tipSide = (px, width, tipWidth) => px + 16 + tipWidth > width ? 'left' : 'right';
  // The page's clock. The demo (window.APP.now) runs from its story moment, advancing as the tab stays open; a real home
  // runs on the real clock. For what the page shows; timers and cache stamps keep Date.now().
  const LOADED = Date.now();
  const appNow = () => { const n = root.APP && root.APP.now;
    return n ? new Date(Date.parse(n.at) + (Date.now() - LOADED)) : new Date(); };
  // The time the readings are from, for how old a reading is and where the history ends: the demo's data never moves
  // past its moment, so a demo tab left open stays live and asks for the same history URLs. A real home: now.
  const readingsNow = () => { const n = root.APP && root.APP.now; return n ? new Date(Date.parse(n.at)) : new Date(); };

  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const PROFILE_ICON = {
    toddler: '<svg viewBox="0 0 24 24"><path d="M10 16c.5.3 1.2.5 2 .5s1.5-.2 2-.5"/><path d="M15 12h.01"/><path d="M19.38 6.813A9 9 0 0 1 20.8 10.2a2 2 0 0 1 0 3.6 9 9 0 0 1-17.6 0 2 2 0 0 1 0-3.6A9 9 0 0 1 12 3c2 0 3.5 1.1 3.5 2.5s-.9 2.5-2 2.5c-.8 0-1.5-.4-1.5-1"/><path d="M9 12h.01"/></svg>',
    sinus: '<svg viewBox="0 0 24 24"><path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/></svg>',
    runner: '<svg viewBox="0 0 24 24"><circle cx="13" cy="4" r="1"/><path d="M4 17l5 1l.75-1.5"/><path d="M15 21v-4l-4-3l1-6"/><path d="M7 12V9l5-1l3 3l3 1"/></svg>',
  };
  const INFO = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="4.9" r=".9" fill="currentColor" stroke="none"/></svg>';
  // a tap target that opens a sentence over what's below; body is HTML
  // label: what the tap target names for screen readers and shows on hover (a profile icon: "Toddler: Stale indoors")
  const popHtml = (summary, body, cls = '', label = '') => `<details class="sx-why"><summary${cls ? ` class="${cls}"` : ''} aria-label="${label ? esc(label) : 'Why'}"${label ? ` title="${esc(label)}"` : ''}>${summary}</summary><p>${body}</p></details>`;
  const tone = n => n.ok === true ? 'ok' : n.ok === false ? 'warn' : 'muted';
  // the profiles, always there but quiet: three icons in the header line, a dot for the state; a tap opens the sentence
  const profilesHeadHtml = profiles => `<span class="sx-nh">${(profiles || []).map(n => popHtml(
    `<i>${PROFILE_ICON[n.id] || ''}<b></b></i>`, `<strong>${esc(n.name)}: ${esc(n.state)}.</strong> ${esc(n.why)}`, `sx-nh-i ${tone(n)}`,
    `${n.name}: ${n.state}`)).join('')}</span>`;
  // on an item, its profile's icon and state take the (i)'s place and open the item's why, then the profile's sentence
  const itemProfileHtml = (it, profiles) => {
    if (!it.why) return '';
    const n = (profiles || []).find(x => x.id === it.profile);
    if (!n) return popHtml(INFO, esc(it.why));
    return popHtml(`${PROFILE_ICON[n.id] || ''}${esc(n.state)}`,
      `${esc(it.why)}<span class="sx-nl"><strong>${esc(n.name)}:</strong> ${esc(n.why)}</span>`, `sx-nchip ${tone(n)}`);
  };

  // chart labels: a label that would run past the chart's right edge (R) ends just before its point instead
  const fitLabel = (x, text, R, size = 10.5) => { const w = text.length * size * .58;
    return x + 8 + w <= R ? { x: x + 8, anchor: 'start' } : { x: x - 8, anchor: 'end' }; };
  // the humidity label sits under its dot, unless the CO₂ label (above the CO₂ dot, same end of the chart) is there
  const rhLabelY = (co2LabelY, rhDotY) => { const y = rhDotY + 14;
    return co2LabelY == null || Math.abs(y - co2LabelY) >= 12 ? y : Math.min(rhDotY - 7, co2LabelY - 13); };
  // the PM2.5 peak the card speaks about: from now to the end of the outlook (summary.py OUTLOOK_HOURS), not the whole chart
  const OUTLOOK_H = 8;
  const peakAhead = (past, fc, now, hours = OUTLOOK_H) => {
    const pts = [...past.slice(-1), ...fc].filter(p => p[0] <= now + hours);
    return pts.length ? pts.reduce((a, b) => b[1] > a[1] ? b : a) : null; };
  // The PM2.5 past half. A measured past is a soft area; the model's past hours (a public monitor without history:
  // the series says source "model") are a dotted line over a pale fill, labeled as the model, so they never read as a
  // reading. d: the line, area: the line closed down to the axis, at: the label's spot, col: the colours (fill: the series').
  const MODEL_LABEL = 'PM2.5 outside · model';
  const pmPastSvg = (source, d, area, at, col) => source !== 'model' ? `<path d="${area}" fill="url(#sx-fp)"/>`
    : `<path d="${area}" fill="${col.fill}" fill-opacity=".14"/><path d="${d}" fill="none" stroke="${col.muted}" stroke-width="1.5" stroke-dasharray="2 3" stroke-linecap="round"/>` +
      `<text x="${at.x}" y="${at.y}" font-size="10.5" font-weight="600" fill="${col.muted}" stroke="${col.card}" stroke-width="3" paint-order="stroke">${MODEL_LABEL}</text>`;
  // each redraw replaces the chart's listeners (including the one on document) instead of adding more
  const rewire = o => { if (o.__ac) o.__ac.abort(); o.__ac = new AbortController(); return o.__ac.signal; };

  // the card's header: TODAY/TONIGHT on the left (unless the page shows it above the card), the profiles on the right
  const kickHtml = (label, profiles, showLabel = true) =>
    `<div class="sx-kick">${showLabel ? `<span>${esc(label)}</span>` : '<span></span>'}${profilesHeadHtml(profiles)}</div>`;

  const api = { appNow, readingsNow, pmPastSvg, kickHtml, hoursOf, lerp, shareOfLimit, fmtClock, staleWhen, tipSide, hourLabel, profilesHeadHtml, itemProfileHtml, fitLabel, rhLabelY, peakAhead, rewire };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  // ── drawing ──
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const CO2_COL = '#6f8194', PM_COL = '#7f93a6', RH_COL = '#a3aeb9';
  const MODEL_LABEL_TOP = 26;   // px: the model label's highest baseline, under the FORECAST → caption
  const MODEL_LABEL_W = 130;    // px: about how wide "PM2.5 outside · model" is at 10.5 px, for finding room over the line

  const ICON = {
    temp: '<svg class="sx-ic" viewBox="0 0 16 16" fill="none" stroke="#7d8b99" stroke-width="1.4" stroke-linecap="round"><path d="M6.5 9.4V3.2a1.5 1.5 0 0 1 3 0v6.2a3 3 0 1 1-3 0Z"/><path d="M8 7v4" stroke="#d98a1c" stroke-width="1.6"/></svg>',
    rain: '<svg class="sx-ic" viewBox="0 0 16 16"><path d="M8 2.2S4.2 6.6 4.2 9.3a3.8 3.8 0 0 0 7.6 0C11.8 6.6 8 2.2 8 2.2Z" fill="#6c7f93"/></svg>',
    Sunrise: '<svg class="sx-ic" viewBox="0 0 16 16" fill="none" stroke="#d48a1e" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12.5h12"/><path d="M4.4 12.5a3.6 3.6 0 0 1 7.2 0"/><path d="M8 6.5V1.8M6 3.8 8 1.8l2 2"/></svg>',
    Sunset: '<svg class="sx-ic" viewBox="0 0 16 16" fill="none" stroke="#d48a1e" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12.5h12"/><path d="M4.4 12.5a3.6 3.6 0 0 1 7.2 0"/><path d="M8 1.8v4.7M6 4.5l2 2 2-2"/></svg>',
    UV: '<svg class="sx-ic" viewBox="0 0 16 16" fill="none" stroke="#d48a1e" stroke-width="1.4" stroke-linecap="round"><circle cx="8" cy="8" r="2.6"/><path d="M8 1.6v1.6M8 12.8v1.6M1.6 8h1.6M12.8 8h1.6M3.5 3.5l1.1 1.1M11.4 11.4l1.1 1.1M3.5 12.5l1.1-1.1M11.4 4.6l1.1-1.1"/></svg>',
  };

  // The chart's data in axis hours.
  function prep(s) {
    const tl = s.timeline, t0 = tl.t0, h = iso => hoursOf(iso, t0);
    const pts = a => (a || []).map(([t, v]) => [h(t), v]);
    const pmItem = (s.items || []).find(i => i.id === 'pm');
    return {
      t0: h(t0), t1: h(tl.t1), now: h(tl.now), lim: tl.limits,
      co2: pts(tl.co2), rh: pts(tl.rh), pmPast: pts(tl.pm.past), pmFc: pts(tl.pm.fc), pmModel: tl.pm.source === 'model',
      cause: pmItem && pmItem.facts && pmItem.facts.cause,
      hours: tl.hours.map(x => ({ t: h(x.t), temp: x.temp, pop: x.pop, mm: x.mm })),
      uv: tl.uv.map(([a, b, m]) => ({ a: h(a), b: h(b), m })),
      sun: tl.sun.map(e => ({ t: h(e.t), kind: e.kind, s: isoClock(e.t) })),
      night: tl.night.map(([a, b]) => [h(a), h(b)]),
    };
  }

  // One panel. Each reading is drawn as a share of its own limit, so one dashed line is "the limit" for all and
  // above it is bad. CO₂ inside is a slate line with a soft fade (amber past the limit); PM2.5 outside a grey area,
  // hatched where it's forecast; under the hours the temperature and rain; night, sun and strong sun on the axis.
  function drawChart(c, w) {
    const R = w - 34, span = c.t1 - c.t0, x = t => (t - c.t0) / span * R, xn = x(c.now);
    const top = 16, P = 80, bot = top + P, card = css('--card'), warn = css('--warn'), warnFill = css('--warn-fill');
    const pm = [...c.pmPast, ...c.pmFc];
    const all = [...c.co2.map(p => p[1] / c.lim.co2), ...pm.map(p => p[1] / c.lim.pm), ...c.rh.map(p => p[1] / c.lim.rh), 1.15];
    const rmax = Math.max(...all) * 1.12, ys = r => bot - r / rmax * P, yl = ys(1);
    const path = (ps, lim) => ps.map(([t, v], i) => (i ? 'L' : 'M') + x(t).toFixed(1) + ' ' + ys(v / lim).toFixed(1)).join(' ');
    const fade = (id, col, a, b) => `<linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity="${a}"/><stop offset="1" stop-color="${col}" stop-opacity="${b}"/></linearGradient>`;
    const defs = fade('sx-fi', CO2_COL, .16, 0) + fade('sx-fw', '#d98a1c', .32, .06) + fade('sx-fp', PM_COL, .30, .12) +
      `<pattern id="sx-h" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="rgba(127,147,166,.42)" stroke-width="1.2"/></pattern>
       <pattern id="sx-hw" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="rgba(217,138,28,.10)"/><line x1="0" y1="0" x2="0" y2="5" stroke="rgba(217,138,28,.7)" stroke-width="1.4"/></pattern>
       <clipPath id="sx-above"><rect x="0" y="-10" width="${w}" height="${yl + 10}"/></clipPath>`;
    let g = `<rect x="0" y="${top}" width="${xn}" height="${P + 12}" fill="${css('--tile')}" opacity=".8"/>`;
    const lab = (xx, yy, s, col, anchor = 'start') => { g += `<text x="${xx}" y="${yy}" font-size="10.5" font-weight="600" fill="${col}" text-anchor="${anchor}" stroke="${card}" stroke-width="3" paint-order="stroke">${esc(s)}</text>`; };
    if (pm.length > 1) {
      const area = ps => `${path(ps, c.lim.pm)} L ${x(ps[ps.length - 1][0])} ${bot} L ${x(ps[0][0])} ${bot} Z`;
      if (c.pmPast.length > 1) {
        // the model's label sits over the line where there's room under the FORECAST caption, else under it
        const x0 = x(c.pmPast[0][0]), under = c.pmPast.filter(p => x(p[0]) <= x0 + MODEL_LABEL_W).map(p => ys(p[1] / c.lim.pm));
        const hi = Math.min(...under), lo = Math.max(...under);
        const ly = hi - 7 >= MODEL_LABEL_TOP ? hi - 7 : Math.min(bot - 4, lo + 15);
        g += pmPastSvg(c.pmModel ? 'model' : '', path(c.pmPast, c.lim.pm), area(c.pmPast),
          { x: (x0 + 2).toFixed(1), y: ly.toFixed(1) }, { fill: PM_COL, muted: css('--muted'), card });
      }
      const fc = c.pmPast.length ? [c.pmPast[c.pmPast.length - 1], ...c.pmFc] : c.pmFc;
      if (fc.length > 1) g += `<path d="${area(fc)}" fill="url(#sx-h)"/><path d="${area(fc)}" fill="url(#sx-hw)" clip-path="url(#sx-above)"/>`;
    }
    const line = (ps, lim, col, width) => {
      const d = path(ps, lim), a = x(ps[0][0]), b = x(ps[ps.length - 1][0]);
      g += `<path d="${d} L ${b} ${bot} L ${a} ${bot} Z" fill="url(#sx-fi)"/>`;
      g += `<path d="${d} L ${b} ${yl} L ${a} ${yl} Z" fill="url(#sx-fw)" clip-path="url(#sx-above)"/>`;
      g += `<path d="${d}" fill="none" stroke="${col}" stroke-width="${width}" stroke-linejoin="round" stroke-linecap="round"/>`;
      g += `<path d="${d}" fill="none" stroke="${warnFill}" stroke-width="${width}" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sx-above)"/>`;
    };
    if (c.rh.length > 1) line(c.rh, c.lim.rh, RH_COL, 1.6);
    if (c.co2.length > 1) line(c.co2, c.lim.co2, CO2_COL, 2.2);
    g += `<line x1="0" x2="${R}" y1="${yl}" y2="${yl}" stroke="${css('--muted')}" stroke-dasharray="3 3" opacity=".55"/>`;
    g += `<text x="${R + 4}" y="${yl + 3.5}" font-size="10" fill="${css('--faint')}">limit ↑</text>`;
    let co2LabY = null;   // where the CO₂ label sits when it's above its dot, so the humidity label can avoid it
    if (c.co2.length) {
      const [tc, vc] = c.co2[c.co2.length - 1], over = vc > c.lim.co2, y = ys(vc / c.lim.co2);
      g += `<circle cx="${x(tc)}" cy="${y}" r="3.5" fill="${over ? warnFill : css('--ink')}" stroke="${card}" stroke-width="1.5"/>`;
      const txt = `CO₂ inside ${Math.round(vc).toLocaleString('en-US')}`;
      if (over) { lab(x(tc) - 7, y - 7, txt, warn, 'end'); co2LabY = y - 7; } else lab(x(tc) + 7, y + 14, txt, css('--soft'));
    }
    if (c.rh.length) {
      const [tr, vr] = c.rh[c.rh.length - 1];
      lab(x(tr) - 7, rhLabelY(co2LabY, ys(vr / c.lim.rh)), `Humidity ${Math.round(vr)}%`, css('--soft'), 'end');
    }
    if (pm.length) {
      // label the peak in the outlook hours (a past spike stays visible, and the readout gives its value)
      const pk = peakAhead(c.pmPast, c.pmFc, c.now);
      if (pk && pk[1] > c.lim.pm) {
        const txt = `PM2.5 outside ${Math.round(pk[1])}${c.cause ? ' · ' + c.cause : ''}`, f = fitLabel(x(pk[0]), txt, R);
        lab(f.x, ys(pk[1] / c.lim.pm) - 3, txt, warn, f.anchor);
      }
      else lab(R - 2, ys(pm[pm.length - 1][1] / c.lim.pm) - 5, 'PM2.5 outside', css('--muted'), 'end');
    }
    const axisY = bot + 12;
    g += `<line x1="${xn}" x2="${xn}" y1="0" y2="${axisY}" stroke="${css('--ink')}" stroke-width="1.25"/>`;
    g += `<text x="${xn + 6}" y="9" font-size="9.5" font-weight="600" letter-spacing=".06em" fill="${css('--soft')}">FORECAST →</text>`;
    g += `<line x1="0" x2="${R}" y1="${axisY}" y2="${axisY}" stroke="${css('--line')}"/>`;
    for (const [a, b] of c.night) g += `<rect x="${x(Math.max(a, c.t0))}" y="${axisY - 2}" width="${Math.max(0, x(Math.min(b, c.t1)) - x(Math.max(a, c.t0)))}" height="4" rx="2" fill="#33475e" opacity=".55"/>`;
    for (const u of c.uv) {
      const xa = x(u.a), xb = x(u.b), xm = (xa + xb) / 2;
      g += `<rect x="${xa}" y="${axisY - 2}" width="${xb - xa}" height="4" rx="2" fill="#e8b04d" opacity=".7"/>`;
      g += `<g transform="translate(${xm} ${axisY - 11})" fill="none" stroke="#d48a1e" stroke-width="1.4" stroke-linecap="round"><circle r="9" fill="${card}" stroke="none"/><circle r="2.8"/><path d="M0-6.5v1.6M0 4.9v1.6M-6.5 0h1.6M4.9 0h1.6M-4.6-4.6l1.1 1.1M3.5 3.5l1.1 1.1M-4.6 4.6l1.1-1.1M3.5-3.5l1.1-1.1"/></g>`;
      lab(xm + 11, axisY - 7, `UV ${u.m}`, css('--muted'));
    }
    for (const e of c.sun) {
      const xe = x(e.t), arrow = e.kind === 'Sunrise' ? 'M0 -2.5V-8M-2.3 -5.8 0 -8 2.3 -5.8' : 'M0 -8V-2.5M-2.3 -4.7 0 -2.5 2.3 -4.7';
      g += `<g transform="translate(${xe} ${axisY - 1})" fill="none" stroke="#d48a1e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><title>${e.kind} ${e.s}</title><circle r="10" fill="${card}" stroke="none"/><path d="M-6.5 4.5h13"/><path d="M-3.8 4.5a3.8 3.8 0 0 1 7.6 0"/><path d="${arrow}"/></g>`;
      lab(xe + 11, axisY - 6, e.s, css('--muted'));
    }
    const rainy = c.hours.some(hh => hh.pop);
    for (const hh of c.hours) {
      const anc = Math.abs(hh.t - c.t0) < .01 ? 'start' : Math.abs(hh.t - c.t1) < .01 ? 'end' : 'middle', fut = hh.t > c.now;
      g += `<text x="${x(hh.t)}" y="${axisY + 13}" font-size="10.5" fill="${css('--faint')}" text-anchor="${anc}">${hourLabel(hh.t)}</text>`;
      if (hh.temp != null) g += `<text x="${x(hh.t)}" y="${axisY + 26}" font-size="11" font-weight="600" fill="${fut ? css('--soft') : css('--faint')}" text-anchor="${anc}">${hh.temp}°C</text>`;
      if (hh.pop) {
        const tw = `${hh.pop}%`.length * 5.6 + 10, x0 = anc === 'start' ? x(hh.t) : anc === 'end' ? x(hh.t) - tw : x(hh.t) - tw / 2;
        g += `<path transform="translate(${x0} ${axisY + 31})" d="M3.5 0C3.5 0 0 4.2 0 6.3a3.5 3.5 0 0 0 7 0C7 4.2 3.5 0 3.5 0Z" fill="#6c7f93"/>`;
        g += `<text x="${x0 + 10}" y="${axisY + 39}" font-size="10" font-weight="600" fill="${css('--soft')}">${hh.pop}%</text>`;
        g += `<text x="${x(hh.t)}" y="${axisY + 51}" font-size="10" fill="${css('--faint')}" text-anchor="${anc}">${hh.mm} mm</text>`;
      }
    }
    const height = axisY + (rainy ? 55 : 30);
    g += `<g class="sx-hv" style="display:none"><line class="sx-hvl" y1="${top - 4}" y2="${axisY}" stroke="${css('--ink')}" stroke-width="1" opacity=".35"/>
      <circle class="sx-hvc" r="4" fill="${card}" stroke-width="2"/><circle class="sx-hvp" r="4" fill="${card}" stroke-width="2"/></g>`;
    return { svg: `<svg width="${w}" height="${height}" viewBox="0 0 ${w} ${height}" style="display:block;overflow:visible" aria-hidden="true"><defs>${defs}</defs>${g}</svg>`, geo: { x, R, ys } };
  }

  // Hover with a mouse, or tap and drag on a phone: one moment, with the chart's own mark on each row.
  function wireHover(el, c, geo, signal) {
    const svg = el.querySelector('svg'), tip = el.querySelector('.sx-tip'), g = svg.querySelector('.sx-hv');
    const coarse = matchMedia('(pointer: coarse)').matches || el.clientWidth < 560;   // a narrow chart docks the readout too
    tip.classList.toggle('dock', coarse);
    const temps = c.hours.filter(hh => hh.temp != null).map(hh => [hh.t, hh.temp]);
    const show = e => {
      const r = svg.getBoundingClientRect(), px = Math.min(Math.max(e.clientX - r.left, 0), geo.R);
      const t = c.t0 + px / geo.R * (c.t1 - c.t0), fc = t > c.now + .05, past = c.pmModel ? 'Model' : 'Measured';
      const co2 = lerp(c.co2, t), rh = lerp(c.rh, t), pm = lerp([...c.pmPast, ...c.pmFc], t), temp = lerp(temps, t);
      const rain = c.hours.find(hh => hh.pop && Math.abs(hh.t - t) <= 1.5);
      const ev = c.uv.find(u => t >= u.a && t <= u.b) ? { kind: 'UV', s: 'UV ' + c.uv.find(u => t >= u.a && t <= u.b).m }
        : c.sun.find(e => Math.abs(e.t - t) <= .5);
      g.style.display = '';
      svg.querySelector('.sx-hvl').setAttribute('x1', px); svg.querySelector('.sx-hvl').setAttribute('x2', px);
      const dot = (cls, v, lim, col) => { const d = svg.querySelector(cls); if (v == null) { d.style.display = 'none'; return; }
        d.style.display = ''; d.setAttribute('cx', px); d.setAttribute('cy', geo.ys(v / lim)); d.setAttribute('stroke', v > lim ? css('--warn-fill') : col); };
      dot('.sx-hvc', co2, c.lim.co2, CO2_COL); dot('.sx-hvp', pm, c.lim.pm, '#8a97a4');
      const rows = [];
      if (co2 != null) rows.push({ sw: '<i class="sx-sw-co2"></i>', lb: 'CO₂ inside', v: Math.round(co2).toLocaleString('en-US'), u: 'ppm', over: co2 > c.lim.co2 });
      if (rh != null) rows.push({ sw: '<i class="sx-sw-rh"></i>', lb: 'Humidity inside', v: Math.round(rh) + '%', u: '', over: rh > c.lim.rh });
      if (pm != null) rows.push({ sw: `<i class="sx-sw-pm${fc ? ' fc' : ''}${pm > c.lim.pm ? ' over' : ''}"></i>`, lb: 'PM2.5 outside', v: Math.round(pm), u: 'µg/m³', over: pm > c.lim.pm });
      if (temp != null) rows.push({ sw: ICON.temp, lb: 'Temperature', v: Math.round(temp) + '°C', u: '' });
      if (rain) rows.push({ sw: ICON.rain, lb: 'Rain', v: rain.pop + '%', u: rain.mm + ' mm', rain: true });
      const evText = ev ? (ev.kind === 'UV' ? 'Strong sun, ' + ev.s : ev.kind + ' at ' + ev.s) : '';
      if (coarse) {
        tip.innerHTML = `<div class="sx-line"><span class="sx-whn"><b>${fmtClock(t)}</b><em>${fc ? 'Forecast' : past}</em></span>` +
          rows.map(x => `<span class="sx-c${x.over ? ' over' : ''}">${x.sw}${x.v}${x.u && !x.rain ? `<small>${x.u}</small>` : ''}</span>`).join('') +
          (ev ? `<span class="sx-c">${ICON[ev.kind]}${esc(ev.kind === 'UV' ? ev.s : ev.s)}</span>` : '') + '</div>';
      } else {
        tip.innerHTML = `<div class="sx-tt"><b>${fmtClock(t)}</b><span class="sx-chip${fc ? '' : ' now'}">${fc ? 'Forecast' : past}</span></div>` +
          rows.map(x => `<div class="sx-r">${x.sw}<span class="sx-lb">${x.lb}</span><span class="sx-v${x.over ? ' over' : ''}">${x.v}<small>${x.u}</small></span></div>`).join('') +
          (ev ? `<div class="sx-ev">${ICON[ev.kind]}<span>${esc(evText)}</span></div>` : '');
      }
      tip.style.display = 'block';
      if (!coarse) { const tw = tip.offsetWidth; tip.style.left = Math.max(0, tipSide(px, r.width, tw) === 'left' ? px - 16 - tw : px + 16) + 'px'; }
    };
    const hide = () => { g.style.display = 'none'; tip.style.display = 'none'; };
    el.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') show(e); }, { signal });
    el.addEventListener('pointermove', e => { if (e.pointerType === 'mouse' || e.buttons) show(e); }, { signal });
    el.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') hide(); }, { signal });
    document.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' && !el.contains(e.target)) hide(); }, { signal });
    el.__hoverAt = frac => { const r = svg.getBoundingClientRect(); show({ clientX: r.left + frac * geo.R }); };
  }

  function itemHtml(it, now, profiles) {
    const when = staleWhen(it.action, now);
    return `<div class="sx-row">
      <div class="sx-lab"><span>${it.key ? `<i class="sx-key ${it.key}${it.forecast ? ' fc' : ''}"></i>` : ''}${esc(it.label)}${it.forecast ? ' · <span class="sx-fct">forecast</span>' : ''}</span>${itemProfileHtml(it, profiles)}</div>
      <div class="sx-num">${esc(it.num)}<small>${esc(it.unit)}</small></div>
      <div class="sx-ctx">${esc(it.ctx)}</div>
      ${it.action && it.action.text ? `<div class="sx-do">${esc(it.action.text)}${when ? ` <span class="sx-when">· ${esc(when)}</span>` : ''}</div>` : ''}
    </div>`;
  }

  function renderSummary(el, s, now = appNow(), opts = {}) {
    if (!el) return false;
    // opts.profilesEl: the page shows the profile icons in the card's header strip instead of a row of their own
    const profilesEl = opts.profilesEl || null;
    if (!s || !s.timeline) { el.innerHTML = '<p class="sx-none">The summary isn’t available right now.</p>'; if (profilesEl) profilesEl.innerHTML = ''; return false; }
    if (profilesEl) profilesEl.innerHTML = profilesHeadHtml(s.profiles);
    const showLabel = opts.label !== false;
    let html = !profilesEl ? kickHtml(s.label, s.profiles, showLabel) : showLabel ? kickHtml(s.label, null) : '';
    if (s.items && s.items.length) {
      html += `<div class="sx-items n${s.items.length}">${s.items.map(it => itemHtml(it, now, s.profiles)).join('')}</div>`;
      if (s.also) html += `<div class="sx-also">${esc(s.also)}</div>`;
    } else {
      html += '<div class="sx-clear"><div class="sx-big">All clear.</div><div class="sx-sub">Nothing to do inside or out.</div></div>';
    }
    html += '<div class="sx-tl"></div>';
    el.innerHTML = html;
    const tlEl = el.querySelector('.sx-tl'), c = prep(s);
    const draw = () => {
      const { svg, geo } = drawChart(c, tlEl.clientWidth || 360);
      tlEl.innerHTML = svg + '<div class="sx-tip"></div>';
      wireHover(tlEl, c, geo, rewire(el));
    };
    draw();
    el.__redraw = draw;   // the page redraws on resize and theme change
    // one popover open at a time; a tap elsewhere closes it
    const pops = sel => [el, profilesEl].filter(Boolean).flatMap(x => [...x.querySelectorAll(sel)]);
    pops('details.sx-why').forEach(d => d.addEventListener('toggle', () => {
      if (d.open) pops('details.sx-why[open]').forEach(o => { if (o !== d) o.open = false; });
    }));
    return true;
  }
  document.addEventListener('click', e => document.querySelectorAll('details.sx-why[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; }));

  root.SummaryCard = { renderSummary, ...api };
})(typeof window !== 'undefined' ? window : globalThis);
