self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("push", (event) => {
  event.waitUntil(showPush(event));
});

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(refreshSubscription(event));
});

async function showPush(event) {
  let payload = { title: "HomeBudget", body: "Nouvelle notification", url: "/" };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch {
    try {
      const text = event.data ? event.data.text() : "";
      if (text) payload.body = text;
    } catch {
      /* empty */
    }
  }
  const title = payload.title || "HomeBudget";
  const body = payload.body || "Nouvelle notification";
  const url = payload.url || "/";
  try {
    await self.registration.showNotification(title, {
      body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url },
      tag: "homebudget",
      renotify: true,
    });
  } catch {
    await self.registration.showNotification(title, { body, data: { url } });
  }
}

async function refreshSubscription(event) {
  try {
    const oldSub = event.oldSubscription;
    const applicationServerKey = oldSub?.options?.applicationServerKey;
    if (applicationServerKey) {
      await self.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey,
      });
    }
  } catch {
    /* the page re-registers on next open */
  }
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of windows) {
    try {
      client.postMessage({ type: "PUSH_RESUBSCRIBE" });
    } catch {
      /* ignore */
    }
  }
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          client.focus();
          if ("navigate" in client) client.navigate(target);
          return;
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
