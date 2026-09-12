# `brief.json`

The brief spec. All prose lives here; the agent never edits the HTML. The build reads this
file, checks every field against the rules below, and renders the page from it.

Fields marked HTML are sanitized against the tag allowlist in Trust boundary below, then
embedded as HTML (`<p>`, `<code>`, `<a>`, `<b>`). Everything else is plain text and is escaped.
`mermaid` is neither: it is diagram source, escaped and placed inside `<pre class="mermaid">`
as inert text, never interpreted as HTML or executed. `svg` is neither, either: it is untrusted
markup, checked against a strict element and attribute denylist and re-serialized, not sanitized
by stripping.

## Trust boundary

`context`, `state`, chapter `prose`, figure `caption`, decision `why`, evidence `summary`, and
`open[]` items are the agent's own words, and every one of these fields is passed through an
allowlist sanitizer before it reaches the page. Only `<p> <br> <b> <strong> <i> <em> <code> <pre>
<a> <ul> <ol> <li> <span>` survive; on `<a>`, only `href` survives, and only when it is a `#`
fragment, an absolute `http://` or `https://` URL, or a scheme-less relative path. Everything
else, tag or attribute, is stripped: the tag disappears but the text inside it is kept.
Sanitizing never fails the build; a hostile or malformed field is a page that reads a little
oddly, not a build error.

`cmd`, `cwd`, `decision`, `chosen`, `rejected`, and `noVisual` are plain text: escaped, not
sanitized, since they carry no markup. `visual.mermaid` is diagram source: escaped and placed as
the text content of a `<pre>`, so a `<script>` inside it renders as inert text, never as markup.

A figure's `svg` is untrusted markup, not prose: it is parsed as XML and checked against a strict
denylist of elements and attributes (see "What the build checks" below). A figure that fails this
check is a build failure naming the chapter and figure index, not stripped or sanitized down to
something safe; the agent fixes the drawing and rebuilds. A figure that passes is re-serialized
and embedded as literal markup, since only markup that has already been proven safe reaches the
page this way.

```json
{
  "title": "Names what happened, not a category",
  "kind": "plan | execution | investigation | mixed",
  "context": "<p>HTML. One paragraph: what this session set out to do. 40 to 120 words.</p>",
  "state": "<p>HTML. Where things stand now, in 1 to 3 sentences. Required.</p>",
  "chapters": [
    {
      "id": "kebab-case",
      "title": "States its claim",
      "prose": "<p>HTML. At most 120 words. Sentences of at most 25 words.</p>",
      "visual": {
        "mermaid": "flowchart LR\n  a[Handler] -->|writes| b[(Outbox)]",
        "caption": "One sentence, at most 25 words: what the picture shows."
      },
      "noVisual": "why a picture would not beat the prose here",
      "decisions": [
        { "decision": "Where retries live", "chosen": "Worker", "rejected": "Handler", "why": "Failing twice is free off the request path." }
      ],
      "evidence": [
        { "cmd": "npm test", "cwd": ".", "exit": 0, "ok": true, "summary": "219 passed" },
        { "cmd": "npm run e2e", "cwd": ".", "exit": null, "summary": "not run" }
      ]
    }
  ],
  "open": ["<HTML list item: an unresolved question or a next step, one per item>"]
}
```

Required: `title`, `kind`, `state`, `chapters`. `context` and `open` are optional. Per chapter,
`id`, `title`, `prose` are required; exactly one of `visual` or `noVisual` is required (both or
neither fails the build); `decisions` and `evidence` are optional arrays.

## Figures

`visual` is either one figure object or an array of 1 to 4 of them, rendered in order:

```json
{ "mermaid": "flowchart LR\n  a --> b", "caption": "One sentence, at most 25 words." }
{ "svg": "<svg viewBox=\"0 0 640 320\" role=\"img\" aria-label=\"...\">...</svg>", "caption": "One sentence, at most 25 words." }
```

Exactly one of `mermaid` or `svg` per figure; `caption` is required on every figure. An `svg`
figure's root must carry `viewBox`; `width`/`height` on the root are stripped, since CSS sizes the
figure. Disallowed anywhere in the tree: `<script>`, `<style>`, `<foreignObject>`, `<iframe>`,
`<image>`, `<a>`, a `<use>` whose `href` is not a `#` fragment, any attribute starting with `on`,
any `href`/`xlink:href` that is not a `#` fragment, and any attribute value containing `url(...)`
unless it is `url(#...)`. A figure that fails any of these is a build failure naming the chapter
and the figure's index, never silently stripped down to something safe: the agent fixes the
drawing. A valid svg figure is capped at 64 KB serialized and is re-serialized with a normalized
`xmlns="http://www.w3.org/2000/svg"` on the root, so no `ns0:`-style prefix ever reaches the page
regardless of how the input declared its namespaces.

Mermaid figures are unchanged: `mermaid` must be non-empty and its first diagram line must start
with a recognized type (below).

## What the build checks

Every failure prints `build_brief: <the defect>` on stderr, exits 1, and writes nothing, so a
failed build leaves the previous page in place. Fix the spec, never the page.

- The spec is valid JSON, and `title`, `kind`, `state`, `chapters` are all present.
- `kind` is one of `plan`, `execution`, `investigation`, `mixed`.
- 1 to 8 chapters. Every chapter id is kebab-case and unique.
- Each chapter has `id`, `title`, `prose`.
- Exactly one of `visual` or `noVisual` per chapter. `noVisual` must be a non-empty string.
  `visual` must be a figure object or an array of 1 to 4 figures. Each figure needs exactly one
  of `mermaid` or `svg`, and a non-empty `caption` of at most 25 words.
  A `mermaid` figure must be non-empty; its first non-blank line, after skipping any leading
  `---`-delimited frontmatter block and any `%%{init...}%%` directive (in either order), must
  start with one of: `flowchart`, `graph`, `sequenceDiagram`, `stateDiagram`, `stateDiagram-v2`,
  `classDiagram`, `erDiagram`, `journey`, `gantt`, `pie`, `quadrantChart`, `timeline`, `mindmap`,
  `sankey-beta`, `xychart-beta`, `block-beta`, `gitGraph`, `C4Context`. Otherwise the build fails,
  naming the chapter, the figure's index, and the line it found.
  An `svg` figure must parse as XML with an `<svg>` root carrying `viewBox`; `width`/`height` on
  the root are stripped. Disallowed anywhere in the tree: `<script>`, `<style>`,
  `<foreignObject>`, `<iframe>`, `<image>`, `<a>`, a `<use>` with a non-`#` `href`, any attribute
  starting with `on`, any `href`/`xlink:href` that is not a `#` fragment, and any attribute value
  containing `url(...)` unless it is `url(#...)`. Failing any of these fails the build, naming the
  chapter and figure index; nothing is stripped to make it pass. A passing figure is capped at
  64 KB serialized and is re-serialized with `xmlns="http://www.w3.org/2000/svg"` normalized onto
  the root, so no `ns0:` prefix leaks regardless of the input's own namespace declarations.
- If `mmdc` is on `PATH`, every mermaid figure is rendered to a scratch SVG under `$TMPDIR` with
  `mmdc -i <tmp.mmd> -o <tmp.svg> -q`. A non-zero exit fails the build with mmdc's stderr, the
  chapter id, and the figure's index. `--no-mmdc` skips this check entirely. When `mmdc` is
  absent, the build prints one line, `build_brief: mmdc not found, mermaid syntax unchecked`, to
  stderr and continues; this is not a failure.
- Word caps, counted on the sanitized text with every tag stripped: chapter `prose` at most 120
  words, `context` at most 120 words, `state` at most 60 words. Over the cap fails, naming the
  field (and the chapter, for `prose`) and the count.
- Sentence cap: in `prose`, `context`, and `state`, no sentence may run past 25 words. A sentence
  is whatever sits between a `.`, `?`, or `!` followed by whitespace or the end of the text; this
  splitter does not know about abbreviations or decimal numbers, so a string like "v2.0 shipped"
  can split where it should not. Write plain sentences and this rarely matters. A failure names
  the field (and chapter, for `prose`) and the sentence's first five words.
- Every `decisions[]` row needs `decision`, `chosen`, `rejected`, `why`, all non-empty.
- Every `evidence[]` row needs `cmd` and `cwd`, and `exit` as an integer or `null`. `ok`, when
  present, must be `true` or `false`. `summary` is optional. `exit: null` renders as "not run".
- Every `open[]` item is a string.

## What the build derives

`chapters`, `visuals` (total figures across all chapters, mermaid and svg combined),
`mermaidFigures`, `svgFigures`, `noVisuals` (chapters with a stated reason instead of a figure),
`decisions` (total rows across all chapters), `evidenceRan` (evidence rows with a non-null
`exit`), `evidenceNotRun` (rows with `exit: null`), and `words` (total prose words across
`context`, `state`, and every chapter's `prose`, counted the same way as the word caps above).
These render in the stats strip under the banner; counts never appear in prose. The build's own
ok line also reports the svg count: `build_brief: ok chapters=N visuals=N noVisuals=N svg=N
decisions=N evidence=N/M words=N`.

## Page order

Banner (title, kind label, build timestamp) → stats strip → Context (if present) → State
(a visually distinct box: this is "where things stand") → chapters in order, each: title, its
figure(s) side by side in reading order or nothing (a `noVisual` reason is never rendered on the
page; it exists only to satisfy the build) → prose → decisions table if any → evidence table if
any → Open items (if any) → Notes.

## Figure rendering

Every figure, mermaid or svg, renders as `<figure class="fig">...<figcaption>` inside a chapter's
`<div class="figs">`, so multiple figures lay out in a grid in spec order.

- A mermaid figure's markup is unchanged: `<pre class="mermaid">`, escaped diagram source as
  inert text.
- An svg figure's validated, re-serialized markup is embedded directly inside
  `<div class="svg">`, since only markup that already passed the denylist reaches this point.
  `.fig svg{max-width:100%;height:auto;display:block}` sizes it from the template; `color` on
  `.fig` is the page's ink token, so a drawing that uses `currentColor` themes with the page.
- The fragment output (`--fragment`) emits `<pre class="mermaid">` blocks as-is and loads no
  mermaid script; the Claude Artifact host renders mermaid blocks natively. svg figures need no
  script either way.
- The full document (`--out`) additionally loads
  `https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.1/mermaid.min.js` (pinned) right after the
  page's own script, then calls `mermaid.initialize({startOnLoad:true, theme: ...})`, picking
  dark or default from the browser's colour scheme. Offline, or if the CDN is unreachable, the
  `<pre>` text is still readable; this is the intended fallback, not a bug.
- The page is otherwise self-contained: no other font, script, or image is fetched.

## Notes and feedback

A textarea per chapter (`data-note="<chapter id>"`), persisted in this browser's `localStorage`
under `data-storage-key="brief:<sha256 of the spec's raw bytes, first 12 hex characters>"`, so
editing and rebuilding the spec starts feedback fresh. "Copy feedback" builds a plain-text block:
`# Feedback on <title>`, then one `## <chapter title>` heading and the note text for every
chapter with a non-empty note. A brief with no notes copies `(no notes written)`.

## Outputs

- `--out` writes a full document: doctype, `<html>`, `<head>`, `<body>`, the mermaid CDN script.
- `--fragment` writes the same content without those wrappers or the mermaid script: `<title>`,
  `<style>`, the body, then `<script>`. This is what the Claude Code Artifact tool wants, since
  the host renders `<pre class="mermaid">` blocks itself.
- `--data-out` writes the derived stats (see above) as JSON.
