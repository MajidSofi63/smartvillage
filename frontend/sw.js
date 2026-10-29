const CACHE_NAME = "smart-village-v4";
const APP_SHELL_FILES = ["/", "/style.css", "/script.js", "/translations.js", "/manifest.json"];
const CACHEABLE_API_PATHS = ["/api/districts", "/api/seasons", "/workers", "/employment/stats"];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async function (cache) {
      for (const file of APP_SHELL_FILES) {
        try { await cache.add(file); } catch (error) { console.error("[SW] FAILED to cache:", file, error); }
      }
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)));
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  const isApi = CACHEABLE_API_PATHS.some(p => url.pathname === p);
  event.respondWith(isApi ? networkFirstThenCache(request) : cacheFirstThenNetwork(request));
});

async function networkFirstThenCache(request) {
  try {
    const res = await fetch(request);
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, res.clone());
    return res;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirstThenNetwork(request) {
  const cached = await caches.match(request);
  const networkFetch = fetch(request)
    .then(function (res) {
      caches.open(CACHE_NAME).then(cache => cache.put(request, res.clone()));
      return res;
    })
    .catch(function () { return cached; });
  return cached || networkFetch;
}
