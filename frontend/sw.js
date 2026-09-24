const CACHE_NAME = "smart-village-v1";
const APP_SHELL_FILES = ["/", "/style.css", "/script.js", "/translations.js", "/manifest.json"];
const CACHEABLE_API_PATHS = ["/options", "/workers", "/employment/stats"];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(async function (cache) {
            for (const file of APP_SHELL_FILES) {
                try {
                    await cache.add(file);
                } catch (error) {
                    console.error("[SW] FAILED to cache:", file, error);
                }
            }
        })
    );
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (cacheNames) {
            return Promise.all(cacheNames.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)));
        })
    );
    self.clients.claim();
});

self.addEventListener("fetch", function (event) {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== "GET" || url.origin !== self.location.origin) return;

    const isCacheableApiCall = CACHEABLE_API_PATHS.some(p => url.pathname === p);
    event.respondWith(isCacheableApiCall ? networkFirstThenCache(request) : cacheFirstThenNetwork(request));
});

async function networkFirstThenCache(request) {
    try {
        const networkResponse = await fetch(request);
        const cache = await caches.open(CACHE_NAME);
        cache.put(request, networkResponse.clone());
        return networkResponse;
    } catch (networkError) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) return cachedResponse;
        throw networkError;
    }
}

async function cacheFirstThenNetwork(request) {
    const cachedResponse = await caches.match(request);
    const networkFetch = fetch(request)
        .then(function (networkResponse) {
            caches.open(CACHE_NAME).then(cache => cache.put(request, networkResponse.clone()));
            return networkResponse;
        })
        .catch(function () { return cachedResponse; });
    return cachedResponse || networkFetch;
}
