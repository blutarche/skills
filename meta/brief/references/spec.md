# `brief.json`

The brief spec. All prose lives here; the agent never edits the HTML. The build reads this
file, checks every field against the rules below, and renders the sheet from it. The sheet
fields sit at the top level next to `chapters`.

## Sheet fields

```json
{
  "title": "Outbox retries: review of feat/outbox",
  "kind": "vet",
  "state": "7 findings. 5 are fixed by default, 2 need you.",
  "blocked": false,
  "tree": {"repo": "/abs/path/to/repo", "base": "main", "head": "worktree"},
  "facts": [{"k": "branch", "v": "feat/outbox"}, {"k": "reviewers", "v": "scrutinize, council"}],
  "panels": [
    {"role": "needs you", "type": "asks", "rows": [{"ask": "Fix F2 now or after merge?", "why": "It changes the retry API."}]},
    {"role": "findings", "type": "findings", "rows": [
      {"id": "F1", "sev": "P1", "claim": "A crash between insert and commit drops the event.", "where": "src/outbox/store.ts:41",
       "foundBy": ["scrutinize", "council"], "default": "fix"}
    ]}
  ],
  "chapters": []
}
```

Every string field has one class. The build runs the voice lint on every `label`,
`instruction`, and `prose` field. The rules are in `lib/voice.md`.

| Class | Rule | Rendered |
|---|---|---|
| `label` | 12 words at most, 1 sentence | escaped text; `` `x` `` becomes `<code>x</code>` |
| `instruction` | 20 words per sentence, 2 sentences at most | same as label |
| `prose` | 25 words per sentence; the field sets the sentence count | sanitized HTML |
| `literal` | no voice check | escaped, in `<code>` for a command or path |

Prose fields are sanitized and embedded as HTML. Only `<p> <br> <b> <strong> <i> <em> <code>
<pre> <a> <ul> <ol> <li> <span>` survive; on `<a>`, only `href` survives, and only when it is a
`#` fragment, an absolute `http://` or `https://` URL, or a scheme-less relative path.
Sanitizing never fails the build.

Top level:

| Field | Required | Class or type |
|---|---|---|
| `title` | yes | label |
| `kind` | yes | one of `plan execute vet finish research grill session` |
| `state` | yes | prose, 2 sentences at most |
| `blocked` | no | bool |
| `tree` | when any `files` panel, `findings[].where`, or `tasks[].commit` exists | `{repo, base, head}` literals |
| `facts` | no, 0 to 6 | `{k: label of 3 words at most, v: literal}` |
| `panels` | yes, 1 to 8 | the first panel is `{"role": "needs you", "type": "asks"}`; its `rows` may be empty |
| `chapters` | no, 0 to 8 | drawers; see Drawers |

`tree.repo` is absolute, or relative to the spec file's folder. `tree.head` is `HEAD`,
`worktree`, or a sha. The old kinds `execution`, `investigation`, and `mixed` are gone, with no
aliases. `context`, `open`, and `noVisual` are gone too.

## Panels

A panel is `{role, type, span?, ...}`. `role` is a label of 4 words at most and is unique.
`span` is 3, 4, 6, 8, or 12 of the 12 grid columns; the build packs each row full. Letters A, B,
C and so on are assigned in order by the builder. Builder-made panels sit after panel A, and the
total stays at 8 or fewer.

| Type | Row fields (class) | The build derives or checks |
|---|---|---|
| `asks` | `ask` label, required; `why` instruction | the count; amber when rows exist, else "Nothing needs you" |
| `checks` | `cmd` literal, `cwd` literal, `exit` int or null, all required; `result` label | pass, fail, and not-run counts; an "agent-reported" note |
| `files` | no rows (fails if given) | rows from git for `tree`; A/M/D letter; +/- bars; totals |
| `figure` | Panel fields, not rows. Exactly one of `svg` or `mermaid`. `caption` label, required. `steps` `[{n: int, say: instruction}]` (svg only). | `svg` allowlist. Steps number 1..N. Each step is used by a `data-s`, and each `data-s` is a step. |
| `decisions` | `id` literal (required when any row has `parent`); `decision` label, `chosen` label, `why` instruction, all required; `rejected` label; `parent` literal | the decision tree when any row has `parent` |
| `tasks` | `id` literal, `name` label, `status` (`done failed blocked skipped todo`), all required. `after` list of ids. `commit` literal. `exit` int or null. | Task waves from `after`; n of m done. An unknown id or a cycle fails. `commit` must exist. |
| `findings` | `id` literal, `sev` (`P0` to `P3`), `claim` instruction, `foundBy` non-empty list, `default` (`fix` or `skip`), all required. `where` literal. `dispute` instruction. `outcome` (`fixed skipped rejected open`). | Severity strip. Venn when exactly 2 reviewers. Fix and skip toggles. `where` checked, else an "agent-reported" chip. |
| `claims` | `id` literal, `claim` instruction, `source` literal, `result` (`verified corrected unverified`), all required; `note` instruction | a stacked bar of results |
| `commands` | `cmd` literal and `does` label, required; `danger` bool | a red border on `danger` rows |
| `matrix` | `id` literal, `label` label, `likelihood` and `impact` (`low med high`), all required | a 3 by 3 heat grid holding the ids |
| `table` | panel fields: `columns` (1 to 5 labels of 3 words at most); `rows` (1 to 8 lists of labels, one per column) | none |

Required panels per kind (role: type). A missing role or a wrong type fails the build.

| Kind | Required |
|---|---|
| `plan` | needs you: asks; hardening: table; tasks: tasks; decisions: decisions |
| `execute` | needs you: asks; checks: checks; files: files; tasks: tasks; review: findings; decisions: decisions |
| `vet` | needs you: asks; findings: findings |
| `finish` | needs you: asks; next move: commands; checks: checks; diff: files; review: findings |
| `research` | needs you: asks; claims: claims |
| `grill` | needs you: asks; decisions: decisions; docs changed: files |
| `session` | needs you: asks |

The stamp is derived, never supplied. `blocked` gives `BLOCKED` (red). Else any ask row gives
`NEEDS YOU` (amber). Else `plan` and `finish` give `READY`, `research` gives `ANSWERED`, and
the other kinds give `DONE` (green).

## Drawers

`chapters` are optional drawers below the sheet, 0 to 8, closed by default. They hold detail the
panels do not.

```json
{
  "id": "kebab-case",
  "title": "States its claim",
  "prose": "<p>HTML. Two sentences at most.</p>",
  "proseWhy": "Optional. Why this drawer needs more than 2 sentences. 20 words per sentence.",
  "figureLayout": "row",
  "visual": {
    "mermaid": "flowchart LR\n  a[Handler] -->|writes| b[(Outbox)]",
    "caption": "A label of 12 words at most."
  },
  "decisions": [
    { "decision": "Where retries live", "chosen": "Worker", "rejected": "Handler", "why": "Failing twice is free off the request path." }
  ],
  "evidence": [
    { "cmd": "npm test", "cwd": ".", "exit": 0, "ok": true, "summary": "219 passed" },
    { "cmd": "npm run e2e", "cwd": ".", "exit": null, "summary": "not run" }
  ]
}
```

`id`, `title`, and `prose` are required. `title` is a label. `prose` is at most 2 sentences,
unless `proseWhy` is present; then `prose` may be longer, up to 120 words. `proseWhy` is never
rendered. `visual`, `decisions`, `evidence`, and `figureLayout` are optional. A drawer needs no
`visual`.

Plain-text fields: `cmd` and `cwd`. `decision`, `chosen`, `rejected` are labels; `why` and
evidence `summary` are instructions.

## Figures

`visual` is either one figure object or an array of 1 to 4 of them, rendered in order:

```json
{ "mermaid": "flowchart LR\n  a --> b", "caption": "A label of 12 words at most." }
{ "svg": "<svg viewBox=\"0 0 640 320\" role=\"img\" aria-label=\"...\">...</svg>", "caption": "A label of 12 words at most." }
```

Exactly one of `mermaid` or `svg` per figure, both as non-empty strings; `caption` is required on
every figure as a label of 12 words at most. An `svg` figure's root must carry `viewBox`;
`width`/`height` on the root are stripped, since CSS sizes the figure.

`figureLayout` is absent (figures stack full width) or exactly `"row"` (side by side); any other
value fails the build. `references/authoring.md` says when `row` is right.

A `mermaid` figure's first non-blank line, after skipping any leading `---`-delimited frontmatter
block and any `%%{init...}%%` directive (in either order), must start with one of: `flowchart`,
`graph`, `sequenceDiagram`, `stateDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`,
`journey`, `gantt`, `pie`, `quadrantChart`, `timeline`, `mindmap`, `sankey-beta`, `xychart-beta`,
`block-beta`, `gitGraph`, `C4Context`. The same rules hold for a `figure` panel's `mermaid`.

If `mmdc` is on `PATH`, each mermaid figure is pre-rendered through it, in a light and a dark
theme, and a non-zero exit fails the build. `--no-mmdc` skips that. Without `mmdc`, the build
prints `build_brief: mmdc not found; mermaid figures render only online` and loads the mermaid
script from a CDN, pinned to 11.15.0. Until it runs, the figure shows "Diagram loads when
online". A drawer's diagrams render when the drawer opens.

An `svg` is checked against an **allowlist**: every element and attribute has to be named below,
or the build fails naming the chapter or panel, the figure's index, and the offending tag or attribute.
Nothing is stripped to make a figure pass; fix the drawing.

- **Elements:** `svg g path rect circle ellipse line polyline polygon text tspan textPath defs
  clipPath mask pattern linearGradient radialGradient stop marker symbol use title desc filter
  feGaussianBlur feOffset feBlend feColorMatrix feComposite feFlood feMerge feMergeNode
  feMorphology feTile feTurbulence feDropShadow feComponentTransfer feFuncR feFuncG feFuncB
  feFuncA`. SMIL animation, `<image>`, `<foreignObject>`, `<iframe>`, `<a>`, `<script>`,
  `<style>`, and HTML tags are refused by omission.
- **Attributes**, on any allowed element: geometry and paint (`x`, `y`, `width`, `height`, `d`,
  `points`, `fill`, `stroke`, `opacity`, and friends), text layout, `viewBox`,
  `preserveAspectRatio`, filter and gradient parameters, `id`, `class`, `transform`,
  `role`/`aria-*`, `xml:space`, `lang`, `xmlns`, `data-s` (a step number list, such as `"1 2"`). See `SVG_ALLOWED_ATTRS` in `lib/svg.py` for
  the exact list; anything not on it fails by name, including `style` and every `on*` handler.
- **`href`/`xlink:href`** are accepted only on `use`, `textPath`, `pattern`, `linearGradient`,
  `radialGradient`, and only as a `#local` reference.
- **Values:** any attribute value containing `url(...)` must be `url(#local)`; any value
  containing `javascript:` or `data:` fails, wherever it appears.
- **Size:** the raw `svg` string is capped at 64 KB, and the re-serialized markup is capped at
  64 KB again.

## What the build checks

Every failure prints `build_brief: <the defect>` on stderr and exits 1. It also writes a BUILD
FAILED page, described under Outputs.

- The spec is valid JSON, and `title`, `kind`, `state`, `panels` are all present.
- `kind` is one of the seven kinds. The kind's required panels exist with the right types.
- Panel A is `needs you: asks`. Roles are unique. Panels number 8 or fewer, builder-made ones
  included. Row fields match the table above, and an unknown field fails.
- The voice lint passes on every `label`, `instruction`, and `prose` field: word and sentence
  caps, the replace list, the ban list, and no em dash.
- `files`, `where`, and `commit` are checked against git for `tree`. `where` is `path:line`;
  a `where` that does not exist shows an "agent-reported" chip instead of failing.
- A `tasks` panel has unique ids, no unknown `after` id, and no cycle.
- Each `svg` passes the allowlist, and `steps` match the `data-s` attributes.
- Drawers: at most 8; ids are kebab-case and unique; `prose` has 2 sentences at most unless
  `proseWhy` is set, and never more than 120 words; `figureLayout` is `"row"` or absent.
- Drawer `decisions` rows need `decision`, `chosen`, `rejected`, `why`. Drawer `evidence` rows need `cmd` and `cwd`,
  and `exit` as an integer or `null`; `ok`, when present, is `true` or `false`.

## What the build derives

The stamp, the panel letters, the row spans, and every count (asks, checks, files, tasks,
findings). It also draws task waves, the Venn, the severity strip, the claim stack, the
decision tree, and the heat matrix from rows. Counts never appear in prose. `words` counts the
words in the checked fields. `--data-out` writes `kind`, `stamp`, `panels`, `asks`, `words`,
`figures`, and `chapters` as JSON.

## On the page

Notes are a textarea per drawer and per panel, stored in this browser's `localStorage`
under a key derived from the spec's raw bytes, so editing and rebuilding the spec starts feedback
fresh. "Copy feedback" builds a plain-text block of the notes and fix or skip choices. The page
loads no web fonts. A drawer's `proseWhy` is never rendered.

## Outputs

- `--out` writes a full document. When mermaid is not pre-rendered, it also holds the mermaid
  CDN script, initialised with `securityLevel: 'strict'`.
- `--fragment` writes the same content without those wrappers or the mermaid script. This is what
  the Claude Code Artifact tool wants, since the host renders mermaid blocks itself.
- `--data-out` writes the derived stats as JSON.
- On a failed build, `--out` and `--fragment` get a BUILD FAILED page that shows the error and
  the spec path, never the spec text. The exit status is 1.
