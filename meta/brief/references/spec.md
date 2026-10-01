# `brief.json`

The brief spec. All prose lives here; the agent never edits the HTML. The build reads this
file, checks every field against the rules below, and renders the page from it.

## Field types

- **HTML fields:** `context`, `state`, chapter `prose`, figure `caption`, decision `why`, evidence
  `summary`, and `open[]` items. They are sanitized and embedded as HTML. Only `<p> <br> <b>
  <strong> <i> <em> <code> <pre> <a> <ul> <ol> <li> <span>` survive; on `<a>`, only `href`
  survives, and only when it is a `#` fragment, an absolute `http://` or `https://` URL, or a
  scheme-less relative path. Everything else is stripped, keeping the text inside it. Sanitizing
  never fails the build; a malformed field is a page that reads oddly, not a build error.
- **Plain text:** `cmd`, `cwd`, `decision`, `chosen`, `rejected`, and `noVisual`.
- **Diagram source:** `visual.mermaid`.
- **Untrusted markup:** `visual.svg`, validated against the allowlist under Figures.

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
      "figureLayout": "row",
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
neither fails the build); `decisions`, `evidence`, and `figureLayout` are optional.

## Figures

`visual` is either one figure object or an array of 1 to 4 of them, rendered in order:

```json
{ "mermaid": "flowchart LR\n  a --> b", "caption": "One sentence, at most 25 words." }
{ "svg": "<svg viewBox=\"0 0 640 320\" role=\"img\" aria-label=\"...\">...</svg>", "caption": "One sentence, at most 25 words." }
```

Exactly one of `mermaid` or `svg` per figure, both as non-empty strings; `caption` is required on
every figure as a non-empty string, at most 25 words. An `svg` figure's root must carry `viewBox`;
`width`/`height` on the root are stripped, since CSS sizes the figure.

`figureLayout` is absent (figures stack full width) or exactly `"row"` (side by side); any other
value fails the build. `references/authoring.md` says when `row` is right.

A `mermaid` figure's first non-blank line, after skipping any leading `---`-delimited frontmatter
block and any `%%{init...}%%` directive (in either order), must start with one of: `flowchart`,
`graph`, `sequenceDiagram`, `stateDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`,
`journey`, `gantt`, `pie`, `quadrantChart`, `timeline`, `mindmap`, `sankey-beta`, `xychart-beta`,
`block-beta`, `gitGraph`, `C4Context`. If `mmdc` is on `PATH`, every mermaid figure is also rendered
through it and a non-zero exit fails the build; `--no-mmdc` skips that, and without `mmdc` the
build prints `build_brief: mmdc not found, mermaid syntax unchecked` and continues.

An `svg` is checked against an **allowlist**: every element and attribute has to be named below,
or the build fails naming the chapter, the figure's index, and the offending tag or attribute.
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
  `role`/`aria-*`, `xml:space`, `lang`, `xmlns`. See `SVG_ALLOWED_ATTRS` in `build_brief.py` for
  the exact list; anything not on it fails by name, including `style` and every `on*` handler.
- **`href`/`xlink:href`** are accepted only on `use`, `textPath`, `pattern`, `linearGradient`,
  `radialGradient`, and only as a `#local` reference.
- **Values:** any attribute value containing `url(...)` must be `url(#local)`; any value
  containing `javascript:` or `data:` fails, wherever it appears.
- **Size:** the raw `svg` string is capped at 64 KB, and the re-serialized markup is capped at
  64 KB again.

## What the build checks

Every failure prints `build_brief: <the defect>` on stderr, exits 1, and writes nothing.

- The spec is valid JSON, and `title`, `kind`, `state`, `chapters` are all present.
- `kind` is one of `plan`, `execution`, `investigation`, `mixed`.
- 1 to 8 chapters. Every chapter id is kebab-case and unique.
- Each chapter has `id`, `title`, `prose`.
- Exactly one of `visual` or `noVisual` per chapter. `noVisual` must be a non-empty string.
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

The stats strip under the banner shows counts the build derives: chapters, figures, chapters with
a `noVisual` reason, decisions, evidence rows run and not run, and total prose words. Counts never
appear in prose. `--data-out` writes the same stats as JSON.

## On the page

A `noVisual` reason is never rendered; it exists only to satisfy the build. `state` renders as a
visually distinct box: it is "where things stand". The page imports its fonts (Geist, Geist Mono,
Instrument Serif) from Google Fonts and falls back to system stacks offline.

Notes are a textarea per chapter, stored in this browser's `localStorage` under a key derived from
the spec's raw bytes, so editing and rebuilding the spec starts feedback fresh. "Copy feedback"
builds a plain-text block: `# Feedback on <title>`, then one `## <chapter title>` heading and the
note text for every chapter with a non-empty note, or `(no notes written)`.

## Outputs

- `--out` writes a full document: doctype, `<html>`, `<head>`, `<body>`, and the mermaid CDN
  script, initialised with `securityLevel: 'strict'` so mermaid's own HTML-label escape hatch
  stays off.
- `--fragment` writes the same content without those wrappers or the mermaid script. This is what
  the Claude Code Artifact tool wants, since the host renders mermaid blocks itself.
- `--data-out` writes the derived stats as JSON.
