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
- A chapter earns a diagram when a cold reader would otherwise have to assemble a mechanism from
  prose alone: a flow, a set of states, a before/after, or who talks to whom. Otherwise write
  `noVisual` and say why in one sentence. "Drawing this would take effort" is not a reason.

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
- A box-per-noun diagram with no arrows between the boxes.
- A diagram that restates a table already on the page.
- `noVisual` used because drawing would take effort, not because prose already carries it better.
- An evidence row for a command that was not run, marked as if it had been.
