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
    try { sessionStorage.setItem("exambit-q-" + data.attemptId, String(current)); } catch (error) { /* ignore */ }
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

    var card = el("div", { class: "card q-card" });
    card.appendChild(el("div", { class: "q-head" }, [
      el("span", { class: "q-count", text: "Question " + (current + 1) + " of " + questions.length }),
      el("span", { class: "badge badge-primary", text: q.marks + (q.marks === 1 ? " mark" : " marks") })
    ]));
    card.appendChild(el("p", { class: "q-text", text: q.text }));

    if (q.type === "short") {
      card.appendChild(el("p", { class: "q-hint", text: "Write your answer below. It is saved automatically." }));
      var area = el("textarea", { rows: "8", class: "answer-text", "aria-label": "Your answer" });
      area.value = a.text;
      area.addEventListener("input", function () { onTextInput(q, area.value); });
      card.appendChild(area);
    } else {
      if (q.type === "multiple") {
        card.appendChild(el("p", { class: "q-hint", text: "Select all that apply." }));
      }
      var choices = [];
      q.options.forEach(function (option) {
        var input = el("input", {
          type: q.type === "multiple" ? "checkbox" : "radio",
          name: "option",
          value: String(option.id)
        });
        input.checked = a.options.indexOf(option.id) !== -1;
        var label = el("label", { class: "option" + (input.checked ? " is-selected" : "") }, [
          input,
          el("span", { text: option.text })
        ]);
        choices.push({ input: input, label: label });
        input.addEventListener("change", function () {
          onOptionChange(q, option.id, input.checked);
          choices.forEach(function (choice) {
            choice.label.classList.toggle("is-selected", choice.input.checked);
          });
        });
        card.appendChild(label);
      });
    }

    var marked = el("input", { type: "checkbox" });
    marked.checked = a.marked;
    marked.addEventListener("change", function () { onMarkedChange(q, marked.checked); });
    card.appendChild(el("label", { class: "mark-toggle" }, [
      marked,
      el("span", { text: "Mark for review" })
    ]));

    var isLast = current === questions.length - 1;
    card.appendChild(el("div", { class: "q-nav" }, [
      el("button", {
        type: "button", class: "btn", text: "\u2190 Previous", disabled: current === 0,
        onclick: function () { goTo(current - 1); }
      }),
      el("button", { type: "button", class: "btn btn-ghost", text: "Clear answer", onclick: function () { clearAnswer(q); } }),
      el("span", { class: "spacer" }),
      el("button", {
        type: "button", class: "btn btn-primary", text: isLast ? "Review \u2192" : "Next \u2192",
        onclick: function () { if (isLast) showReview(); else goTo(current + 1); }
      })
    ]));
    main.appendChild(card);
  }

  function renderReview() {
    main.textContent = "";
    var answered = 0;
    var marked = 0;
    questions.forEach(function (q) {
      if (isAnswered(q)) answered++;
      if (answers[q.id].marked) marked++;
    });

    var card = el("div", { class: "card" });
    card.appendChild(el("h2", { class: "review-title", text: "Review your answers" }));
    card.appendChild(el("p", { class: "review-summary" }, [
      el("span", { class: "badge badge-success", text: answered + " answered" }),
      document.createTextNode(" "),
      el("span", { class: "badge badge-warning", text: (questions.length - answered) + " not answered" }),
      document.createTextNode(" "),
      el("span", { class: "badge badge-primary", text: marked + " marked for review" })
    ]));

    var table = el("table", { class: "review-table" });
    table.appendChild(el("tr", {}, [
      el("th", { text: "Q" }), el("th", { text: "Question" }), el("th", { text: "Status" }),
      el("th", { text: "Review flag" }), el("th")
    ]));
    questions.forEach(function (q, index) {
      var shortText = q.text.length > 60 ? q.text.slice(0, 60) + "..." : q.text;
      var isDone = isAnswered(q);
      table.appendChild(el("tr", {}, [
        el("td", { text: String(index + 1) }),
        el("td", { text: shortText }),
        el("td", {}, [el("span", {
          class: "badge " + (isDone ? "badge-success" : "badge-warning"),
          text: isDone ? "Answered" : "Not answered"
        })]),
        el("td", {}, [answers[q.id].marked
          ? el("span", { class: "badge badge-primary", text: "Marked" })
          : document.createTextNode("\u2013")]),
        el("td", {}, [
          el("button", { type: "button", class: "btn btn-sm", text: "Go to question", onclick: function () { goTo(index); } })
        ])
      ]));
    });
    card.appendChild(table);

    card.appendChild(el("div", { class: "q-nav" }, [
      el("button", { type: "button", class: "btn", text: "\u2190 Back to questions", onclick: function () { goTo(current); } }),
      el("span", { class: "spacer" }),
      el("button", { type: "button", class: "btn btn-primary", text: "Submit exam", onclick: submitExam })
    ]));
    main.appendChild(card);
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
    var layout = side.parentNode;
    side.classList.add("side-card");
    timerEl = el("p", { class: "timer", text: "--:--" });
    statusEl = el("p", { class: "save-status", "aria-live": "polite" });
    paletteEl = el("div", { class: "pal-grid" });

    // the timer, save status and Review button stay visible when the panel is collapsed
    var body = el("div", { class: "side-body" }, [
      el("h3", { class: "side-heading", text: "Questions" }),
      paletteEl,
      el("div", { class: "legend" }, [
        el("span", {}, [el("i", { class: "dot dot-answered" }), document.createTextNode("Answered")]),
        el("span", {}, [el("i", { class: "dot dot-marked" }), document.createTextNode("Marked")]),
        el("span", {}, [el("i", { class: "dot" }), document.createTextNode("Not answered")])
      ])
    ]);
    var toggle = el("button", {
      type: "button", class: "btn btn-ghost btn-sm btn-block", "aria-expanded": "true",
      text: "Hide panel \u25B8"
    });
    toggle.addEventListener("click", function () {
      var collapsed = layout.classList.toggle("panel-collapsed");
      body.hidden = collapsed;
      toggle.textContent = collapsed ? "\u25C2 Show panel" : "Hide panel \u25B8";
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    });

    side.appendChild(el("div", { class: "timer-box" }, [
      el("span", { class: "timer-label", text: "Time left" }),
      timerEl
    ]));
    side.appendChild(statusEl);
    side.appendChild(el("button", { type: "button", class: "btn btn-primary btn-block", text: "Review page", onclick: showReview }));
    side.appendChild(toggle);
    side.appendChild(body);
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

  // In-page confirm box. The browser's own confirm() can steal focus or leave
  // fullscreen, and that would be counted as a violation.
  // In-page confirm box shared with the rest of the site. The browser's own confirm()
  // can steal focus or leave fullscreen, and that would be counted as a violation.
  function confirmDialog(message, confirmText, onConfirm) {
    window.ExamBitUI.confirm(message, confirmText, onConfirm);
  }

  function submitExam() {
    confirmDialog(
      "Submit your exam now? You cannot change your answers after this.",
      "Submit exam",
      doSubmit
    );
  }

  // ---------- timer (display only; the server decides the real deadline) ----------

  // 59:59 below one hour, 1:30:20 from one hour up
  function formatTime(totalSeconds) {
    var hours = Math.floor(totalSeconds / 3600);
    var minutes = Math.floor((totalSeconds % 3600) / 60);
    var seconds = totalSeconds % 60;
    var mm = String(minutes).padStart(2, "0");
    var ss = String(seconds).padStart(2, "0");
    return hours > 0 ? hours + ":" + mm + ":" + ss : mm + ":" + ss;
  }

  function tick() {
    var left = Math.max(0, remaining - Math.floor((performance.now() - startedAt) / 1000));
    timerEl.textContent = formatTime(left);
    timerEl.classList.toggle("timer-low", left <= 300);
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
    try {
      var savedIndex = parseInt(sessionStorage.getItem("exambit-q-" + data.attemptId), 10);
      if (savedIndex >= 0 && savedIndex < questions.length) current = savedIndex;
    } catch (error) { /* storage can be blocked: start at question 1 */ }
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
