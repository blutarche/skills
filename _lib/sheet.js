  // Sheet behavior. Runs inside the page IIFE after notes.js, so $, $$, state, and save exist.
  state.toggles = state.toggles || {};

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
  if (sheetExport) sheetExport.addEventListener("click", function () {
    var md = sheetFeedback();
    if (sheetPreview) sheetPreview.textContent = md;
    sheetCopy(md, function (ok) {
      if (sheetStatus) sheetStatus.textContent = ok ? "Copied." : "Clipboard blocked. Copy from the box below.";
      if (sheetPreview && !ok) {
        sheetPreview.hidden = false;
        var r = document.createRange(); r.selectNodeContents(sheetPreview);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
      }
    });
  });

  // Whole-row navigation. A click on a [data-go] row or panel header opens its section, unless it hit
  // a control. The go-a anchor navigates natively; this only covers the rest of the row.
  var lastGo = null;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var go = t.closest("[data-go]");
    if (go) {
      lastGo = go;
      if (!t.closest("a, button, input, textarea, select, label, .tog")) location.hash = "#" + go.getAttribute("data-go");
      return;
    }
    var back = t.closest(".chead .back");
    if (back && lastGo && document.body.contains(lastGo)) {
      e.preventDefault();
      lastGo.scrollIntoView({ block: "center" });
      if (reduceMotion) return;
      lastGo.classList.remove("flash");
      void lastGo.offsetWidth;
      lastGo.classList.add("flash");
    }
  });
  document.addEventListener("animationend", function (e) {
    var f = e.target.closest ? e.target.closest(".flash") : null;
    if (f) f.classList.remove("flash");
  });
