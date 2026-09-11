# `review-tour.json`

The walkthrough spec. All prose lives here; the agent never edits the HTML. The build reads
this file, checks every claim against `git diff`, and renders the page from it.

Fields marked HTML are rendered as-is (`<p>`, `<code>`, `<a>`, `<b>`). Everything else is plain
text and is escaped.

## Trust boundary

Ranges, counts, and coverage are validated against `git`; the agent cannot fake a line number or
a file that is not in the diff. Prose (`overview`, `intuition`, `background`, `focus` items,
chapter `overview`, file `why`, hunk `why`, `verify.ran` summaries, and `verify.manual` items) is
the agent's own words, rendered as HTML with no further check beyond a blocklist on the handful
of tags that can run script: `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:`,
`on*=` handlers, `<style>`, `<link>`, `<meta>`. A prose field that matches one of these fails the
build by name. The reader grades the prose; the build only keeps it from executing.

```json
{
  "title": "Names the change, not a category",
  "repo": "Owner/repo",
  "base": "<full sha of the merge-base>",
  "head": "<sha> or worktree",
  "overview": "<p>HTML. What changed and why, 100 to 250 words.</p>",
  "focus": ["<HTML list item: what to check, linking a chapter with <a href=\"#ch-id\">"],
  "intuition": "<p>HTML. The mental model to hold before the tour.</p>",
  "background": "<p>HTML. What the reader must know about the surrounding code.</p>",
  "chapters": [
    {
      "id": "kebab-case",
      "title": "States its claim",
      "risk": "attention | medium | safe",
      "overview": "<p>HTML. Two to six sentences: what changed here, why, what to check.</p>",
      "files": [
        {
          "path": "src/thing.ts",
          "why": "HTML. One sentence on why this file is in this chapter (optional).",
          "entities": ["override the derived name list (optional)"],
          "hunks": [
            { "side": "new", "start": 35, "end": 46, "why": "HTML. Why it matters (optional)." }
          ]
        }
      ]
    }
  ],
  "everythingElse": [{ "path": "changed file no chapter claims", "why": "HTML (optional)" }],
  "verify": {
    "ran": [
      { "cmd": "npm test", "cwd": ".", "exit": 0, "ok": true, "summary": "219 passed", "tree": "head" }
    ],
    "manual": ["<HTML list item: one step and the result it should produce>"]
  }
}
```

Required: `title`, `base`, `head`, `overview`, `chapters`. Everything else is optional.
`repo` only enables GitHub blob links; leave it out and the page carries no external link.

## Revisions

- `"head": "<sha>"` compares `base..head`. Both must resolve to a commit or the build fails.
- `"head": "worktree"` compares `base` to the working tree: tracked changes from
  `git diff base`, plus every file from `git ls-files --others --exclude-standard` as `A`. New
  side content is read from disk, old side from `git show base:path`.
- Reader progress is stored under `walkthrough:<head>` for a sha, and under a hash of the diff
  for a working tree, so editing the tree starts the reader fresh.

## What the build checks

- Every file in the diff appears in at least one chapter or in `everythingElse`. A placed path
  that is not in the diff fails. A path in both a chapter and `everythingElse` fails.
- A file may sit in several chapters when it carries several concepts. No changed line may be
  shown twice across the whole page.
- A hunk range lies inside the file on its side (`new` reads the head or worktree file, `old`
  reads the base file) and holds at least one changed line: an added line, or a removed block
  attached to a line in the range.
- `risk` is `attention`, `medium`, or `safe`. `side` is `new` or `old`. Chapter ids are unique.
  Chapters: 1 to 10. A hunk needs integer `start` and `end` with `start <= end`.
- A binary file can hold no hunk.
- Every `verify.ran` row needs `cwd`, a repo-root-relative path (`"."` for the repo root). A row
  missing it fails, naming its index.
- `verify.ran[].ok`, when present, must be `true` or `false`.
- Every prose field is checked against the tag blocklist in Trust boundary above.

A failure prints `build_tour: <the defect>` on stderr, exits 1, and writes nothing, so a failed
build leaves the previous page in place. Fix the spec, never the page.

## What the build derives

- Per file: status (`A`, `M`, `D`, `R`, `C`, `T`, or binary), added and removed line counts, and
  the names the added lines introduce (declarations, class methods, `describe` and `it` titles,
  Python `def` and `class`, Go and Rust declarations, shell functions). Skipped entirely for
  `.html`, `.htm`, `.css`, `.md`, `.json`, and `.txt`. Names under 3 characters, and names made only
  of `$` or `_`, are dropped; the whole list is suppressed for a file when more than a third of
  what is left is still under 4 characters. A file spanning several chapters lists only the names
  its own hunks introduce.
- Per hunk: the rendered rows with `+`, `-`, and context markers and real line numbers, a
  "Copy as prompt" payload (repo when set, revision, `path:start-end`, chapter title, hunk text),
  and a blob link when `repo` is set and the side has a commit to link to.
- Stats: `filesChanged`, `filesPlaced`, `everythingElse`, `linesAdded`, `linesRemoved`,
  `linesShown`, `linesChanged`, `coveragePercent`, `hunksShown`, `chapters`, `attentionChapters`.
  `linesShown` counts distinct changed lines actually rendered by a hunk, on either side;
  `coveragePercent` is `linesShown` over `linesChanged`. Below 30% the page adds a one-line notice
  under the stats strip. `--data-out` writes the stats as JSON.
- The "Changed lines only" toggle is hidden when no rendered hunk holds a context row, since
  there is nothing for it to hide.

## Anchors

- Chapter: `#ch-<id>`. File card: `#f-<chapter id>-<slug of path>`.
- Hunk: `#f-<chapter id>-<slug of path>-<side>-<start>`.
- Everything else card: `#f-everything-else-<slug of path>`.

## Outputs

- `--out` writes a full document: doctype, `<html>`, `<head>`, `<body>`.
- `--fragment` writes the same content without those wrappers: `<title>`, `<style>`, the body,
  then `<script>`. That is what the Claude Code Artifact tool wants, since it supplies the
  document itself.
- Both are self-contained. No fonts, scripts, or images are fetched.
