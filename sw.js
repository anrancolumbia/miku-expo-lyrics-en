// Miku Expo lyrics viewer — offline cache
// Strategy: cache-first for app shell + song data. Bump VERSION to force refresh.

const VERSION = 'miku-en-v1-2026-04-22';
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './pjsk.webp',
  './data/setlist.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    // Shell files first (required)
    await cache.addAll(SHELL);
    // Then proactively cache all songs across all setlists so no network needed at concert
    try {
      const resp = await fetch('./data/setlist.json', { cache: 'no-cache' });
      const data = await resp.json();
      const ids = new Set();
      (data.setlists || []).forEach(sl => (sl.songs || []).forEach(id => ids.add(id)));
      const songUrls = [...ids].map(id => `./data/songs/${id}.json`);
      await cache.addAll(songUrls);
    } catch (err) {
      console.warn('[sw] pre-cache songs failed', err);
    }
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)));
    self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // Only handle same-origin GET requests.
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  e.respondWith((async () => {
    const cached = await caches.match(e.request);
    if (cached) {
      // Revalidate in background (stale-while-revalidate)
      fetch(e.request).then(resp => {
        if (resp && resp.ok) {
          caches.open(VERSION).then(c => c.put(e.request, resp.clone()));
        }
      }).catch(() => {});
      return cached;
    }
    try {
      const resp = await fetch(e.request);
      if (resp && resp.ok) {
        const c = await caches.open(VERSION);
        c.put(e.request, resp.clone());
      }
      return resp;
    } catch (err) {
      // Offline and not cached — return a minimal fallback for JSON/HTML.
      if (e.request.headers.get('accept')?.includes('application/json')) {
        return new Response('{"error":"offline"}', {
          headers: { 'Content-Type': 'application/json' }
        });
      }
      return new Response('Offline', { status: 503 });
    }
  })());
});
