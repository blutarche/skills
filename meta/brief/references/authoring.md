# Authoring rules

A brief replaces the long markdown an agent would otherwise dump after a planning, execution,
research, or debugging stretch. It is one sheet of typed panels, with detail in drawers, in
simple English. The sheet stays a page a reader glances at rather than scrolls past.

## Drawers

- Drawers hold detail only. The panels carry the state, the asks, and the facts. A drawer is
  optional, and a sheet may have none.
- Cut by concept, not by file or commit. 0 to 8 drawers.
- A drawer title states its claim: "The handler stores the event before it returns", not
  "Webhook changes".
- `prose` is 2 sentences at most. Add `proseWhy` (never shown) only when a drawer truly needs
  more, and then keep `prose` to 120 words.
- A drawer's `visual` is optional. A figure caption is a label of 12 words at most.

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

The source table and its gates (`diagram-design`, mermaid, `dataviz`, hand-authored SVG) are in
SKILL.md step 1.

A drawer can carry 1 to 4 figures, mixing mermaid and svg, when more than one picture earns its
place; each one still needs its own caption and still has to clear the bar below. More often one
is enough. Figures stack full width by default; set `"figureLayout": "row"` on the chapter to lay
them side by side instead, and only when every figure in the chapter is narrow, roughly `viewBox`
width under 500 — a wide figure such as a swimlane or a wide flowchart loses half its width next
to another figure in a row and should stay stacked. Some tells for which kind of figure a chapter
wants:

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

The rules are in `lib/voice.md`. The build checks word caps, the replace and ban lists, and em
dashes. You check the rest: one meaning per word, active voice, short common words.

## Anti-patterns

- A drawer per file or per commit.
- Hand-drawn boxes-and-lines for a `diagram-design` figure with no type reference behind it.
- A box-per-noun diagram with no arrows between the boxes.
- A diagram that restates a table already on the page.
- A `figure` panel for something the build already draws from rows, such as task waves.
- An evidence row for a command that was not run, marked as if it had been.
