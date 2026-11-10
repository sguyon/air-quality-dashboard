// Capture a page with headless Chrome once it is fully drawn. Used by scripts/screenshot.sh.
//
//   node scripts/screenshot.mjs <chrome path> <url> <out.png> <profile dir> [options]
//     --viewport WxH     window size in CSS pixels (default 1440x900); under 768 wide it is a phone (touch, mobile)
//     --dpr N            device pixel ratio (default 1)
//     --first-screen     capture the window only (default: the whole page)
//     --theme light|dark the dashboard's theme in ?shot mode (sets ?shot=dark and the system preference)
//     --transparent      no default white behind the page (for scripts/hero.html)
//
// Ready means: the dashboard's summary is drawn, nothing is updating or loading, the monitor cards are in,
// fonts are loaded and, for the whole page, the map has drawn (or said it can't). A page can define
// window.__shotReady() to replace that check (scripts/hero.html does).
import { spawn } from 'node:child_process';
import { writeFile } from 'node:fs/promises';

const args = process.argv.slice(2);
const [chromePath, rawUrl, out, profile] = args;
const flag = name => args.includes(name);
const opt = (name, dflt) => { const i = args.indexOf(name); return i > 0 && args[i + 1] ? args[i + 1] : dflt; };
const [W, H] = opt('--viewport', '1440x900').split('x').map(Number);
const dpr = Number(opt('--dpr', '1'));
const firstScreen = flag('--first-screen');
const theme = opt('--theme', 'light');
const mobile = W < 768;
if (!chromePath || !rawUrl || !out || !profile || !W || !H || !dpr || !['light', 'dark'].includes(theme)) {
  console.error('usage: node screenshot.mjs <chrome> <url> <out.png> <profile> [--viewport WxH] [--dpr N] [--first-screen] [--theme light|dark] [--transparent]');
  process.exit(2);
}
// the dark theme in ?shot mode is ?shot=dark (index.html reads it before first paint)
const url = theme === 'dark' ? rawUrl.replace(/([?&])shot\b(=\w+)?/, '$1shot=dark') : rawUrl;

const port = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn(chromePath, ['--headless=new', '--hide-scrollbars', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
  '--allow-file-access-from-files', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, `--window-size=${W},${H}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
// Ask Chrome to close itself (Browser.close) before killing it: on macOS a killed Chrome shows a "quit unexpectedly" dialog.
let closeBrowser = null;
const quit = async code => {
  const exited = new Promise(r => chrome.once('exit', r));
  if (closeBrowser) await Promise.race([closeBrowser().catch(() => {}), sleep(1000)]);
  await Promise.race([exited, sleep(3000)]);
  if (chrome.exitCode === null && chrome.signalCode === null) { chrome.kill(); await Promise.race([exited, sleep(5000)]); }
  process.exit(code);
};   // gone before the next one starts
const fail = msg => { console.error(msg); return quit(1); };
try {
  let target;
  for (let i = 0; i < 100 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t => t.type === 'page'); } catch {}
  }
  if (!target) await fail('Chrome did not start');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
  let id = 0; const waiting = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } };
  const send = (method, params = {}) => new Promise(ok => { const n = ++id; waiting.set(n, ok); ws.send(JSON.stringify({ id: n, method, params })); });
  closeBrowser = () => send('Browser.close');
  const evaluate = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
  const metrics = h => send('Emulation.setDeviceMetricsOverride', { width: W, height: h, deviceScaleFactor: dpr, mobile });

  // the whole page starts in a tall window, so everything that waits to be on screen (the map) draws
  await metrics(firstScreen ? H : 4000);
  if (mobile) await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: theme }, { name: 'prefers-reduced-motion', value: 'no-preference' }] });
  if (flag('--transparent')) await send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  await send('Page.enable');
  await send('Page.navigate', { url });

  const ready = `(() => {
    if (window.__shotReady) return window.__shotReady();
    if (document.fonts.status !== 'loaded') return false;
    const card = document.querySelector('section.sum-card'), sx = document.getElementById('summary');
    const summary = !!sx && !!sx.querySelector('.sx-tl svg') && !sx.querySelector('.sx-none');   // drawn, not "Reading the air…"
    const idle = card && card.getAttribute('aria-busy') !== 'true' && !card.dataset.phase && !document.querySelector('.loading, .ag-skel');
    const monitors = document.querySelectorAll('#monitors > *').length > 0;
    const map = ${firstScreen} || !!document.body.dataset.mapReady;   // the map is far below the first screen
    return summary && idle && monitors && map;
  })()`;
  let ok = false;
  for (let i = 0; i < 120 && !ok; i++) { await sleep(500); ok = await evaluate(ready); }
  if (!ok) await fail(`The page did not finish drawing in 60 s: ${url}`);
  await sleep(2500);   // let the intro animation finish

  let h = H;
  if (!firstScreen) {
    h = await evaluate("Math.ceil(document.querySelector('.page').getBoundingClientRect().bottom + scrollY + 32)");   // the page's content, not the tall window
    await metrics(h);
    await sleep(800);
  }
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: !firstScreen, clip: { x: 0, y: 0, width: W, height: h, scale: 1 } });
  if (!shot.result) await fail(`Chrome could not capture: ${JSON.stringify(shot.error)}`);
  await writeFile(out, Buffer.from(shot.result.data, 'base64'));
  console.log(`${W}x${h}@${dpr}`);
  ws.close(); await quit(0);
} catch (e) { await fail(String(e)); }
