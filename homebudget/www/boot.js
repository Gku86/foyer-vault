window.__HB_STATIC__ = true;
(function () {
  var m = String(location.pathname || "").match(/^(\/api\/hassio_ingress\/[^/]+)/);
  window.__HB_BASE__ = window.__HB_BASE__ || (m ? m[1] : "");
})();
window.onerror = function (msg, src, line) {
  var el = document.getElementById("app");
  if (el) el.textContent = "Erreur HomeBudget : " + msg + " (" + (src || "") + ":" + line + ")";
};
window.addEventListener("unhandledrejection", function (ev) {
  var el = document.getElementById("app");
  if (el) el.textContent = "Erreur HomeBudget : " + ((ev.reason && ev.reason.message) || ev.reason);
});
