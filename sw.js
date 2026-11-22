const APP_CACHE = 'absensi-app-v13';
const AI_MODELS_CACHE = 'absensi-ai-models-v1';
const FOTO_ACUAN_CACHE = 'absensi-foto-acuan-v1';
const DAFTAR_CACHE_AKTIF = [APP_CACHE, AI_MODELS_CACHE, FOTO_ACUAN_CACHE];

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(async (cacheNames) => {
            const aiCache = await caches.open(AI_MODELS_CACHE);
            const fotoCache = await caches.open(FOTO_ACUAN_CACHE);

            for (const oldName of cacheNames) {
                if (!DAFTAR_CACHE_AKTIF.includes(oldName)) {
                    try {
                        const oldCache = await caches.open(oldName);
                        const requests = await oldCache.keys();
                        for (const req of requests) {
                            if (req.url.includes('/models/')) {
                                const res = await oldCache.match(req);
                                if (res) await aiCache.put(req, res);
                            } else if (req.url.includes('/foto_acuan/')) {
                                const res = await oldCache.match(req);
                                if (res) await fotoCache.put(req, res);
                            }
                        }
                    } catch (e) {}
                    await caches.delete(oldName);
                }
            }
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = event.request.url;

    // 1. Wadah Permanen Otak AI Wajah (./models)
    if (url.includes('/models/')) {
        event.respondWith(
            caches.open(AI_MODELS_CACHE).then(async (cache) => {
                const cached = await cache.match(event.request);
                if (cached) return cached;
                const networkRes = await fetch(event.request);
                if (networkRes && networkRes.status === 200) {
                    cache.put(event.request, networkRes.clone());
                }
                return networkRes;
            })
        );
        return;
    }

    // 2. Wadah Permanen Foto Acuan Profil ASN (foto_acuan/)
    if (url.includes('supabase.co') && url.includes('/foto_acuan/')) {
        event.respondWith(
            caches.open(FOTO_ACUAN_CACHE).then(async (cache) => {
                const cached = await cache.match(event.request);
                if (cached) return cached;
                const networkRes = await fetch(event.request);
                if (networkRes && networkRes.status === 200) {
                    cache.put(event.request, networkRes.clone());
                }
                return networkRes;
            })
        );
        return;
    }

    // 3. Abaikan request database & upload foto sidak Supabase
    if (url.includes('supabase.co')) {
        return;
    }

    // 4. File tampilan utama (index.html, manifest, ikon)
    event.respondWith(
        fetch(event.request)
            .then((networkRes) => {
                if (event.request.method === 'GET' && networkRes && networkRes.status === 200) {
                    const resClone = networkRes.clone();
                    caches.open(APP_CACHE).then((cache) => cache.put(event.request, resClone));
                }
                return networkRes;
            })
            .catch(() => caches.match(event.request))
    );
});
