# `_lib`

Reusable page-building machinery shared by skills that render a self-contained HTML page.
There is no `SKILL.md` here, so this directory is never installed as a skill and never
becomes a `/command`. A skill reaches it through its own `lib` symlink (e.g.
`software-development/review/walkthrough/lib -> ../../../_lib`), never by importing across
skill folders directly. `install.sh --copy` follows that symlink (`cp -RL`) so a copied skill
still gets a real, self-contained `lib/` directory.

| File | What it does |
| --- | --- |
| `pagelib.py`, `page.css`, `notes.js` | Page shell helpers, base styles, notes kept in the browser. |
| `voice.py`, `voice-words.json`, `voice.md` | Simple English lint. A build fails on a hard word or a long sentence. |
| `svg.py` | Allowlist for SVG figures that an agent draws. |
| `gitfacts.py` | Reads git: changed files, line counts, and if a `path:line` or commit exists. |
| `figures.py` | Figures the builder draws: task waves, Venn, severity strip, decision tree, risk matrix, claim stack. |
| `sheet.py`, `sheet.css`, `sheet.js` | The report sheet: schema, required panels per kind, panel HTML, styles, the send handler. |
