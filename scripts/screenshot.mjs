// Capture the whole dashboard page with headless Chrome, waiting until the page is fully drawn
// (summary in, map tiles drawn, intro animation over). Used by scripts/screenshot.sh.
// node scripts/screenshot.mjs <chrome path> <url> <out.png> <profile dir>
import { spawn } from 'node:child_process';
const [chromePath, url, out, profile] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn(chromePath, ['--headless=new', '--hide-scrollbars', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, '--window-size=1440,900', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fail = msg => { console.error(msg); chrome.kill(); process.exit(1); };
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t => t.type === 'page'); } catch {}
  }
  if (!target) fail('Chrome did not start');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
  let id = 0; const waiting = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } };
  const send = (method, params = {}) => new Promise(ok => { const n = ++id; waiting.set(n, ok); ws.send(JSON.stringify({ id: n, method, params })); });
  const evaluate = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.result?.value;
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 4000, deviceScaleFactor: 1, mobile: false });   // tall, so everything that waits for the screen draws
  await send('Page.enable');
  await send('Page.navigate', { url });
  // ready: the advice cards are in, nothing is updating, and the map has drawn (or said it can't)
  const ready = `(() => document.querySelectorAll('#s-cards .n-card').length > 0 && !document.querySelector('.ag-skel')
    && document.querySelector('section.ai')?.getAttribute('aria-busy') !== 'true' && !!document.body.dataset.mapReady)()`;
  let ok = false;
  for (let i = 0; i < 120 && !ok; i++) { await sleep(500); ok = await evaluate(ready); }
  if (!ok) fail('The page did not finish drawing in 60 s');
  await sleep(2500);   // let the intro animation finish
  const h = await evaluate("Math.ceil(document.querySelector('.page').getBoundingClientRect().bottom + scrollY + 32)");   // the page's content, not the tall window
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: h, deviceScaleFactor: 1, mobile: false });
  await sleep(800);
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: 1440, height: h, scale: 1 } });
  const { writeFile } = await import('node:fs/promises');
  await writeFile(out, Buffer.from(shot.result.data, 'base64'));
  console.log(`${h}`);
  ws.close(); chrome.kill(); process.exit(0);
} catch (e) { fail(String(e)); }
