const CACHE_NAME = 'absensi-pwa-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Jalankan permintaan jaringan secara normal
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
