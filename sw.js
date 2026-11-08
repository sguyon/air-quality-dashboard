// v5: the manifest and icons are network-first. v4 kept the manifest cache-first under a fixed cache name,
// so installed phones never saw a new manifest (an old one with an SVG icon gave iOS a letter icon).
// v4: the page's CSS and JS moved to /static/, with a ?v=<content hash> the server adds.
// v3: pages are network-first (v2 served a cached page until the cache name changed),
// only GET responses are cached, and history is cached once per monitor.
const CACHE_NAME = 'aq-dashboard-v5';
const STATIC_ASSETS = [
  '/',
  'https://cdn.jsdelivr.net/npm/chart.js@4',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
];
const CROSS_ORIGIN_OK = ['fonts.googleapis.com', 'fonts.gstatic.com', 'cdn.jsdelivr.net'];

// Install: cache the shell. A failed asset does not block installation.
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => Promise.allSettled(STATIC_ASSETS.map((url) => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

// Activate: remove older caches.
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

// History requests carry from/to times, so they never repeat. Cache them under the monitor's path only,
// which keeps one copy per monitor and lets the page find it offline.
function cacheKey(request, url) {
  if (url.pathname.startsWith('/api/history/')) return new Request(url.origin + url.pathname);
  return request;
}

function putInCache(key, response) {
  if (!response || !response.ok) return;
  const copy = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(key, copy)).catch(() => {});
}

// Network first, then the last cached copy.
function networkFirst(request, key, offlineResponse) {
  return fetch(request)
    .then((response) => { putInCache(key, response); return response; })
    .catch(() => caches.match(key).then((cached) => cached || offlineResponse()));
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  // The Cache API only stores GET. POST /api/analyze goes straight to the network;
  // the page keeps its last summary in localStorage for offline use.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;
  if (!sameOrigin && !CROSS_ORIGIN_OK.includes(url.hostname)) return;

  if (sameOrigin && url.pathname.startsWith('/api/')) {
    const key = cacheKey(request, url);
    event.respondWith(networkFirst(request, key, () => new Response(
      JSON.stringify({ error: 'Offline, and no earlier copy of this data.' }),
      { status: 503, statusText: 'Service Unavailable', headers: { 'Content-Type': 'application/json' } }
    )));
    return;
  }

  // Pages: network first, so a new deploy shows on the next visit.
  if (request.mode === 'navigate' || request.destination === 'document') {
    event.respondWith(networkFirst(request, request, () => caches.match('/').then((page) => page || Response.error())));
    return;
  }

  // Manifest and icons: network first, so a new icon reaches installed phones.
  if (sameOrigin && (url.pathname === '/manifest.json' || url.pathname.startsWith('/static/icons/') || /^\/(apple-touch-icon[\w-]*\.png|favicon\.ico)$/.test(url.pathname))) {
    event.respondWith(networkFirst(request, request, () => Response.error()));
    return;
  }

  // Our CSS and JS: the URL carries a content hash, so cache first is safe.
  // Storing a new version removes the older copies of the same file.
  if (sameOrigin && url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.keys().then((keys) => Promise.all(
          keys.filter((k) => new URL(k.url).pathname === url.pathname && k.url !== request.url).map((k) => cache.delete(k))
        )).then(() => cache.put(request, copy))).catch(() => {});
      }
      return response;
    })));
    return;
  }

  // Fonts and CDN scripts: cache first.
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok || response.type === 'opaque') {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).catch(() => {});
      }
      return response;
    }))
  );
});
