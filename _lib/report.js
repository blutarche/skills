  // Open all / Close all for the chapter cards; the $ and $$ helpers come from notes.js.
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

  // A link into a closed card opens the card and every card around it, then scrolls to the target.
  function openToHash() {
    var el = null;
    try { el = location.hash.length > 1 ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null; } catch (e) { el = null; }
    if (!el) return;
    if (el.tagName === "DETAILS") el.open = true;
    for (var d = el.parentElement && el.parentElement.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) d.open = true;
    el.scrollIntoView({ block: "start" });
  }
  openToHash();
  window.addEventListener("hashchange", openToHash);
  // following a link to the hash already in the address bar fires no hashchange
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (a && a.hash === location.hash) setTimeout(openToHash, 0);
  });
