// sw.js
// Service Worker: makes the site work offline for rural users on unreliable
// connections. Two different strategies for two different kinds of content:
//
// 1. APP SHELL (the HTML/CSS/JS that makes the UI itself) - cached on install,
//    served from cache FIRST so the app opens instantly even with zero signal,
//    with a background refresh to pick up updates for next time.
//
// 2. LIVE DATA (crop options, the public worker feed, etc.) - tried over the
//    NETWORK first, since this data changes and should be fresh whenever
//    possible; only falls back to the last cached copy if the network fails.
//
// Anything that changes real data (POST/PUT/DELETE - submitting a prediction,
// registering, applying, etc.) is deliberately left alone here and goes
// straight to the network, since caching a "submit" doesn't make sense -
// script.js's existing safeFetch() already shows a clear error if that fails.

const CACHE_NAME = "smart-village-v1"; // bump this string whenever the app shell changes, to bust old caches

// The core files needed to draw the UI itself, with no network at all
const APP_SHELL_FILES = [
    "/",
    "/style.css",
    "/script.js",
    "/translations.js",
    "/manifest.json",
];

// API routes worth remembering for offline viewing (all are simple GETs with
// no personal/sensitive data - safe to keep a local copy of)
const CACHEABLE_API_PATHS = ["/options", "/workers", "/employment/stats"];


// ---------- Install: pre-cache the app shell ----------

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(APP_SHELL_FILES);
        })
    );
    self.skipWaiting(); // activate this new version immediately, don't wait for old tabs to close
});


// ---------- Activate: clean up any old-versioned caches ----------

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (cacheNames) {
            return Promise.all(
                cacheNames
                    .filter(function (name) { return name !== CACHE_NAME; })
                    .map(function (name) { return caches.delete(name); })
            );
        })
    );
    self.clients.claim(); // take control of any already-open tabs right away
});


// ---------- Fetch: decide how to answer each request ----------

self.addEventListener("fetch", function (event) {
    const request = event.request;
    const url = new URL(request.url);

    // Only handle GET requests from our own origin - never intercept POST/PUT/
    // DELETE (those need a live server, caching them would be actively wrong),
    // and never intercept requests to other origins (like the Gemini/weather
    // APIs, which the backend calls server-side anyway, not the browser).
    if (request.method !== "GET" || url.origin !== self.location.origin) {
        return;
    }

    const isCacheableApiCall = CACHEABLE_API_PATHS.some(function (path) {
        return url.pathname === path;
    });

    if (isCacheableApiCall) {
        event.respondWith(networkFirstThenCache(request));
    } else {
        event.respondWith(cacheFirstThenNetwork(request));
    }
});


// Network-first: try the real thing, fall back to the last cached copy if offline
async function networkFirstThenCache(request) {
    try {
        const networkResponse = await fetch(request);
        const cache = await caches.open(CACHE_NAME);
        cache.put(request, networkResponse.clone()); // save this fresh copy for next time we're offline
        return networkResponse;
    } catch (networkError) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) return cachedResponse;
        throw networkError; // nothing cached either - let the page's own error handling take over
    }
}


// Cache-first: show the app instantly, then quietly refresh the cache for next time
async function cacheFirstThenNetwork(request) {
    const cachedResponse = await caches.match(request);

    const networkFetch = fetch(request)
        .then(function (networkResponse) {
            caches.open(CACHE_NAME).then(function (cache) {
                cache.put(request, networkResponse.clone());
            });
            return networkResponse;
        })
        .catch(function () {
            return cachedResponse; // network failed - if we had a cached copy, this is the fallback
        });

    return cachedResponse || networkFetch;
}