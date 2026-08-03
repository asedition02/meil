/* Meil service worker — uygulama kabuğunu önbelleğe alır (PWA).
   API istekleri her zaman ağa gider; kabuk dosyaları önce önbellekten gelir. */
const CACHE = "meil-shell-v5";
const SHELL = ["/app", "/style.css", "/app.js", "/manifest.json",
               "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api") || url.pathname.startsWith("/share")) {
    return; // API ve paylaşım her zaman ağdan
  }
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(
      (hit) =>
        hit ||
        fetch(e.request).then((res) => {
          if (res.ok && url.origin === location.origin) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
          }
          return res;
        })
    )
  );
});

/* Web Push: sunucudan (app/push_notify.py) gelen bildirimi göster.
   Yük her zaman {title, body, url} biçiminde JSON'dur. */
self.addEventListener("push", (e) => {
  let data = { title: "Meil", body: "Yeni bir bildiriminiz var.", url: "/app" };
  if (e.data) {
    try { data = { ...data, ...e.data.json() }; } catch { data.body = e.data.text() || data.body; }
  }
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: data.url || "/app" },
    })
  );
});

/* Bildirime tıklanınca: açık bir sekme varsa öne getir, yoksa yeni sekme aç. */
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/app";
  e.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((all) => {
      for (const c of all) {
        if (c.url.includes(url) && "focus" in c) return c.focus();
      }
      if (all.length > 0 && "focus" in all[0]) { all[0].focus(); return all[0].navigate(url); }
      return clients.openWindow(url);
    })
  );
});
