const CACHE_NAME = 'wheke-food-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// ===== NOTIFICATIONS PUSH =====

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data.json();
  } catch (e) {
    data = { title: "Whèkè Food", body: event.data ? event.data.text() : "Nouveauté disponible !" };
  }

  const options = {
    body: data.body || "Un nouveau plat vient d'être ajouté !",
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    vibrate: [100, 50, 100],
    data: { url: data.url || "/" }
  };

  event.waitUntil(
    self.registration.showNotification(data.title || "Whèkè Food", options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url || "/")
  );
});