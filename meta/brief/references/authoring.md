# Authoring rules

A brief replaces the long markdown an agent would otherwise dump after a planning, execution,
research, or debugging stretch. It is chapters by concept, each with a diagram or a stated
reason it has none, decisions and evidence in tables, and prose capped so it stays a page a
reader opens rather than scrolls past.

## Chapters

- Cut by concept, not by file or commit. 1 to 8 chapters: the goal or contract first, then the
  mechanism, then what changed or was decided, then what is open.
- A chapter title states its claim: "The handler stores the event before it returns", not
  "Webhook changes".
- `prose` is at most 120 words, sentences of at most 25 words. Say what you would say out loud
  before the reader looks at anything else.

## What to draw

- Depict the mechanism, not its name. A box labelled "Outbox" says nothing a sentence didn't
  already say; an arrow showing what writes to it and what reads it says something a sentence
  can't as quickly.
- Comparing two options means drawing the difference between them, not two labelled boxes side
  by side with no arrows connecting either to the decision.
- Match complexity to the stakes. A one-line config change does not earn a diagram just because
  the chapter has room for one.
- Label every arrow. An unlabeled arrow between two boxes is a guess the reader has to make.
- Deletion is the highest-quality move: cut a node, a swimlane, or a whole diagram before adding
  one. Above roughly nine nodes, it is two diagrams, not one crowded diagram. Keep one or two
  focal elements; everything else is context around them.
## Choosing a figure source

For every chapter the default is a figure; `noVisual` is the exception, and its reason must name
why prose beats a picture here, not that drawing would take effort.

| Need | Source | How |
|---|---|---|
| Flow, sequence, state, git, gantt, simple ER | mermaid | write the source into the spec |
| Architecture, layer stack, before/after with emphasis, quadrant, Venn, fishbone, Wardley, timeline with callouts, bar, line, scatter, anything needing editorial layout | `diagram-design` skill (Claude Code) | (a) load the skill and pick the visual type from its §3 selection table; (b) load that type's own reference file before drawing; (c) follow its §6 connector rules and §7 4px grid and complexity budget; (d) run `python3 <diagram-design skill dir>/scripts/self_check.py <figure.svg>` on the saved figure and paste nothing into the spec until it prints `OK`; (e) then take the `<svg>` and paste it into `svg` |
| Heatmap, small multiples, stat tiles | `dataviz` skill (Claude Code) | follow it for form and palette; author inline SVG; paste into `svg` |
| A mechanism sketch not worth a library | hand-authored inline SVG per the rules below | `viewBox`, `currentColor`, marker arrowheads, grid-aligned, 11-13px text |

Hand-drawn boxes-and-lines with no type reference behind them is an anti-pattern, not a shortcut.
On agents without those skills: use mermaid, or a hand-authored SVG following the rules below.
`diagram-design`'s style-guide gate applies here too: if the project has no `.diagram-design`
marker, pass the default profile; brief never prompts the user for brand tokens.

A chapter can carry 1 to 4 figures, mixing mermaid and svg, when more than one picture earns its
place; each one still needs its own caption and still has to clear the bar below. More often one
is enough. Some tells for which kind of figure a chapter wants:

- A decisions table with three or more rows about trade-offs is often clearer as a quadrant or a
  before/after pair than as more table rows.
- Evidence with numbers across runs — timings, counts, pass rates over time — is a chart, not a
  table.
- A plan with phases is a timeline or a gantt, not a bulleted list of dates.
- An investigation is a fishbone of ruled-out causes, or a sequence of what was tried in order.

## Mermaid type picker

| What the chapter shows | Diagram type |
|---|---|
| A mechanism: who calls what, what writes where | `flowchart` |
| Who talks to whom, over time | `sequenceDiagram` |
| A lifecycle: states and the transitions between them | `stateDiagram-v2` |
| Before and after | two `flowchart` subgraphs in one block, labelled Before / After |
| A schedule | `gantt` or `timeline` |
| Prioritisation among options | `quadrantChart` |
| The shape of data | `erDiagram` |
| The shape of a git history | `gitGraph` |

## Inline SVG mechanics

- Size the drawing by `viewBox`, not `width`/`height`; the page strips those and sizes it with
  CSS. Theme it with `currentColor` so it follows the page's ink; reserve one literal hue for the
  single focal element a reader's eye should land on first.
- Arrowheads are markers, not manually rotated triangles. Text sits at 11-13px, short labels only.
  Align shapes to a grid instead of eyeballing coordinates.
- One figure, one claim: a figure that tries to show two unrelated things is two figures.
- The drawing has to be self-contained and pass the element/attribute allowlist in
  `references/spec.md`: no SMIL animation, `<script>`, `<style>`, `<foreignObject>`, `<iframe>`,
  `<image>`, `<a>`, no event-handler attributes, no external `href`, no external `url(...)`.

## Dataviz condensation

- One series colour unless the series differ in kind, not just in identity.
- Axis labels carry units; a number without a unit is a guess the reader has to resolve.
- No 3D. No pie chart for more than three slices; a table or a bar chart says more past that.
- Direct labels on the data beat a legend when there are only a few series.

## Decisions and evidence

- A `decisions[]` row is one real fork: `decision`, `chosen`, `rejected`, and `why` in one
  sentence, all required. If nothing was actually rejected, there is no decision row to write.
- An `evidence[]` row is a command that was actually run this session, with its real exit code.
  A command not run this session is written with `exit: null`, which renders as "not run". Never
  mark a command as run when it wasn't, and never invent a passing result you did not see.

## Voice

Sentences of at most 25 words. Plain words. No verdicts, no emoji, no em dashes, plain hyphens
only. No "successfully", no "comprehensive". Counts belong in the stats strip the build renders,
never in prose: don't write "all 12 tests" in a sentence when the evidence table already says so.

## Anti-patterns

- A chapter per file or per commit.
- Hand-drawn boxes-and-lines for a `diagram-design` figure with no type reference behind it.
- A box-per-noun diagram with no arrows between the boxes.
- A diagram that restates a table already on the page.
- `noVisual` used because drawing would take effort, not because prose already carries it better.
- An evidence row for a command that was not run, marked as if it had been.
