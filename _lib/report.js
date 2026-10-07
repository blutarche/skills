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
