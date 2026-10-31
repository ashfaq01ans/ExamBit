// ExamBit exam screen. One page for the whole attempt: questions change without
// reloading, so camera, screen share and fullscreen stay alive. The SERVER stays the
// authority: it keeps the deadline, saves answers and finalizes the attempt. This
// script only displays and sends. proctor.js calls ExamRunner.start(payload).
(function () {
  "use strict";

  var data, questions, answers;
  var current, view, dirty, saveChain, textTimer, submitting, leaving;
  var main, side, timerEl, statusEl, paletteEl;
  var remaining, startedAt;

  // ---------- small helpers ----------

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (key) {
      var value = props[key];
      if (value === false || value === null || value === undefined) return;
      if (key === "text") node.textContent = value;
      else if (key === "class") node.className = value;
      else if (key.indexOf("on") === 0) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    });
    (children || []).forEach(function (child) {
      if (child) node.appendChild(child);
    });
    return node;
  }

  function isAnswered(q) {
    var a = answers[q.id];
    return q.type === "short" ? a.text.trim().length > 0 : a.options.length > 0;
  }

  function setStatus(message) {
    statusEl.textContent = message;
  }

  // ---------- saving ----------

  function markDirty(q) {
    dirty[q.id] = true;
    setStatus("Unsaved changes...");
  }

  function saveNow(q) {
    if (!dirty[q.id]) return saveChain;
    var a = answers[q.id];
    var body = {
      question_id: q.id,
      options: a.options.slice(),
      text: a.text,
      marked: a.marked
    };
    delete dirty[q.id];

    saveChain = saveChain.then(function () {
      return fetch(data.urls.answer, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      })
        .then(function (response) { return response.json(); })
        .then(function (result) {
          if (result.finished) {
            goResult(result.result_url);
            return;
          }
          if (!result.ok) throw new Error("save failed");
          if (Object.keys(dirty).length === 0) setStatus("All changes saved");
        })
        .catch(function () {
          dirty[q.id] = true; // try again on the next flush
          setStatus("Could not save. Retrying...");
        });
    });
    return saveChain;
  }

  function flushAll() {
    clearTimeout(textTimer);
    questions.forEach(function (q) {
      if (dirty[q.id]) saveNow(q);
    });
    return saveChain;
  }

  function flushCurrent() {
    clearTimeout(textTimer);
    if (view === "question") saveNow(questions[current]);
  }

  // ---------- answer changes ----------

  function onOptionChange(q, optionId, checked) {
    var a = answers[q.id];
    if (q.type === "multiple") {
      var index = a.options.indexOf(optionId);
      if (checked && index === -1) a.options.push(optionId);
      if (!checked && index !== -1) a.options.splice(index, 1);
    } else {
      a.options = checked ? [optionId] : [];
    }
    markDirty(q);
    saveNow(q);
    refreshPalette();
  }

  function onTextInput(q, value) {
    answers[q.id].text = value;
    markDirty(q);
    clearTimeout(textTimer);
    textTimer = setTimeout(function () {
      saveNow(q);
      refreshPalette();
    }, 1500);
  }

  function onMarkedChange(q, checked) {
    answers[q.id].marked = checked;
    markDirty(q);
    saveNow(q);
    refreshPalette();
  }

  function clearAnswer(q) {
    answers[q.id].options = [];
    answers[q.id].text = "";
    markDirty(q);
    saveNow(q);
    render();
  }

  // ---------- navigation ----------

  function goTo(index) {
    flushCurrent();
    current = index;
    view = "question";
    render();
  }

  function showReview() {
    flushCurrent();
    view = "review";
    render();
  }

  function render() {
    if (view === "review") renderReview();
    else renderQuestion();
    refreshPalette();
  }

  // ---------- views ----------

  function renderQuestion() {
    var q = questions[current];
    var a = answers[q.id];
    main.textContent = "";

    main.appendChild(el("h2", { text: "Question " + (current + 1) + " of " + questions.length }));
    main.appendChild(el("p", {
      class: "q-text",
      text: q.text + " (" + q.marks + (q.marks === 1 ? " mark)" : " marks)")
    }));

    if (q.type === "short") {
      var area = el("textarea", { rows: "8", class: "answer-text", "aria-label": "Your answer" });
      area.value = a.text;
      area.addEventListener("input", function () { onTextInput(q, area.value); });
      main.appendChild(area);
    } else {
      if (q.type === "multiple") main.appendChild(el("p", { text: "Select all that apply." }));
      q.options.forEach(function (option) {
        var input = el("input", {
          type: q.type === "multiple" ? "checkbox" : "radio",
          name: "option",
          value: String(option.id)
        });
        input.checked = a.options.indexOf(option.id) !== -1;
        input.addEventListener("change", function () {
          onOptionChange(q, option.id, input.checked);
        });
        main.appendChild(el("p", {}, [
          el("label", {}, [input, document.createTextNode(" " + option.text)])
        ]));
      });
    }

    var marked = el("input", { type: "checkbox" });
    marked.checked = a.marked;
    marked.addEventListener("change", function () { onMarkedChange(q, marked.checked); });
    main.appendChild(el("p", {}, [
      el("label", {}, [marked, document.createTextNode(" Mark for review")])
    ]));

    var isLast = current === questions.length - 1;
    main.appendChild(el("p", {}, [
      el("button", {
        type: "button", text: "\u2190 Previous", disabled: current === 0,
        onclick: function () { goTo(current - 1); }
      }),
      document.createTextNode(" "),
      el("button", {
        type: "button", text: isLast ? "Review \u2192" : "Next \u2192",
        onclick: function () { if (isLast) showReview(); else goTo(current + 1); }
      }),
      document.createTextNode(" "),
      el("button", { type: "button", text: "Clear answer", onclick: function () { clearAnswer(q); } })
    ]));
  }

  function renderReview() {
    main.textContent = "";
    var answered = 0;
    var marked = 0;
    questions.forEach(function (q) {
      if (isAnswered(q)) answered++;
      if (answers[q.id].marked) marked++;
    });

    main.appendChild(el("h2", { text: "Review your answers" }));
    main.appendChild(el("p", {
      text: "Answered: " + answered + " | Not answered: " + (questions.length - answered) +
            " | Marked for review: " + marked
    }));

    var table = el("table", { border: "1", cellpadding: "6" });
    table.appendChild(el("tr", {}, [
      el("th", { text: "Q" }), el("th", { text: "Question" }), el("th", { text: "Status" }),
      el("th", { text: "Marked for review" }), el("th")
    ]));
    questions.forEach(function (q, index) {
      var shortText = q.text.length > 60 ? q.text.slice(0, 60) + "..." : q.text;
      table.appendChild(el("tr", {}, [
        el("td", { text: String(index + 1) }),
        el("td", { text: shortText }),
        el("td", { text: isAnswered(q) ? "Answered" : "Not answered" }),
        el("td", { text: answers[q.id].marked ? "Marked" : "\u2013" }),
        el("td", {}, [
          el("button", { type: "button", text: "Go to question", onclick: function () { goTo(index); } })
        ])
      ]));
    });
    main.appendChild(table);

    main.appendChild(el("p", {}, [
      el("button", { type: "button", text: "\u2190 Back to questions", onclick: function () { goTo(current); } }),
      document.createTextNode(" "),
      el("button", { type: "button", text: "Submit exam", onclick: submitExam })
    ]));
  }

  function refreshPalette() {
    paletteEl.textContent = "";
    questions.forEach(function (q, index) {
      var classes = "pal-btn";
      if (isAnswered(q)) classes += " answered";
      if (answers[q.id].marked) classes += " marked";
      if (view === "question" && index === current) classes += " current";
      paletteEl.appendChild(el("button", {
        type: "button", class: classes, text: String(index + 1),
        "aria-label": "Go to question " + (index + 1),
        onclick: function () { goTo(index); }
      }));
    });
  }

  function buildSide() {
    timerEl = el("p", { class: "timer", text: "--:--" });
    statusEl = el("p", { class: "save-status", "aria-live": "polite" });
    paletteEl = el("div", { class: "pal-grid" });
    side.appendChild(el("p", { text: "Time left" }));
    side.appendChild(timerEl);
    side.appendChild(statusEl);
    side.appendChild(el("p", { text: "Questions" }));
    side.appendChild(paletteEl);
    side.appendChild(el("p", { text: "Green: answered. Orange outline: marked for review." }));
    side.appendChild(el("button", { type: "button", text: "Review page", onclick: showReview }));
  }

  // ---------- submit and finish ----------

  function goResult(url) {
    leaving = true;
    if (window.Proctor) window.Proctor.stop();
    window.location.href = url;
  }

  function doSubmit() {
    if (submitting) return;
    submitting = true;
    flushAll()
      .then(function () {
        return fetch(data.urls.submit, { method: "POST", headers: { "X-Requested-With": "fetch" } });
      })
      .then(function (response) { return response.json(); })
      .then(function (result) { goResult(result.result_url || data.urls.result); })
      .catch(function () {
        setStatus("Submit failed. Check your connection.");
        setTimeout(function () { submitting = false; }, 3000);
      });
  }

  function submitExam() {
    // the browser confirm box can make the window lose focus: do not count that
    if (window.Proctor) window.Proctor.suppressFocus(20000);
    var ok = window.confirm("Submit your exam now? You cannot change answers after this.");
    if (window.Proctor) window.Proctor.suppressFocus(1500);
    if (ok) doSubmit();
  }

  // ---------- timer (display only; the server decides the real deadline) ----------

  function tick() {
    var left = Math.max(0, remaining - Math.floor((performance.now() - startedAt) / 1000));
    var minutes = Math.floor(left / 60);
    var seconds = left % 60;
    timerEl.textContent = String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
    if (left === 0) doSubmit();
  }

  // ---------- start ----------

  function start(payload) {
    data = payload;
    questions = data.questions;
    answers = {};
    questions.forEach(function (q) {
      var saved = data.answers[q.id] || {};
      answers[q.id] = {
        options: (saved.options || []).slice(),
        text: saved.text || "",
        marked: !!saved.marked
      };
    });
    current = 0;
    view = "question";
    dirty = {};
    saveChain = Promise.resolve();
    textTimer = null;
    submitting = false;
    leaving = false;
    remaining = data.remaining;
    startedAt = performance.now();
    main = document.getElementById("main-panel");
    side = document.getElementById("side-panel");

    // warn if the tab is closed or refreshed while a change is still unsaved
    window.addEventListener("beforeunload", function (event) {
      if (!leaving && Object.keys(dirty).length) {
        event.preventDefault();
        event.returnValue = "";
      }
    });

    buildSide();
    render();
    tick();
    setInterval(tick, 500);
    setInterval(flushAll, 5000); // retry any save that failed
  }

  window.ExamRunner = { start: start };
})();
