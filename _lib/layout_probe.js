/* Layout probe: collects raw boxes for layout_check.py. No pass/fail logic lives here. */
(function () {
  function box(el) { return el.getBoundingClientRect(); }
  function px(style, name) { return parseFloat(style.getPropertyValue(name)) || 0; }
  function all(root, sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); }
  function first(root, sel) { return root.querySelector(sel); }

  var out = {
    viewport: { innerWidth: window.innerWidth, scrollWidth: document.documentElement.scrollWidth },
    headers: [],
    files: []
  };

  all(document, ".panel>h2, .digest>h2").forEach(function (h2, i) {
    var r = box(h2), cs = window.getComputedStyle(h2);
    var parent = h2.parentNode;
    var item = {
      id: parent.id || (parent.className + "#" + i),
      top: r.top, bottom: r.bottom,
      borderTop: px(cs, "border-top-width"), borderBottom: px(cs, "border-bottom-width"),
      paddingTop: px(cs, "padding-top"), paddingBottom: px(cs, "padding-bottom"),
      scrollWidth: h2.scrollWidth, clientWidth: h2.clientWidth,
      children: []
    };
    [".ltr", ".note-btn", ".go-a"].forEach(function (sel) {
      var c = first(h2, sel);
      if (c) { var b = box(c); item.children.push({ name: sel.slice(1), top: b.top, bottom: b.bottom }); }
    });
    out.headers.push(item);
  });

  all(document, ".files").forEach(function (files, i) {
    var rows = [];
    all(files, ".frow").forEach(function (row) {
      if (row.classList.contains("more")) return;
      var bar = first(row, ".bar"), add = first(row, ".n.add"), del = first(row, ".n.del");
      rows.push({
        bar: bar ? box(bar).left : null,
        add: add ? box(add).right : null,
        del: del ? box(del).right : null
      });
    });
    var panel = files.closest ? files.closest(".panel") : null;
    out.files.push({ id: (panel && panel.id) || ("files#" + i), rows: rows });
  });

  function emit() {
    var s = document.createElement("script");
    s.type = "application/json";
    s.id = "layout-probe";
    s.text = JSON.stringify(out);
    document.body.appendChild(s);
  }
  if (document.readyState === "complete") emit();
  else window.addEventListener("load", emit);
})();
