  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      var s = raw ? JSON.parse(raw) : {};
      return Object.assign({ read: {}, notes: {}, changedOnly: false }, s);
    } catch (e) { return { read: {}, notes: {}, changedOnly: false }; }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* storage blocked: the page still reads */ }
  }
  var state = load();
