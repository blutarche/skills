---
name: brief
description: "Render a run as one glanceable HTML sheet: stamp, asks, checks, diff, findings, tasks, and claims as typed panels, with a linked full report below. Use when a workflow ends, or the user asks to brief, recap, or visualize a run. Also use when the user calls the last output a wall of text."
---

# Brief

All prose lives in `brief.json`. The agent never edits HTML: `scripts/build_brief.py` validates
the spec and renders the sheet. A rejected spec is a defect in the summary, not a formatting
problem. The build derives every count, stamp, and drawing from validated rows, so no number on
the sheet is typed by hand.

This skill is read-only with respect to the repository. It writes only under the temp directory.

## Steps

### 1. Pick the kind and fill the panels

Pick the `kind` that matches the workflow that ends. The build needs the panels listed for it.

| Kind | Used by |
|---|---|
| `plan` | `plan` workflow |
| `execute` | `execute` workflow |
| `vet` | `vet` workflow |
| `finish` | `finish` workflow |
| `research` | `research-council` workflow |
| `grill` | `grill-with-docs` workflow |
| `session` | any other run |

Required panels per kind (role: type). A missing role or a wrong type fails the build.

| Kind | Required panels |
|---|---|
| `plan` | needs you: asks; hardening: table; tasks: tasks; decisions: decisions |
| `execute` | needs you: asks; checks: checks; files: files; tasks: tasks; review: findings; decisions: decisions |
| `vet` | needs you: asks; findings: findings |
| `finish` | needs you: asks; next move: commands; checks: checks; diff: files; review: findings |
| `research` | needs you: asks; claims: claims |
| `grill` | needs you: asks; decisions: decisions; docs changed: files |
| `session` | needs you: asks |

The build draws task waves, the Venn, the severity strip, the claim stack, and the decision tree
from your rows. Draw a `figure` panel only for a mechanism a reader must see. Put the full
report in `chapters`: open sections below the sheet (0 to 12, optional). Each panel or row that
has more detail links to its chapter with `more` (a chapter id).

What the full report holds, by kind.

| Kind | One section for each | Each section says |
|---|---|---|
| `plan` | hard task or decision | what, why, and the risk |
| `execute` | task | what changed, why, and how it was checked |
| `vet` | P0 or P1 finding | what breaks, how to reproduce it, and the fix |
| `finish` | the whole branch | what ships, what is left, and how to roll back |
| `research` | sub-question, after the full answer | the answer, with sources |
| `grill` | decision | the question, the options, and why the chosen one won |
| `session` | the whole session | what was done and what was found |

Figures in a `figure` panel or a chapter come from these sources.

| Need | Source | How |
|---|---|---|
| Flow, sequence, state, architecture, layer stack, before/after with emphasis, timeline/swimlane, quadrant, Venn, fishbone, Wardley, bar, line, scatter, simple ER, anything needing editorial layout | `diagram-design` skill (Claude Code) | (a) load the skill and pick the visual type from its §3 selection table; (b) load that type's own reference file before drawing; (c) follow its §6 connector rules and §7 4px grid and complexity budget; (d) run `python3 <diagram-design skill dir>/scripts/self_check.py <figure.svg>` on the saved figure and paste nothing into the spec until it prints `OK`; (e) then take the `<svg>` and paste it into `svg` |
| Flow, sequence, state, git, gantt, simple ER | mermaid | when the `diagram-design` skill is not installed, or for `gitGraph`/`gantt` where mermaid's renderer is adequate; write source into the spec |
| Heatmap, small multiples, stat tiles | `dataviz` skill (Claude Code) | follow it for form and palette; author inline SVG; paste into `svg` |
| A mechanism sketch not worth a library | hand-authored inline SVG per `references/authoring.md` | `viewBox`, `currentColor`, marker arrowheads, grid-aligned, 11-13px text |

Hand-drawn boxes-and-lines with no type reference behind them is an anti-pattern, not a shortcut.
On agents without those skills: mermaid, or hand-authored SVG following `references/authoring.md`.
`diagram-design`'s style-guide gate applies too: if the project has no `.diagram-design` marker,
pass the default profile; never prompt the user for brand tokens from inside brief. Mermaid
renders in the sheet itself when `mmdc` is on `PATH`. Without `mmdc`, the page loads a pinned
mermaid script from a CDN; offline, a mermaid figure shows "Diagram loads when online".

Read `references/authoring.md` before drawing: what earns a diagram, the mermaid type picker,
inline SVG mechanics, dataviz condensation, and figure layout (`figureLayout`).

Done when: every required panel for the kind is present (an empty `asks` panel is fine), and each chapter title states a claim.

### 2. Write the spec

Write `brief.json` in `${TMPDIR:-/tmp}/brief/<repo-or-cwd-name>-<slug>-<YYYYMMDD-HHMM>/`.
Format: `references/spec.md`. Shape to copy: one example per kind in `examples/`, named
`examples/<kind>.example.json`. Voice rules are in `lib/voice.md`; the build fails on the ones
it can check.

Evidence rows only for commands actually run this session, with their real exit codes; a
command not run gets `exit: null`. Do not describe a green suite you did not see. Exit codes are
shown as reported. `files`, `where`, and `commit` are checked against git, so give `tree`.

Done when: the spec is valid JSON and has every required panel for its kind.

### 3. Build

```bash
python3 <skill-dir>/scripts/build_brief.py \
  --spec brief.json --out brief.html --fragment brief.fragment.html
```

A failure names the defect: a field over its voice cap, a missing panel, a `where` that is not
in git. Fix the spec, never the page, and build again.

Done when it prints
`build_brief: ok kind=K stamp=S panels=N asks=N words=N chapters=N`.

A failed build still writes a BUILD FAILED page at `--out`. Fix the spec and rebuild, 2 times at
most. Then reply "sheet failed", the first error, and the path.

### 4. Look before delivering

Open the page and confirm it before handing it over. Render a screenshot of `brief.html` with a
headless browser if one is available. At minimum, Read `brief.html` and confirm that the stamp,
every panel role, the full report, and every chapter title appear once, in order. Check that each
`more` link lands on the chapter it names, and that each chapter links back to the sheet. Every figure, mermaid or svg, needs
to be seen rendered; an svg figure that shows nothing or clips is a spec defect, not a page bug.
Mermaid without `mmdc` shows "Diagram loads when online" until the CDN script runs.

Done when seen rendered.

### 5. Deliver

**Always:** if `orca status --json` succeeds, run `orca tab create --url file://<abs path> --json`
(Orca's built-in browser). Else use `open` on macOS or `xdg-open` on Linux. A sandbox can block
both: try once, then print the path and the command for the user. Feedback comes back through
the page: Notes, then "Copy feedback", then paste into the chat.

**On top of that, only when the user explicitly asks to publish or share the brief online**, try
each of these in order, and use the first that applies:

a. **Claude Code with the Artifact tool:** publish `brief.fragment.html` (title = the spec
   title, `icon` = one generic word such as `map`). Feedback comes back as artifact comments.
b. **`orca status --json` succeeds:** `ORCA` below is a placeholder for the resolved binary:
   `$ORCA_CLI_COMMAND` when set, otherwise `orca`; on Linux outside an Orca terminal use
   `orca-ide`, never bare `orca` (it is the GNOME screen reader there). The `orca-cli` skill,
   when installed, has the same rule. Then `ORCA artifacts share brief.html --json` and report
   the URL. On `artifact_sharing_disabled`, do not retry: tell the user it's Settings →
   Artifacts.
c. **Neither applies, or the tried route fails:** tell the user the brief was not published and
   point back to the local path already given.

Never offer plannotator's `tot` publish.

Done when: the local file was opened and its path printed, and, if a publish was requested,
either the user has a link or has been told it was not published and pointed back to the path.

### 6. Stop

Reply in 3 lines at most: the state (with the stamp), what needs the user (the count and the
first ask), and the local path. Add the link if a requested publish succeeded, or a note that it
did not. Do not act on feedback in this skill; that is the next request.

## Files

- `scripts/build_brief.py`: validator and renderer, stdlib only, Python 3.10 or newer.
  `--data-out` writes `kind`, `stamp`, `panels`, `asks`, `words`, `figures`, and `chapters` as
  JSON. `--no-mmdc` skips the mermaid pre-render even when `mmdc` is on `PATH`.
- `scripts/test_build_brief.py`: `python3 -m unittest scripts/test_build_brief.py` from this
  directory. Run it after touching the build.
- `templates/brief-shell.html`: the page shell with the CSS, the JavaScript, and the markers the
  build splices into. It holds no prose.
- `lib/sheet.py`, `lib/voice.py`: the sheet schema and panels, and the voice lint the build runs.
- `lib/`: symlink to the repo's shared `_lib/` page machinery (theme, layout, `pagelib.py`).
  Never edit through this symlink; edit `_lib/` itself.
