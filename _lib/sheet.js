  // Sheet behavior. Runs inside the page IIFE after notes.js, so $, $$, state, and save exist.
  state.toggles = state.toggles || {};
  state.answers = state.answers || {};

  function sheetCopy(text, done) {
    function ok() { if (done) done(true); }
    function no() { if (done) done(false); }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text; ta.className = "sr";
      document.body.appendChild(ta); ta.select();
      var copied = false;
      try { copied = document.execCommand("copy"); } catch (e) { copied = false; }
      document.body.removeChild(ta);
      if (copied) ok(); else no();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, fallback);
    else fallback();
  }

  $$(".note-btn").forEach(function (b) {
    var letter = b.getAttribute("data-for");
    var ta = $('textarea[data-note="' + letter + '"]');
    if (!ta) return;
    if (state.notes[letter]) { ta.value = state.notes[letter]; ta.hidden = false; }
    b.setAttribute("aria-expanded", ta.hidden ? "false" : "true");
    b.addEventListener("click", function () {
      ta.hidden = !ta.hidden;
      b.setAttribute("aria-expanded", ta.hidden ? "false" : "true");
      if (!ta.hidden) ta.focus();
    });
    ta.addEventListener("input", function () {
      if (ta.value.trim()) state.notes[letter] = ta.value; else delete state.notes[letter];
      save();
    });
  });

  $$(".tog").forEach(function (tog) {
    var id = tog.getAttribute("data-id");
    var btns = $$("button", tog);
    function pick(v) {
      btns.forEach(function (x) { x.setAttribute("aria-pressed", x.getAttribute("data-v") === v ? "true" : "false"); });
    }
    if (state.toggles[id]) pick(state.toggles[id]);
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        var v = b.getAttribute("data-v");
        pick(v);
        state.toggles[id] = v;
        save();
      });
    });
  });

  $$(".fig[data-steps]").forEach(function (fig) {
    var steps = [];
    try { steps = JSON.parse(fig.getAttribute("data-steps")) || []; } catch (e) { steps = []; }
    var wrapEl = fig.parentNode;
    var cap = $(".cap", wrapEl), sayBtn = $('[data-act="say"]', wrapEl), playBtn = $('[data-act="play"]', wrapEl);
    var N = steps.length, cur = 0, timer = null;

    function show(n) {
      cur = n;
      if (!n) {
        fig.classList.remove("stepping");
        $$("[data-s]", fig).forEach(function (el) { el.classList.remove("on"); });
        if (cap) cap.textContent = "Press play or next to step through.";
        return;
      }
      fig.classList.add("stepping");
      $$("[data-s]", fig).forEach(function (el) {
        var on = el.getAttribute("data-s").split(" ").indexOf(String(n)) >= 0;
        if (on) el.classList.add("on"); else el.classList.remove("on");
      });
      if (cap) { cap.textContent = ""; var b = document.createElement("b"); b.textContent = n + "/" + N; cap.appendChild(b); cap.appendChild(document.createTextNode(steps[n - 1])); }
      if (sayBtn && sayBtn.getAttribute("aria-pressed") === "true" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(steps[n - 1]));
      }
    }
    function stop() { if (timer) clearInterval(timer); timer = null; if (playBtn) playBtn.textContent = "play"; }

    var act = {
      next: function () { show(cur >= N ? 1 : cur + 1); },
      prev: function () { show(cur <= 1 ? N : cur - 1); },
      all: function () { stop(); show(0); },
      play: function () {
        if (timer) return stop();
        playBtn.textContent = "pause";
        show(cur >= N ? 1 : cur + 1);
        timer = setInterval(function () { if (cur >= N) stop(); else show(cur + 1); }, 2600);
      },
      say: function () {
        var on = sayBtn.getAttribute("aria-pressed") !== "true";
        sayBtn.setAttribute("aria-pressed", on ? "true" : "false");
        sayBtn.textContent = on ? "narrate: on" : "narrate";
        if (!on && window.speechSynthesis) window.speechSynthesis.cancel();
      }
    };
    $$("[data-act]", wrapEl).forEach(function (b) {
      b.addEventListener("click", function () { var f = act[b.getAttribute("data-act")]; if (f) f(); });
    });
    show(0);
  });

  function sheetFeedback() {
    var h1 = $(".sheet h1");
    var out = ["# Feedback on " + (h1 ? h1.textContent : "the sheet"), ""];
    if (askCards.length) out.unshift(sheetAnswers().text, "");
    $$("textarea[data-note]").forEach(function (ta) {
      var text = ta.value.trim();
      if (!text) return;
      var sec = ta.closest("section");
      var role = sec ? sec.getAttribute("data-role") : "";
      out.push("## Panel " + ta.getAttribute("data-note") + ": " + role, "", text, "");
    });
    var togs = $$(".tog");
    if (togs.length) {
      var fix = [], skip = [];
      togs.forEach(function (t) {
        var p = $('[aria-pressed="true"]', t);
        (p && p.getAttribute("data-v") === "fix" ? fix : skip).push(t.getAttribute("data-id"));
      });
      out.push("Fix: " + (fix.join(", ") || "none"), "Skip: " + (skip.join(", ") || "none"), "");
    }
    if (out.length === 2) out.push("(no notes written)", "");
    return out.join("\n");
  }

  var sheetExport = $("[data-export]"), sheetStatus = $("[data-export-status]"), sheetPreview = $("[data-export-preview]");
  // Asks: option buttons and an Other field per card. state.answers[n] = { picks: [option numbers], other: text }.
  var askCards = $$(".asks > li[data-ask]");
  function askState(li) {
    var n = li.getAttribute("data-ask");
    return state.answers[n] || (state.answers[n] = { picks: [], other: "" });
  }
  function askAnswered(li) {
    var a = askState(li);
    return a.picks.length > 0 || a.other.trim() !== "";
  }
  function askPaint(li) {
    var a = askState(li);
    $$(".opt", li).forEach(function (b) {
      b.setAttribute("aria-pressed", a.picks.indexOf(Number(b.getAttribute("data-i"))) >= 0 ? "true" : "false");
    });
    var other = $(".opt-other", li);
    if (other && other.value !== a.other) other.value = a.other;
  }
  function askCount() {
    var sub = $("#panel-A .sub");
    if (!sub || !askCards.length) return;
    sub.textContent = askCards.filter(askAnswered).length + " of " + askCards.length + " answered";
  }
  function askPick(li, i) {
    var a = askState(li), at = a.picks.indexOf(i);
    if (li.hasAttribute("data-multi")) {
      if (at >= 0) a.picks.splice(at, 1); else a.picks.push(i);
    } else {
      a.picks = at >= 0 ? [] : [i];
      if (a.picks.length) a.other = "";
    }
  }
  function askRecommended(li) {
    var b = $(".opt .rec", li);
    return b ? Number(b.parentNode.getAttribute("data-i")) : 0;
  }
  askCards.forEach(function (li) {
    askPaint(li);
    $$(".opt", li).forEach(function (b) {
      b.addEventListener("click", function () {
        askPick(li, Number(b.getAttribute("data-i")));
        askPaint(li); askCount(); save();
      });
    });
    var other = $(".opt-other", li);
    other.addEventListener("input", function () {
      var a = askState(li);
      a.other = other.value;
      if (a.other.trim() && !li.hasAttribute("data-multi")) a.picks = [];
      askPaint(li); askCount(); save();
    });
    li.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey || !/^[1-4]$/.test(e.key)) return;
      if (e.target.closest && e.target.closest("input, textarea")) return;
      var b = $('.opt[data-i="' + e.key + '"]', li);
      if (b) { e.preventDefault(); b.click(); }
    });
  });
  askCount();

  var acceptBtn = $("[data-accept]");
  if (acceptBtn) acceptBtn.addEventListener("click", function () {
    askCards.forEach(function (li) {
      var rec = askRecommended(li);
      if (!rec || askAnswered(li)) return;
      askState(li).picks = [rec];
      askPaint(li);
    });
    askCount(); save();
  });

  // The answer block is one plain-text format for every host; the agent reads it from the paste.
  function sheetAnswers() {
    var h1 = $(".sheet h1");
    var title = h1 ? h1.textContent : "the sheet";
    var items = askCards.map(function (li) {
      var a = askState(li), rec = askRecommended(li);
      var picks = a.picks.slice().sort(function (x, y) { return x - y; }).map(function (i) {
        var b = $('.opt[data-i="' + i + '"] .opt-l', li);
        return { label: b ? b.textContent : "", rec: i === rec };
      });
      return { n: Number(li.getAttribute("data-ask")), ask: $(".q", li).textContent, picks: picks, other: a.other.trim() };
    });
    var lines = ["Answers: " + title];
    items.forEach(function (it) {
      var parts = it.picks.map(function (p) { return p.label + (p.rec ? " (recommended)" : ""); });
      if (it.other) parts.push("Other: " + it.other);
      lines.push(it.n + ". " + it.ask, "   -> " + (parts.join("; ") || "(no answer)"));
    });
    return { title: title, items: items, text: lines.join("\n") };
  }

  // Inside a claude.ai artifact viewer only: claude.use("db") resolves to a database, or null.
  // Send waits on this promise, so a click before the viewer answers still saves.
  var claudeDb = Promise.resolve(null);
  if (window.claude && typeof window.claude.use === "function") {
    try {
      claudeDb = Promise.resolve(window.claude.use("db")).then(function (db) { return db || null; }, function () { return null; });
    } catch (e) { claudeDb = Promise.resolve(null); }
  }

  var sheetPop = $(".dock-pop"), popClose = $("[data-pop-close]");
  var toastTimer = null, flipTimer = null;
  if (popClose) popClose.addEventListener("click", function () {
    sheetPop.hidden = true;
    if (sheetStatus) sheetStatus.hidden = true;
  });
  // Green for the two success-only messages, amber for any message that names a problem.
  // A blocked-clipboard toast stays while the popover is open; the rest hide after 4 seconds.
  function sheetSay(msg) {
    if (!sheetStatus) return;
    var good = msg === "Copied." || msg === "Copied. Saved for the agent.";
    sheetStatus.textContent = msg;
    sheetStatus.className = "dock-toast " + (good ? "ok" : "warn");
    sheetStatus.hidden = false;
    clearTimeout(toastTimer);
    if (!(sheetPop && !sheetPop.hidden)) toastTimer = setTimeout(function () { sheetStatus.hidden = true; }, 4000);
  }
  // The button confirms for 2.5 seconds; a click during the flip sends again and restarts it.
  function sheetFlip() {
    if (!sheetExport) return;
    sheetExport.textContent = "✓ Sent";
    sheetExport.classList.add("sent");
    clearTimeout(flipTimer);
    flipTimer = setTimeout(function () {
      sheetExport.textContent = "Send feedback";
      sheetExport.classList.remove("sent");
    }, 2500);
  }
  if (sheetExport) sheetExport.addEventListener("click", function () {
    var md = sheetFeedback(), ans = sheetAnswers();
    if (sheetPreview) sheetPreview.textContent = md;
    var copied = null, saved = null, db;
    function done() {
      if (copied === null || db === undefined || (db && saved === null)) return;
      var msg;
      if (copied) msg = saved === false ? "Copied. Could not save on the page." : saved ? "Copied. Saved for the agent." : "Copied.";
      else msg = saved ? "Saved for the agent. Clipboard blocked; copy from the box below." : "Clipboard blocked. Copy from the box below.";
      if (copied || saved) sheetFlip();
      if (sheetPreview && !copied && sheetPop) sheetPop.hidden = false;
      sheetSay(msg);
      if (sheetPreview && !copied) {
        sheetPreview.hidden = false;
        var r = document.createRange(); r.selectNodeContents(sheetPreview);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
      }
    }
    sheetCopy(md, function (ok) { copied = ok; done(); });
    claudeDb.then(function (d) { db = d; if (db) save(); else done(); });
    function save() {
      var notes = {}, fix = [], skip = [];
      $$("textarea[data-note]").forEach(function (ta) {
        if (ta.value.trim()) notes[ta.getAttribute("data-note")] = ta.value.trim();
      });
      $$(".tog").forEach(function (t) {
        var p = $('[aria-pressed="true"]', t);
        (p && p.getAttribute("data-v") === "fix" ? fix : skip).push(t.getAttribute("data-id"));
      });
      var doc = {
        title: ans.title,
        text: md,
        answers: ans.items.map(function (it) {
          return {
            n: it.n, ask: it.ask,
            picks: it.picks.map(function (p) { return p.label; }),
            other: it.other,
            recommended: it.picks.some(function (p) { return p.rec; })
          };
        }),
        notes: notes,
        fix: fix,
        skip: skip,
        sentAt: new Date().toISOString()
      };
      try {
        db.doc("feedback/latest").set(doc).then(
          function () { saved = true; done(); },
          function () { saved = false; done(); });
      } catch (e) { saved = false; done(); }
    }
  });

  // Whole-row navigation. A click on a [data-go] row or panel header opens its section, unless it hit
  // a control. The go-a anchor stays a real link for keyboard and no-script use.
  var lastGo = null;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function flash(el) {
    if (reduceMotion) return;
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
  }
  // Setting location.hash to its current value does not scroll, so a second visit scrolls by hand.
  function open(id) {
    var target = document.getElementById(id);
    if (target && target.tagName === "DETAILS") target.open = true;
    if (location.hash !== "#" + id) location.hash = "#" + id;
    else if (target) { target.scrollIntoView({ block: "start" }); flash(target); }
  }
  // A chapter is a closed card; a hash that names one opens it, on load and on later changes.
  function openHashChapter() {
    var el = location.hash.length > 1 ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (el && el.tagName === "DETAILS" && el.classList.contains("chapter")) el.open = true;
  }
  openHashChapter();
  window.addEventListener("hashchange", openHashChapter);
  var toggleAll = $("[data-toggle-all]");
  function chapters() { return $$("details.chapter"); }
  function toggleLabel() {
    if (toggleAll) toggleAll.textContent = chapters().every(function (d) { return d.open; }) ? "Close all" : "Open all";
  }
  if (toggleAll) {
    toggleAll.addEventListener("click", function () {
      var openAll = toggleAll.textContent === "Open all";
      chapters().forEach(function (d) { d.open = openAll; });
      toggleLabel();
    });
    chapters().forEach(function (d) { d.addEventListener("toggle", toggleLabel); });
    toggleLabel();
  }
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var go = t.closest("[data-go]");
    if (go) {
      lastGo = go;
      if (t.closest(".go-a")) { e.preventDefault(); open(go.getAttribute("data-go")); }
      else if (!t.closest("a, button, input, textarea, select, label, .tog")) open(go.getAttribute("data-go"));
      return;
    }
  });
  // One floating button: visible only while the report is on screen and the sheet is not.
  var toSheet = $(".tosheet"), reportEl = $("#report"), sheetEl = $("#sheet");
  if (toSheet && reportEl && sheetEl) {
    var seen = { report: false, sheet: false };
    var toSheetShow = function () { toSheet.hidden = !(seen.report && !seen.sheet); };
    if (window.IntersectionObserver) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) { seen[en.target === reportEl ? "report" : "sheet"] = en.isIntersecting; });
        toSheetShow();
      });
      io.observe(reportEl); io.observe(sheetEl);
    } else toSheet.hidden = false;
    toSheet.addEventListener("click", function () {
      if (lastGo && document.body.contains(lastGo)) {
        lastGo.scrollIntoView({ block: "center" });
        flash(lastGo);
      } else sheetEl.scrollIntoView({ block: "start" });
    });
  }
  document.addEventListener("animationend", function (e) {
    var f = e.target.closest ? e.target.closest(".flash") : null;
    if (f) f.classList.remove("flash");
  });
