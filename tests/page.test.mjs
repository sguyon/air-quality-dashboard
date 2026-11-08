// The page's wiring: index.html uses the new summary card, and every bare function call in app.js is defined
// in one of the page's scripts or is a browser global.
// Found by the branch review: two calls to deleted functions (renderAgenda, renderActionVis) broke the refresh loop.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const strip = s => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:\\])\/\/.*$/gm, '$1')
  .replace(/'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"/g, "''");
const files = ['static/app.js', 'static/sky.js', 'static/summary.js'].map(f => strip(readFileSync(new URL(f, root), 'utf8')));
const all = files.join('\n');

const declared = new Set();
const add = x => x && declared.add(x.replace(/^\.\.\./, '').replace(/=.*/, ''));
for (const m of all.matchAll(/\b(?:function\s*\*?\s*|const\s+|let\s+|var\s+|class\s+)([A-Za-z_$][\w$]*)/g)) add(m[1]);
for (const m of all.matchAll(/\b(?:const|let|var)\s*[{[]([^=]*?)[}\]]\s*=/g)) m[1].split(/[,:\s]+/).forEach(add);
for (const m of all.matchAll(/function\s*[\w$]*\s*\(([^)]*)\)|\(([^()]*)\)\s*=>|([A-Za-z_$][\w$]*)\s*=>/g)) (m[1] ?? m[2] ?? m[3]).split(/[,\s{}=[\]]+/).forEach(add);
for (const m of all.matchAll(/[{,]\s*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/g)) add(m[1]);   // method shorthand: get() { … }

const GLOBALS = new Set(('if for while switch catch return typeof new function await async import require super ' +
  'setTimeout clearTimeout setInterval clearInterval requestAnimationFrame fetch getComputedStyle matchMedia ' +
  'Number String Boolean Object Array Date Math JSON Promise Set Map WeakMap Symbol Proxy Reflect Error RegExp ' +
  'parseFloat parseInt isNaN isFinite encodeURIComponent decodeURIComponent structuredClone queueMicrotask btoa atob ' +
  'Intl URL URLSearchParams IntersectionObserver ResizeObserver MutationObserver PointerEvent alert confirm ' +
  // not code: CSS functions inside template strings, and a word inside a regex
  'calc var Yesterday').split(' '));

test('app.js calls only functions that exist', () => {
  const missing = new Set();
  for (const m of files[0].matchAll(/(^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/g)) if (!declared.has(m[2]) && !GLOBALS.has(m[2])) missing.add(m[2]);
  assert.deepEqual([...missing], []);
});

test('the page uses the new summary card, not the old headline and need cards', async () => {
  const { readFile } = await import('node:fs/promises');
  const html = await readFile(new URL('index.html', root), 'utf8');
  assert.match(html, /id="summary"/);
  assert.doesNotMatch(html, /id="s-cards"/);
  assert.doesNotMatch(html, /id="lead"/);
});
