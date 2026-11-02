// Shared interface bits: toast messages and the centered confirm popup.
(function () {
  "use strict";

  // ---------- toasts ----------
  function dismiss(toast) {
    toast.classList.add("leaving");
    setTimeout(function () { toast.remove(); }, 220);
  }

  function enhance(toast) {
    var close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "Dismiss message");
    close.textContent = "\u00d7";
    close.addEventListener("click", function () { dismiss(toast); });
    toast.appendChild(close);
    // success and info messages fade away; errors stay until closed
    if (!toast.classList.contains("toast-error")) {
      setTimeout(function () { dismiss(toast); }, 4500);
    }
  }

  function toast(message, type) {
    var box = document.getElementById("toasts");
    if (!box) return;
    var node = document.createElement("div");
    node.className = "toast toast-" + (type === "success" || type === "error" ? type : "info");
    node.setAttribute("role", "status");
    var text = document.createElement("span");
    text.className = "toast-text";
    text.textContent = message;
    node.appendChild(text);
    box.appendChild(node);
    enhance(node);
  }

  document.querySelectorAll("#toasts .toast").forEach(enhance);

  // ---------- confirm popup ----------
  function confirmBox(message, label, onConfirm) {
    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn btn-ghost";
    cancel.textContent = "Cancel";

    var ok = document.createElement("button");
    ok.type = "button";
    ok.className = "btn " + (/^delete/i.test(label) ? "btn-danger" : "btn-primary");
    ok.textContent = label;

    var text = document.createElement("p");
    text.textContent = message;
    var actions = document.createElement("div");
    actions.className = "modal-actions";
    actions.appendChild(cancel);
    actions.appendChild(ok);
    var box = document.createElement("div");
    box.className = "modal-box";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.appendChild(text);
    box.appendChild(actions);
    var overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.appendChild(box);

    function close() {
      document.removeEventListener("keydown", onKey);
      overlay.remove();
    }
    function onKey(event) { if (event.key === "Escape") close(); }

    cancel.addEventListener("click", close);
    overlay.addEventListener("click", function (event) { if (event.target === overlay) close(); });
    ok.addEventListener("click", function () { close(); onConfirm(); });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
    cancel.focus();
  }

  // any form with data-confirm="..." asks first
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var message = form.dataset ? form.dataset.confirm : null;
    if (!message) return;
    event.preventDefault();
    confirmBox(message, form.dataset.confirmLabel || "Confirm", function () { form.submit(); });
  });

  // ---------- CSRF token for background requests ----------
  // Every POST must carry the token from the page's <meta name="csrf-token">.
  // Forms include it as a hidden field. This adds it to fetch() calls.
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  if (window.fetch) {
    var plainFetch = window.fetch.bind(window);
    window.fetch = function (resource, options) {
      options = Object.assign({}, options);
      var method = (options.method || "GET").toUpperCase();
      if (method !== "GET" && method !== "HEAD") {
        var headers = new Headers(options.headers || {});
        if (!headers.has("X-CSRFToken")) headers.set("X-CSRFToken", csrfToken());
        options.headers = headers;
      }
      return plainFetch(resource, options);
    };
  }

  window.ExamBitUI = { toast: toast, confirm: confirmBox };
})();
