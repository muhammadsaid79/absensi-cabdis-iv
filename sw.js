const CACHE_NAME = 'absensi-pwa-v4'; 

self.addEventListener('install', (event) => {
    // Memaksa Service Worker baru untuk langsung mengambil alih
    self.skipWaiting(); 
});

self.addEventListener('activate', (event) => {
    // LOGIKA PENTING: Menghapus cache versi lama secara otomatis
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Menghapus cache lama', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    // 1. ABAIKAN REQUEST KE SUPABASE
    // Jika URL mengandung kata "supabase.co", biarkan lewat begitu saja.
    // Service worker tidak akan menyentuh atau mencampuri request database Anda.
    if (event.request.url.includes('supabase.co')) {
        return; 
    }

    // 2. STRATEGI UNTUK FILE TAMPILAN (GITHUB PAGES)
    // Ambil tampilan terbaru dari GitHub, jika internet putus, tampilkan versi cache
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
