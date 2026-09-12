---
name: brief
description: Render the current session (a plan, an execution result, an investigation, a debug) as one self-contained visual HTML page: chapters by concept, a mermaid diagram or a stated reason per chapter, decision and evidence tables, prose capped. Use when the user asks to brief, summarise, recap, or visualise what was planned or done, or says the last output was a wall of text.
---

# Brief

One page the user opens instead of the long markdown the agent would otherwise write after a
long planning, execution, research, or debugging stretch. Chapters by concept; every chapter
carries a diagram or an explicit reason it has none; decisions and evidence go in tables; prose
is capped.

All prose lives in `brief.json`. The agent never edits HTML: `scripts/build_brief.py` validates
the spec and renders the page. A rejected spec is a defect in the summary, not a formatting
problem.

This skill is read-only with respect to the repository. It writes only under the temp directory.

## Steps

### 1. Cut chapters and choose each figure

Decide the `kind`: what the session was mostly (`plan`, `execution`, `investigation`, `mixed`).
Cut chapters by concept, 1 to 8 of them: the goal or contract first, then the mechanism, then
what changed or was decided, then what is open.

For every chapter the default is a figure (1 to 4 of them, mermaid or inline SVG); `noVisual` is
the exception, and its reason has to name why prose beats a picture here, not that drawing would
take effort.

| Need | Source | How |
|---|---|---|
| Flow, sequence, state, git, gantt, simple ER | mermaid | write source into the spec |
| Architecture, layer stack, before/after with emphasis, quadrant, Venn, fishbone, Wardley, timeline with callouts, anything needing editorial layout | `diagram-design` skill (Claude Code) | invoke it with the type; take the `<svg>` from its HTML output; paste into `svg` |
| Bar, line, scatter, heatmap, small multiples, stat tiles | `dataviz` skill (Claude Code) | follow it for form and palette; author inline SVG; paste into `svg` |
| A mechanism sketch not worth a library | hand-authored inline SVG per `artifact-diagramming` rules | `viewBox`, `currentColor`, marker arrowheads, grid-aligned, 11-13px text |

On agents without those skills: mermaid, or hand-authored SVG following `references/authoring.md`.
`diagram-design`'s style-guide gate applies too: if the project has no `.diagram-design` marker,
pass the default profile; never prompt the user for brand tokens from inside brief. Full rules
(what earns a diagram, mermaid type picker, dataviz condensation): `references/authoring.md`.

Done when: each chapter has a one-line claim as its title.

### 2. Write the spec

Write `brief.json` in `${TMPDIR:-/tmp}/brief/<repo-or-cwd-name>-<slug>-<YYYYMMDD-HHMM>/`.
Format: `references/spec.md`. Shape to copy: `examples/brief.example.json`.

Evidence rows only for commands actually run this session, with their real exit codes; a
command not run gets `exit: null`. Do not describe a green suite you did not see.

Done when: the spec is valid JSON and every chapter has `visual` xor `noVisual`.

### 3. Build

```bash
python3 <skill-dir>/scripts/build_brief.py \
  --spec brief.json --out brief.html --fragment brief.fragment.html
```

A failure names the defect: a chapter over the prose cap, a mermaid block with no recognized
type, a decision row missing a field. Fix the spec, never the page, and build again.

Done when it prints
`build_brief: ok chapters=N visuals=N noVisuals=N decisions=N evidence=N/M words=N`.

### 4. Look before delivering

Open the page and confirm it before handing it over: on Claude Code, publish
`brief.fragment.html` as an Artifact and view its preview; otherwise render a screenshot with a
headless browser if one is available; at minimum, Read `brief.html` and confirm every chapter
title appears once, in order, and every figure is present. Every figure, mermaid or svg, needs
to be seen rendered; an svg figure that shows nothing or clips is a spec defect, not a page bug.

Done when seen rendered.

### 5. Deliver

Try each of these in order, and use the first that applies:

a. **Claude Code with the Artifact tool:** publish `brief.fragment.html` (title = the spec
   title, favicon 🗺️). Feedback comes back as artifact comments.
b. **`orca status --json` succeeds:** resolve the binary per the orca-cli skill stub
   (`ORCA_CLI_COMMAND` env var, else `orca`; on Linux outside Orca use `orca-ide`, never a bare
   `orca`), then `ORCA artifacts share brief.html --json` and report the URL. On
   `artifact_sharing_disabled`, do not retry: tell the user it's Settings → Artifacts, and fall
   through to (c).
c. **Otherwise:** `open brief.html` on macOS, `xdg-open` on Linux. Feedback comes back through
   the page: Notes, then "Copy feedback", then paste into the chat.

Always print the local path, whichever route was used.

### 6. Stop

Report the link or path, the chapter count, and how feedback comes back. Do not act on feedback
in this skill; that is the next request.

## Rules that decide the shape

- **One concept per chapter.** Never a chapter per file or per commit.
- **A diagram earns its place.** It depicts the mechanism, not its name; `noVisual` is a real
  reason, not an excuse.
- **Counts come from the build**, never from prose. The stats strip is where they live.
- **Evidence is what ran.** A command not run this session is `exit: null`, not a guess.
- **Voice.** Sentences of at most 25 words. No verdicts, no emoji, no em dashes, no
  "successfully", no "comprehensive".
- **Offline-safe.** The mermaid CDN script loads only in the full document; if it can't reach
  the network, the `<pre class="mermaid">` source stays readable as text.

## Files

- `scripts/build_brief.py`: validator and renderer, stdlib only, Python 3.10 or newer.
  `--data-out` writes the derived stats as JSON. `--no-mmdc` skips the optional mermaid syntax
  check even when `mmdc` is on `PATH`.
- `scripts/test_build_brief.py`: `python3 -m unittest scripts/test_build_brief.py` from this
  directory. Run it after touching the build.
- `templates/brief-shell.html`: the page shell with the CSS, the JavaScript, and the markers the
  build splices into. It holds no prose.
- `lib/`: symlink to the repo's shared `_lib/` page machinery (theme, layout, `pagelib.py`).
  Never edit through this symlink; edit `_lib/` itself.
- `references/spec.md`: the `brief.json` format and every check the build runs.
- `references/authoring.md`: chapter, diagram, decision, evidence, and voice rules.
- `examples/brief.example.json`: a complete spec to copy the shape from.
