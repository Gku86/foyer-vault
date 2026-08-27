self.addEventListener("push", (event) => {
  let payload = { title: "HomeBudget", body: "", url: "/" };
  try {
    if (event.data) payload = { ...payload, ...event.data.json() };
  } catch {
    try {
      payload.body = event.data ? event.data.text() : "";
    } catch {
      /* empty */
    }
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "HomeBudget", {
      body: payload.body || "",
      icon: "/favicon.svg",
      badge: "/favicon.svg",
      data: { url: payload.url || "/" },
    }),
  );
});

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
