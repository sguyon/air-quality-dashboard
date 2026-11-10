import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Exercise the real worker cache path: a setup form must not be saved for offline reuse.
test('the service worker never caches a no-store setup page', async () => {
  const stored = [];
  const context = vm.createContext({
    self: { addEventListener() {} }, URL, Request, Response,
    caches: { open: async () => ({ put: async (...args) => stored.push(args) }) },
  });
  vm.runInContext(readFileSync(new URL('../sw.js', import.meta.url), 'utf8'), context);
  context.setup = new Response('<form>one-use value</form>', { headers: { 'Cache-Control': 'no-store' } });
  vm.runInContext('putInCache("/", setup)', context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(stored.length, 0);
  context.normal = new Response('readings');
  vm.runInContext('putInCache("/", normal)', context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(stored.length, 1);
});


test('installation also leaves a no-store setup page out of the shell cache', async () => {
  const stored = [];
  const listeners = {};
  const cache = {
    add: async url => stored.push(url),
    put: async (url) => stored.push(url),
  };
  const context = vm.createContext({
    self: { addEventListener: (name, callback) => { listeners[name] = callback; }, skipWaiting() {} },
    URL, Request, Response,
    caches: { open: async () => cache },
    fetch: async url => new Response('shell', { headers: url === '/' ? { 'Cache-Control': 'no-store' } : {} }),
  });
  vm.runInContext(readFileSync(new URL('../sw.js', import.meta.url), 'utf8'), context);
  let done;
  listeners.install({ waitUntil: promise => { done = promise; } });
  await done;
  assert.equal(stored.includes('/'), false);
  assert.equal(stored.length, 2);
});


test('activation removes v5 pages and keeps the new worker cache', async () => {
  const listeners = {};
  const removed = [];
  const opened = [];
  const context = vm.createContext({
    self: { addEventListener: (name, callback) => { listeners[name] = callback; }, clients: { claim() {} } },
    caches: {
      open: async name => { opened.push(name); return { put: async () => {} }; },
      keys: async () => ['aq-dashboard-v5', ...opened],
      delete: async name => { removed.push(name); },
    },
    URL, Request, Response,
  });
  vm.runInContext(readFileSync(new URL('../sw.js', import.meta.url), 'utf8'), context);
  context.page = new Response('new page');
  await vm.runInContext('putInCache("/", page)', context);
  let done;
  listeners.activate({ waitUntil: promise => { done = promise; } });
  await done;
  assert.deepEqual(removed, ['aq-dashboard-v5']);
  assert.equal(opened.length, 1);
  assert.equal(removed.includes(opened[0]), false);
});
