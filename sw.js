/* 生字泡泡離線快取（本機 svg 筆順） */
const CACHE = "char-bubble-v2-local-svg";
const PRECACHE = [
  "./index.html",
  "./sw.js",
  "./char_bubble.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" && req.method !== "HEAD") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const isLocal =
    url.pathname.endsWith("/index.html") || url.pathname.endsWith("/") ||
    url.pathname.endsWith("/sw.js") ||
    url.pathname.endsWith("/char_bubble.webmanifest") ||
    url.pathname.includes("/svg/");

  if (!isLocal) return;

  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      if (req.method === "GET") {
        const hit = await cache.match(req);
        if (hit) return hit;
      }
      try {
        const res = await fetch(req);
        if (req.method === "GET" && res && res.ok) cache.put(req, res.clone());
        return res;
      } catch (e) {
        if (req.method === "GET") {
          const hit = await cache.match(req);
          if (hit) return hit;
        }
        throw e;
      }
    })
  );
});
