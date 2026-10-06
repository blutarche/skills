  // The floating dock: Send feedback, its toast, and the blocked-clipboard popover. Runs inside the page IIFE
  // after notes.js, so $ and $$ exist. A page sets dockCollect to a function returning
  // {title, text, answers, notes, fix, skip}; the dock adds the project line and the db fields.
  var dockCollect = null;
  var dockBtn = $("[data-export]"), dockToast = $("[data-export-status]"), dockPre = $("[data-export-preview]");
  var dockPop = $(".dock-pop"), dockClose = $("[data-pop-close]"), dockEl = $(".dock");
  var dockToastTimer = null, dockFlipTimer = null;

  function dockCopy(text, done) {
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

  // Inside a claude.ai artifact viewer only: claude.use("db") resolves to a database, or null.
  // Send waits on this promise, so a click before the viewer answers still saves.
  var claudeDb = Promise.resolve(null);
  if (window.claude && typeof window.claude.use === "function") {
    try {
      claudeDb = Promise.resolve(window.claude.use("db")).then(function (db) { return db || null; }, function () { return null; });
    } catch (e) { claudeDb = Promise.resolve(null); }
  }

  if (dockClose) dockClose.addEventListener("click", function () {
    dockPop.hidden = true;
    if (dockToast) dockToast.hidden = true;
  });
  // Green for the two success-only messages, amber for any message that names a problem.
  // A blocked-clipboard toast stays while the popover is open; the rest hide after 4 seconds.
  function dockSay(msg) {
    if (!dockToast) return;
    var good = msg === "Copied." || msg === "Copied. Saved for the agent.";
    dockToast.textContent = msg;
    dockToast.className = "dock-toast " + (good ? "ok" : "warn");
    dockToast.hidden = false;
    clearTimeout(dockToastTimer);
    if (!(dockPop && !dockPop.hidden)) dockToastTimer = setTimeout(function () { dockToast.hidden = true; }, 4000);
  }
  // The button confirms for 2.5 seconds; a click during the flip sends again and restarts it.
  function dockFlip() {
    dockBtn.textContent = "✓ Sent";
    dockBtn.classList.add("sent");
    clearTimeout(dockFlipTimer);
    dockFlipTimer = setTimeout(function () {
      dockBtn.textContent = "Send feedback";
      dockBtn.classList.remove("sent");
    }, 2500);
  }
  if (dockBtn) dockBtn.addEventListener("click", function () {
    if (!dockCollect) return;
    var d = dockCollect();
    var project = dockEl ? dockEl.getAttribute("data-project") || "" : "";
    var branch = dockEl ? dockEl.getAttribute("data-branch") || "" : "";
    var md = (project ? "Project: " + project + (branch ? " · Branch: " + branch : "") + "\n\n" : "") + d.text;
    if (dockPre) dockPre.textContent = md;
    var copied = null, saved = null, db;
    function done() {
      if (copied === null || db === undefined || (db && saved === null)) return;
      var msg;
      if (copied) msg = saved === false ? "Copied. Could not save on the page." : saved ? "Copied. Saved for the agent." : "Copied.";
      else msg = saved ? "Saved for the agent. Clipboard blocked; copy the text in the box." : "Clipboard blocked. Copy the text in the box.";
      if (copied || saved) dockFlip();
      if (dockPre && !copied && dockPop) dockPop.hidden = false;
      dockSay(msg);
      if (dockPre && !copied) {
        var r = document.createRange(); r.selectNodeContents(dockPre);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
      }
    }
    dockCopy(md, function (ok) { copied = ok; done(); });
    claudeDb.then(function (x) { db = x; if (db) store(); else done(); });
    function store() {
      var doc = {
        title: d.title, project: project, branch: branch, text: md,
        answers: d.answers || [], notes: d.notes || {}, fix: d.fix || [], skip: d.skip || [],
        sentAt: new Date().toISOString()
      };
      try {
        db.doc("feedback/latest").set(doc).then(
          function () { saved = true; done(); },
          function () { saved = false; done(); });
      } catch (e) { saved = false; done(); }
    }
  });
