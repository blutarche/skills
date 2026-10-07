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
| `report.css`, `report.js` | The report chrome the brief and the walkthrough share: the Walkthrough head, chapter cards, the Open all button, and opening the card a `#link` points to. |
| `voice.py`, `voice-words.json`, `voice.md` | Simple English lint. A build fails on a hard word or a long sentence. |
| `svg.py` | Allowlist for SVG figures that an agent draws. |
| `dock.py`, `dock.css`, `dock.js` | The floating Send feedback dock that the brief and the walkthrough share: markup, styles, script. It needs no sheet. |
| `gitfacts.py` | Reads git: changed files, line counts, if a `path:line` or commit exists, and the project and branch names. |
| `figures.py` | Figures the builder draws: task waves, Venn, severity strip, decision tree, risk matrix, claim stack. |
| `sheet.py`, `sheet.css`, `sheet.js` | The report sheet: schema, required panels per kind, panel HTML, styles, the send handler. Every sheet shows its project and branch: from `tree`, or from the spec's `project` and `branch`; the copied feedback and `feedback/latest` carry both. |
