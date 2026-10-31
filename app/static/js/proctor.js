// ExamBit proctoring. Runs the system check (camera, screen share, fullscreen),
// then watches the exam: tab or window switch, fullscreen exit, screen share
// stopped, camera off, right-click. It also sends a webcam snapshot every 30 seconds.
// The browser can detect and report these, but it cannot stop them.
(function () {
  "use strict";

  var boot = JSON.parse(document.getElementById("boot-data").textContent);
  var $ = function (id) { return document.getElementById(id); };

  var cameraStream = null;
  var screenStream = null;
  var cameraReady = false;
  var screenReady = false;
  var state = null;            // exam payload, set after Begin
  var active = false;          // true while the exam is being monitored
  var lastFocusViolation = 0;
  var suppressFocusUntil = 0;  // ignore focus loss caused by our own dialogs
  var needs = { screen: false, camera: false, fullscreen: false };
  var queue = [];              // violations waiting to be sent
  var sending = false;
  var warnTimer = null;

  // ---------- small helpers ----------

  function showGateError(message) {
    var box = $("gate-error");
    box.textContent = message || "";
    box.hidden = !message;
  }

  function updateGate() {
    $("btn-screen").disabled = !cameraReady;
    $("btn-begin").disabled = !($("consent").checked && cameraReady && screenReady);
    $("status-camera").textContent = cameraReady ? "Camera on" : "Not done";
    $("status-screen").textContent = screenReady ? "Entire screen shared" : "Not done";
  }

  function stopStream(stream) {
    if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
  }

  function suppressFocus(ms) {
    suppressFocusUntil = Date.now() + ms;
  }

  function warn(message) {
    var bar = $("warning-bar");
    bar.textContent = message;
    bar.hidden = false;
    clearTimeout(warnTimer);
    warnTimer = setTimeout(function () { bar.hidden = true; }, 6000);
  }

  // ---------- permissions ----------

  function requestCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return Promise.reject(new Error("Camera is not available here. Use Chrome or Edge over HTTPS."));
    }
    return navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false })
      .then(function (stream) {
        stopStream(cameraStream);
        cameraStream = stream;
        var video = $("cam");
        video.srcObject = stream;
        video.hidden = false;
        stream.getVideoTracks()[0].addEventListener("ended", onCameraEnded);
        return stream;
      }, function () {
        throw new Error("Camera access was blocked. Allow the camera in your browser settings, then try again.");
      });
  }

  function requestScreen() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
      return Promise.reject(new Error("Screen sharing is not available here. Use Chrome or Edge over HTTPS."));
    }
    return navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: "monitor" }, audio: false })
      .then(function (stream) {
        var track = stream.getVideoTracks()[0];
        var settings = track && track.getSettings ? track.getSettings() : {};
        if (settings.displaySurface && settings.displaySurface !== "monitor") {
          stopStream(stream);
          throw new Error("Please share your ENTIRE screen, not a window or a browser tab.");
        }
        stopStream(screenStream);
        screenStream = stream;
        track.addEventListener("ended", onScreenEnded);
        return stream;
      }, function () {
        throw new Error("Screen sharing was cancelled or blocked.");
      });
  }

  function enterFullscreen() {
    var root = document.documentElement;
    if (!root.requestFullscreen) {
      return Promise.reject(new Error("This browser does not support fullscreen."));
    }
    return root.requestFullscreen().catch(function () {
      throw new Error("Fullscreen was blocked. Click the button again.");
    });
  }

  // ---------- system check (before the exam) ----------

  $("consent").addEventListener("change", updateGate);

  $("btn-camera").addEventListener("click", function () {
    showGateError("");
    requestCamera()
      .then(function () { cameraReady = true; updateGate(); })
      .catch(function (error) { showGateError(error.message); });
  });

  $("btn-screen").addEventListener("click", function () {
    showGateError("");
    requestScreen()
      .then(function () { screenReady = true; updateGate(); })
      .catch(function (error) { showGateError(error.message); });
  });

  $("btn-begin").addEventListener("click", function () {
    showGateError("");
    // must run inside this click so the browser allows fullscreen
    enterFullscreen()
      .then(function () {
        return fetch(boot.urls.begin, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent: $("consent").checked })
        });
      })
      .then(function (response) { return response.json(); })
      .then(function (body) {
        if (!body.ok) {
          if (body.result_url) { window.location.href = body.result_url; return; }
          throw new Error(body.error || "Could not start the exam.");
        }
        startExam(body.payload);
      })
      .catch(function (error) {
        if (document.fullscreenElement) document.exitFullscreen();
        showGateError(error && error.message ? error.message : "Could not start the exam.");
      });
  });

  // ---------- start of the exam ----------

  function startExam(payload) {
    state = payload;
    $("gate").hidden = true;
    $("exam-app").hidden = false;
    window.ExamRunner.start(payload);
    startMonitoring();
  }

  function startMonitoring() {
    active = true;
    lastFocusViolation = Date.now(); // ignore the focus changes while entering fullscreen

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) focusLost();
    });
    window.addEventListener("blur", focusLost);
    document.addEventListener("fullscreenchange", onFullscreenChange);

    document.addEventListener("contextmenu", function (event) {
      if (!active) return;
      event.preventDefault();
      report("right_click");
    });
    ["copy", "cut", "paste"].forEach(function (name) {
      document.addEventListener(name, function (event) {
        if (!active) return;
        event.preventDefault();
        warn("Copy, cut and paste are not allowed.");
      });
    });

    if (state.violationCount > 0) {
      warn("You already have " + state.violationCount + " of " + state.maxViolations + " violations.");
    }

    setInterval(sendQueue, 5000); // retry violations that could not be sent
    takeSnapshot();
    setInterval(takeSnapshot, boot.snapshotInterval * 1000);
  }

  // ---------- detection ----------

  // A tab switch fires both visibilitychange and blur, so one cooldown counts it once.
  function focusLost() {
    if (!active || Date.now() < suppressFocusUntil) return;
    var now = Date.now();
    if (now - lastFocusViolation < 2000) return;
    lastFocusViolation = now;
    report("tab_switch");
  }

  function onFullscreenChange() {
    if (!active) return;
    if (document.fullscreenElement) {
      needs.fullscreen = false;
    } else {
      needs.fullscreen = true;
      report("fullscreen_exit");
    }
    refreshOverlay();
  }

  function onScreenEnded() {
    screenReady = false;
    if (!active) { updateGate(); return; }
    needs.screen = true;
    refreshOverlay();
    report("screen_share_stopped");
  }

  function onCameraEnded() {
    cameraReady = false;
    if (!active) { updateGate(); return; }
    needs.camera = true;
    refreshOverlay();
    report("camera_off");
  }

  // ---------- overlay: blocks the exam until the problem is fixed ----------

  function refreshOverlay() {
    var box = $("overlay");
    var need = needs.screen ? "screen" : needs.camera ? "camera" : needs.fullscreen ? "fullscreen" : null;
    if (!need) { box.hidden = true; return; }
    var spec = {
      screen: {
        text: "Screen sharing stopped. Share your ENTIRE screen again to continue.",
        button: "Share screen", action: reshare
      },
      camera: {
        text: "Your camera is off. Turn it on to continue.",
        button: "Enable camera", action: recamera
      },
      fullscreen: {
        text: "You left fullscreen mode. Return to fullscreen to continue.",
        button: "Return to fullscreen", action: refull
      }
    }[need];
    $("overlay-text").textContent = spec.text;
    $("overlay-btn").textContent = spec.button;
    $("overlay-btn").onclick = spec.action;
    box.hidden = false;
  }

  function overlayError(error) {
    $("overlay-text").textContent = error.message;
  }

  function reshare() {
    suppressFocus(30000);
    requestScreen()
      .then(function () { needs.screen = false; screenReady = true; refreshOverlay(); })
      .catch(overlayError)
      .then(function () { suppressFocus(1500); });
  }

  function recamera() {
    requestCamera()
      .then(function () { needs.camera = false; cameraReady = true; refreshOverlay(); })
      .catch(overlayError);
  }

  function refull() {
    suppressFocus(3000);
    enterFullscreen()
      .then(function () { needs.fullscreen = false; refreshOverlay(); })
      .catch(overlayError);
  }

  // ---------- reporting violations to the server ----------

  function report(kind) {
    queue.push(kind);
    sendQueue();
  }

  function sendQueue() {
    if (sending || !queue.length || !state) return;
    sending = true;
    var kind = queue[0];
    fetch(state.urls.violation, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: kind })
    })
      .then(function (response) { return response.json(); })
      .then(function (result) {
        queue.shift();
        sending = false;
        if (result.finished) {
          active = false;
          window.location.href = result.result_url;
          return;
        }
        if (result.ok) {
          warn("Violation recorded: " + (boot.labels[kind] || kind) + ". " +
               result.count + " of " + result.max + ". Integrity score: " + result.integrity + ".");
        }
        sendQueue();
      })
      .catch(function () { sending = false; }); // keep it in the queue and retry later
  }

  // ---------- webcam snapshots ----------

  function takeSnapshot() {
    var video = $("cam");
    if (!active || !cameraStream || !cameraReady || video.readyState < 2 || !video.videoWidth) return;

    var canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 240;
    canvas.getContext("2d").drawImage(video, 0, 0, 320, 240);
    canvas.toBlob(function (blob) {
      if (!blob) return;
      var form = new FormData();
      form.append("image", blob, "snapshot.jpg");
      fetch(state.urls.snapshot, { method: "POST", body: form })
        .then(function (response) { return response.json(); })
        .then(function (result) {
          if (result.finished) {
            active = false;
            window.location.href = result.result_url;
          }
        })
        .catch(function () { /* a missed snapshot is not fatal */ });
    }, "image/jpeg", 0.6);
  }

  // used by exam-runner.js
  window.Proctor = {
    suppressFocus: suppressFocus,
    stop: function () { active = false; }
  };

  updateGate();
})();
