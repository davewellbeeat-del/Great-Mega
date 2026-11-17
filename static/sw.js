// Service worker: makes the site installable and keeps the look available offline.
// It NEVER caches API data or pages: balances, bots and activity are always live.
const VERSION = "gm-v2-1";
const SHELL = [
  "/static/css/style.css?v=2",
  "/static/js/theme.js?v=2",
  "/static/js/app.js?v=2",
  "/static/icons/icon-192.png",
  "/offline",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;                    // always live

  if (req.mode === "navigate") {                                   // pages: network, else offline notice
    event.respondWith(fetch(req).catch(() => caches.match("/offline")));
    return;
  }

  if (url.pathname.startsWith("/static/")) {                       // styles, scripts, icons: fast + refresh
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(VERSION).then((cache) => cache.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});
