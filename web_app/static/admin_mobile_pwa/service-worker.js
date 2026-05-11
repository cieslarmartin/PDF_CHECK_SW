/* Privátní Service Worker pro /admin/m-dashboard (registrace jen v mobile_app.html) */

const CACHE_NAME = 'dokucheck-admin-mobile-v1';
const APP_SHELL = [
  '/admin/m-dashboard',
  '/admin/m-dashboard/manifest.json',
  '/static/logo/dokucheck-icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k))))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Scope jen pro mobile dashboard
  if (!url.pathname.startsWith('/admin/m-dashboard')) {
    return;
  }

  // API nikdy necachovat
  if (url.pathname.startsWith('/admin/api/mobile')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // App shell: cache-first s network fallback
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

