# `brief.json`

The brief spec. All prose lives here; the agent never edits the HTML. The build reads this
file, checks every field against the rules below, and renders the page from it.

Fields marked HTML are sanitized against the tag allowlist in Trust boundary below, then
embedded as HTML (`<p>`, `<code>`, `<a>`, `<b>`). Everything else is plain text and is escaped.
`mermaid` is neither: it is diagram source, escaped and placed inside `<pre class="mermaid">`
as inert text, never interpreted as HTML or executed.

## Trust boundary

`context`, `state`, chapter `prose`, `visual.caption`, decision `why`, evidence `summary`, and
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
        "caption": "One sentence: what the picture shows."
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

## What the build checks

Every failure prints `build_brief: <the defect>` on stderr, exits 1, and writes nothing, so a
failed build leaves the previous page in place. Fix the spec, never the page.

- The spec is valid JSON, and `title`, `kind`, `state`, `chapters` are all present.
- `kind` is one of `plan`, `execution`, `investigation`, `mixed`.
- 1 to 8 chapters. Every chapter id is kebab-case and unique.
- Each chapter has `id`, `title`, `prose`.
- Exactly one of `visual` or `noVisual` per chapter. `noVisual` must be a non-empty string.
  `visual.mermaid` must be non-empty; its first non-blank line, after skipping any leading
  `---`-delimited frontmatter block and any `%%{init...}%%` directive (in either order), must
  start with one of: `flowchart`, `graph`, `sequenceDiagram`, `stateDiagram`, `stateDiagram-v2`,
  `classDiagram`, `erDiagram`, `journey`, `gantt`, `pie`, `quadrantChart`, `timeline`, `mindmap`,
  `sankey-beta`, `xychart-beta`, `block-beta`, `gitGraph`, `C4Context`. Otherwise the build fails,
  naming the chapter and the line it found.
- If `mmdc` is on `PATH`, every mermaid block is rendered to a scratch SVG under `$TMPDIR` with
  `mmdc -i <tmp.mmd> -o <tmp.svg> -q`. A non-zero exit fails the build with mmdc's stderr and the
  chapter id. `--no-mmdc` skips this check entirely. When `mmdc` is absent, the build prints one
  line, `build_brief: mmdc not found, mermaid syntax unchecked`, to stderr and continues; this is
  not a failure.
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

`chapters`, `visuals` (chapters with a diagram), `noVisuals` (chapters with a stated reason
instead), `decisions` (total rows across all chapters), `evidenceRan` (evidence rows with a
non-null `exit`), `evidenceNotRun` (rows with `exit: null`), and `words` (total prose words
across `context`, `state`, and every chapter's `prose`, counted the same way as the word caps
above). These render in the stats strip under the banner; counts never appear in prose.

## Page order

Banner (title, kind label, build timestamp) → stats strip → Context (if present) → State
(a visually distinct box: this is "where things stand") → chapters in order, each: title, visual
or nothing (a `noVisual` reason is never rendered on the page; it exists only to satisfy the
build) → prose → decisions table if any → evidence table if any → Open items (if any) → Notes.

## Mermaid rendering

- The fragment output (`--fragment`) emits `<pre class="mermaid">` blocks only and loads no
  mermaid script; the Claude Artifact host renders mermaid blocks natively.
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
