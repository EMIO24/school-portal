const CACHE_NAME = 'parent-portal-v1';
const OFFLINE_URLS = ['/parent/dashboard', '/static/js/main.chunk.js'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(OFFLINE_URLS).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const { request } = event;

  // Never cache auth/OTP endpoints — always go to network
  if (
    request.url.includes('/api/auth/parent/otp') ||
    request.url.includes('/api/auth/')
  ) {
    return; // browser handles with no SW interception
  }

  // Cache parent dashboard data endpoints for offline use
  if (
    request.url.includes('/api/auth/parent/children') ||
    request.url.includes('/api/auth/parent/dashboard')
  ) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Navigation: serve cached page on offline
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/parent/dashboard') || caches.match('/'))
    );
  }
});
