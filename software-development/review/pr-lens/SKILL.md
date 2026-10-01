---
name: pr-lens
description: "PR Lens: draws a code change or part of a codebase as an animated architecture or data-flow diagram, standalone or on a pull request. Use when asked to diagram, visualise or visualize, or explain a change or a system, or when a pull request should carry a diagram."
license: MIT
---

# PR Lens

PR Lens represents a diff or a piece of code as one JSON document (lanes, nodes, edges, ordered flows) and renders it as an animated SVG.

## Operating manual

Diagrams stay local by default. `canvas push` (uploads to prlens.dev, a third-party service), attaching a diagram to a pull request (uploads to GitHub), publishing SVGs to an `--asset-base-url`, and `analyze` (sends code to an LLM provider) run only when the user explicitly asks for that destination.

If the user asked for a canvas, decide that before you write the document: only a canvas draws `payload`, the sample request and response on a flow step. A late decision costs another pass through steps 2 and 3.

1. **Read the diff.** When asked to represent a code change: `git diff --find-renames <base>...<head>`. The base is the merge base, not the tip of the base branch.

   If not expressing a code diff, read the code to be visually represented

2. **Write the document** to `.pr-lens/graph.json`, following `references/graph-document.md`. `references/example.graph.json` is valid reference with three lanes, all four delta states, a hero edge, a seven-step flow, a nested drill-down tree and a six-step walkthrough. Read it before you write your first one. It is quicker than reading the reference. If the user asked for a canvas, give every flow step (`messages`) that moves data a `payload` as you write it. "Sample traffic on a flow step" below says what goes in one. Only a flow step carries one. Flows need the `data-flow` lens, so an architecture view draws none.

3. **Validate, and fix**

   ```bash
   npx @coldtea/pr-lens-cli@latest validate .pr-lens/graph.json
   ```

   Fix every failure and run it again. Do not render an invalid document; do not "work around" a failure by deleting the element it names.

4. **Render.**

   ```bash
   npx @coldtea/pr-lens-cli@latest render .pr-lens/graph.json --theme light
   ```

   Render light by default unless the user requests another theme. The SVGs, the manifest and `drawn.graph.json` land in `.pr-lens/`, which the CLI adds to the repository's .gitignore. Do not commit any of it. These files are rebuilt from the diff whenever anyone wants them again. Each SVG is named after its view, the theme and a content hash; `manifest.json` lists them by lens and view, so read the names from there or from the directory.

   By default, this is the deliverable. The top view is the architecture view with `defaultOpen: true` in the document; find its SVG in `manifest.json`. Give the user the SVG paths, top view first, and open the top view locally: `open` on macOS, `xdg-open` on Linux.

   **Only when the user asks for a prlens.dev canvas:**

   ```bash
   npx @coldtea/pr-lens-cli@latest canvas push
   ```

   This uploads `.pr-lens/drawn.graph.json` to prlens.dev and prints three links. Give the user the view link, `https://prlens.dev/c/{id}`: that is the diagram, full screen, every view on one page, and it opens without a login. The edit link, the one ending in `#w=…`, lets its holder push over the canvas, so leave it out of the reply unless they ask, and never paste it anywhere public. The embed link serves the top view as an SVG for a README.

   Pushing the same file again updates the same canvas, so a follow-up such as "rename that node" or "add the queue" is: edit the document, validate, render, push. The link stays the same. If the push fails, say so and tell them where the SVGs are and which one is the top view.

5. **Attach, only when the user asked for the diagram on a pull request.** Otherwise skip this step.

   GitHub CLI uploads the diagram with the pull request. Write the body with a Markdown image pointing at the local file, then pass the same path to `--attach`. `gh` rewrites the reference to the uploaded asset and keeps the alt text you wrote:

   ```markdown
   Moves bulk sending off the per-recipient trigger and onto a batch endpoint.

   ![Architecture after this change: the queue route, the new bulk sender and the retired per-recipient path](.pr-lens/overview-light-4f9bd6c1.svg)
   ```

   ```bash
   gh pr create --title "Batch broadcast sends" --body-file .pr-lens/body.md \
     --attach .pr-lens/overview-light-4f9bd6c1.svg
   ```

   On a pull request that already exists, `gh pr edit <number>` with the same two flags puts the diagram in the description, and `gh pr comment <number>` puts it in a comment. Repeat `--attach` for each diagram the body references.

   gh has three rules:
   - The reference has to be a Markdown image, `![alt](path)`. An HTML `<img>` or `<picture>` is left as written, and the file is appended at the bottom of the body instead.
   - The alt text is the caption a reader without images gets. Say what the diagram shows, in one line.
   - `--attach` is recent in GitHub CLI. Check that `gh pr create --help` lists it before you write a body around it.

   Attach the views a reviewer needs and leave the rest in `.pr-lens/`: the top architecture view first, then a data flow if the change has a sequence worth following. A body with four diagrams reads worse than one with two, except the four are really needed to understand the change e.g., in the case of a complex feature or refactor.

   When `--attach` is not an option and the user names where to publish the SVGs, let the CLI compose the comment instead. Never pick a host yourself:

   ```bash
   npx @coldtea/pr-lens-cli@latest comment \
     --graph .pr-lens/drawn.graph.json \
     --manifest .pr-lens/manifest.json \
     --asset-base-url https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<dir>
   ```

   `--graph` takes `drawn.graph.json`, not the document you wrote, because corrections change what the diagrams show and the CLI refuses a document its manifest does not describe. `--asset-base-url` is where you published the SVGs; leave it out and the markdown points at local paths no reader can fetch. The markdown goes to stdout, with each diagram as a `<picture>` pair; posting it is your business.

If you would rather not author the document yourself, `npx @coldtea/pr-lens-cli@latest analyze --base <ref>` does steps 1 and 2 by asking a provider — Gemini, OpenAI, or any endpoint speaking `/chat/completions` — with a key of your own. It sends the diff to that provider, so run it only when the user explicitly asks for it. That is the only path here that needs a key.

## The pull request body, when there is one

This section applies only when the user asked for the diagram on a pull request, the same gate as step 5.

A reviewer should understand the change before reading the diff, so the diagram goes where they look first: the description, not a trailing comment. Open with one sentence on why the change exists, then the architecture diagram, then whatever proves the change works, such as a screenshot of the result or a recording of the interaction. Use one visual per idea. A diagram that needs a paragraph of explanation has a document problem; go back to step 2.

## What makes a document worth reading

- **Include what did not change.** A diagram of only the changed nodes says nothing about blast radius. The unchanged neighbours a change touches are the context; mark them `delta: "unchanged"`.
- **Lanes are the reader's mental model** (a runtime, a tier, a boundary), not the folder tree.
- **One hero edge**, two at the outside: the connection the change is really about.
- **Add a flow only when there is a sequence** worth animating. One good flow beats three thin ones.
- **Attach file refs**: they become the permalinks a reviewer clicks.
- **There is no findings lens.** PR Lens is the comprehension layer, not another review bot. There is no field for a bug, a risk or a security note, and a document that invents one is rejected rather than trimmed.

## Choosing architecture views

Treat architecture views as a C4-inspired decision tree, not a checklist; one useful view is enough for a small change. Read "Choosing architecture views" in `references/graph-document.md` before writing `views`.

## Writing a walkthrough

A walkthrough is a short guided tour of the diagrams: each step shows one diagram, points at one part of it, and says a few words about it. Only a canvas plays it, so write one only when the user asked for a canvas. The format leaves it optional, but for a canvas write one for anything that is not trivial: more than one diagram, a diagram with several changed parts, or any flow. Skip it only when the document is one small diagram whose single step would just repeat the title. The JSON shape, field limits and validator checks are in `references/graph-document.md`, "Walkthrough".

Aim for three to seven steps (the format allows two to twelve).

A walkthrough is the fastest read of a pull request. Each step is one change: something added, changed, removed or moved, in the order a reviewer needs it. A step is never a description of the diagram.

What counts as a step: a behaviour change, an API change, an architecture change, a data-flow change, or an addition. Unchanged parts appear only where a step needs them to make sense. The headline change is step one. An overview of everything touched, if there is one, is the last step.

- `heading`: the thing and what happened to it. Build it from change words: added, removed, replaced, now, moved, split. If a heading could have been true before the pull request, it is not a change heading.
- `body`: one line under the heading on what the change means for behaviour: what happens now that did not before, or what stops happening, with the numbers when they matter. Not a restatement of the heading, and not a description of the code. A heading with no body reads as unfinished, so the body is required.
- `stage`: open on the widest view with the focus left out, so the reader sees the whole thing before it narrows.
- `focus`: focus the elements the step's change touched, so the veil lights the change. Point at two or three of them. A step that lights half the diagram has not said anything.

Write every word for a smart twelve-year-old: short common words, one idea per line, active voice, things named as the diagram names them, numbers as digits. If a line needs a second read, rewrite it. Words like leverages, orchestrates, asynchronous pipeline and fan-out never belong in a step. This holds in whatever language the document is written in.

Keep consecutive steps on the same stage together. Every change of stage flies the camera across the canvas, so a tour that alternates between two diagrams spends its time travelling.

## Sample traffic on a flow step

A flow step can carry a `payload`: what travels on it. Only the canvas draws it, in the rail that opens when a reader clicks a step. Nothing in an SVG or a pull request comment changes. Write it when the document is going to a canvas (step 4, `canvas push`) and leave it out otherwise. Payloads add a lot of length to a document, so this is not a field to fill by default.

On a canvas document, add it to a step that moves data: a request body, a job record, a query, a result. Leave it off a step that only signals, such as a trigger with nothing attached. The JSON shape and field rules are in `references/graph-document.md`, "Sample traffic". Write `sample` as one exemplar instance after the change, with every key once, one element in any array, and long strings cut with an ellipsis. Do not write `changedPaths`; a list you write is discarded.

## What the validator will catch

The four failures that account for nearly everything:

| Code                         | What you did                                                         |
| ---------------------------- | -------------------------------------------------------------------- |
| `BROKEN_REFERENCE`           | an edge, a flow step, a view or a walkthrough step names an id you never declared |
| `INVALID_DOCUMENT`           | an invented field; the schemas are strict, unknown keys are rejected |
| `DUPLICATE_ID`               | two nodes, edges or views sharing an id                              |
| `UNSUPPORTED_SCHEMA_VERSION` | `schemaVersion` is not the contract version installed                |

Seven rules cannot be expressed in JSON Schema and are checked only by the parser, so structured output alone does not make a document valid: referential integrity, a line range that ends before it starts, a `self` message whose endpoints disagree, a patch whose two commits are the same, more views than a render manifest could describe, a walkthrough step focusing flow steps the diagram on its stage does not draw, and sample traffic past its depth or byte caps.

## Fixing a map instead of writing one

When someone says an inferred diagram is wrong (a node is misnamed, a folder should not be on it, something sits in the wrong lane), and the document came from `analyze` or the hosted App, do not edit it: it is regenerated on every run. Write the correction into `.github/pr-lens.yml`, an overlay applied over fresh inference, and read `references/config.md` for the format, selectors and recipes. A document you wrote yourself (steps 1-4) is edited directly instead.
