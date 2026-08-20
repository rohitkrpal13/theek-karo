/* Theek Karo offline shell — minimal, dependency-free service worker.
   Network-first for pages/API (freshness matters), cache-first for static
   assets, with an offline fallback to the cached home page. */

const VERSION = "tk-v1";
const STATIC_CACHE = `${VERSION}-static`;
const SHELL_CACHE = `${VERSION}-shell`;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(["/en", "/en/explore"]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key.startsWith("tk-v") && key !== VERSION).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request).catch(() => caches.match("/en")));
    return;
  }

  if (url.origin !== self.location.origin) return;

  if (/\.(png|jpe?g|webp|svg|woff2?|ico)$/.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
            return response;
          }),
      ),
    );
    return;
  }

  event.respondWith(
    fetch(request).then((response) => {
      if (response.ok && request.mode === "navigate") {
        const copy = response.clone();
        caches.open(SHELL_CACHE).then((cache) => cache.put("/en", copy));
      }
      return response;
    }).catch(() => caches.match(request).then((cached) => cached || caches.match("/en"))),
  );
});