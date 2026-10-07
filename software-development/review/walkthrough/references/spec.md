# `review-tour.json`

The walkthrough spec. All prose lives here; the agent never edits the HTML. The build reads
this file, checks every claim against `git diff`, and renders the page from it.

Fields marked HTML are sanitized against the tag allowlist in Trust boundary below, then embedded
as HTML (`<p>`, `<code>`, `<a>`, `<b>`). Everything else is plain text and is escaped.

## Trust boundary

Ranges, counts, and coverage are validated against `git`; the agent cannot fake a line number or
a file that is not in the diff. Prose (`overview`, `intuition`, `background`, `focus` items,
chapter `overview`, file `why` in both chapters and `everythingElse`, hunk `why`, group `why`,
`verify.ran` summaries, and `verify.manual` items) is the agent's own words, and every one of these fields is
passed through an allowlist sanitizer before it reaches the page. Only `<p> <br> <b> <strong> <i>
<em> <code> <pre> <a> <ul> <ol> <li> <span>` survive; on `<a>`, only `href` survives, and only
when it is a `#` fragment, an absolute `http://` or `https://` URL, or a scheme-less relative
path. Everything else, tag or attribute, is stripped: the tag disappears but the text inside it
is kept, so a `<script>` block still shows its source as inert text rather than vanishing or
running. Sanitizing never fails the build; a hostile or malformed field is a page that reads a
little oddly, not a build error. The reader grades the prose; the build only keeps it from
executing.

```json
{
  "title": "Names the change, not a category",
  "repo": "Owner/repo",
  "base": "<full sha of the merge-base>",
  "head": "<sha> or worktree",
  "prLens": {
    "graph": "pr-lens/.pr-lens/drawn.graph.json",
    "manifest": "pr-lens/.pr-lens/manifest.json",
    "worktreeHash": "required only when head is worktree"
  },
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
  "groups": [
    { "id": "rename", "title": "fetchUser becomes loadUser", "files": ["src/*.ts"],
      "from": "fetchUser", "to": "loadUser", "regex": false, "why": "HTML (optional)" },
    { "id": "lock", "title": "Lockfile follows package.json", "files": ["package-lock.json"],
      "kind": "generated | lockfile | bulk", "why": "HTML. Required: what wrote these files." }
  ],
  "everythingElse": [{ "path": "small leftover no chapter or group claims", "why": "HTML (optional)" }],
  "verify": {
    "ran": [
      { "cmd": "npm test", "cwd": ".", "exit": 0, "ok": true, "summary": "219 passed", "tree": "head" }
    ],
    "manual": ["<HTML list item: one step and the result it should produce>"]
  }
}
```

Required: `title`, `base`, `head`, `prLens`, `overview`, `chapters`. Everything else is optional.
`repo` only enables GitHub blob links; leave it out and the page carries no external link.

## `groups` (optional)

A group places many files with one entry. It has an `id`, a `title`, and `files`, a non-empty list
of globs. The `id` must be unique across chapters and groups, and must not be `moved`,
`line-ends`, `everything-else`, `deleted`, or `binary`. It becomes the `#g-<id>` anchor, so use
kebab-case. A group has one of two shapes:

- **Substitution:** `from`, `to`, and optional `regex` (default `false`) and `why`. The build
  proves this one. It joins the old file's lines with newlines, replaces every match of `from`
  with `to`, and needs the result to equal the new file exactly. With `regex: true`, `from` is a
  Python regular expression and `to` is a `re.sub` replacement, so `\1` and `\g<name>` work. A
  renamed file replays its old path. A file passes or fails as a whole.
- **Agent's word:** `kind` (`generated`, `lockfile`, or `bulk`) and a required `why`. The build
  checks only that the globs match changed files. It takes no `from`, `to`, or `regex`.

Globs use Python `fnmatch.fnmatchcase` on the repo-relative path. Matching is case-sensitive, and
`*` also crosses `/`, so `src/*.ts` matches `src/a/b.ts`. There is no `**` rule; `src/**/*.ts` works
only because `*` already crosses `/`, and it needs at least one folder under `src/`.

### Where a changed file lands

The build places each changed file once, in this order:

1. A chapter. A chapter file never joins a group, even when a glob matches it.
2. A group whose glob matches it. A file two groups match fails. A file a group matches that is
   also in `everythingElse` fails.
3. `everythingElse`.
4. A derived group, with no spec entry: `moved` (a rename with the same content and the same
   file mode; never a copy or a symlink), then `line-ends` (only line endings or trailing spaces
   changed; indentation never counts, and Markdown never counts), then `deleted`, then `binary`.
5. Nowhere: the build fails and names the file.

A glob that matches no changed file fails. A group whose matched files all sit in chapters
fails.

### Tiers

Every changed file gets one tier:

| Tier | Files | On the page |
|---|---|---|
| `flagged` | a substitution group claimed it, but its rule does not explain the file | an open card under Read first, with the reason and any lines that broke the rule |
| `read` | in at least one `attention` or `medium` chapter | Read first |
| `skim` | only in `safe` chapters | Skim |
| `matched` | a substitution group, `moved`, `line-ends` | Matched by the build, one closed card per rule |
| `word` | an agent's-word group, `everythingElse`, `deleted`, `binary` | On the agent's word, one closed card per group |

A substitution file is flagged when it is new, deleted, a copy, binary, or changed type or file
mode, or when the replay does not give the new file. The replay must give the exact text, so a
rename plus a CRLF conversion or a changed final newline is flagged too. A flag never fails the build. The page
still shows a substitution group whose files were all flagged, so the reader sees the rule.

### Samples

Each agent's-word group with changed lines shows spot-check samples: the largest file, plus
files drawn at random up to 3 in all, or 10% of the group when that is more, at most 8. Only
files with changed text lines count. Each sample sits at a random run of changed lines, padded by
two lines, at most 40 lines. Deleted and binary groups show no sample. `--seed N` fixes the draw
for tests. Without it the seed comes from the change: the first 8 hex digits of the head commit
sha, or of the working-tree fingerprint for `worktree`, so rebuilding draws the same samples.
The page says "Samples drawn from this commit." or "Samples drawn with seed N, set by hand.",
and `--data-out` holds `seed` and `seedSource` (`commit` or `manual`).

### `everythingElse` cap

`everythingElse` holds at most `min(20, max(3, files // 10))` files, where `files` is the number
of changed files. Past that the build fails and asks for groups or chapters.

## `sheet` (optional)

An optional top-level `sheet` block puts a report sheet above the tour, so one page carries the run
facts and the walkthrough. Without it the page is unchanged. Write the words by `lib/voice.md`.

```json
"sheet": {
  "state": "Two sentences at most. What was built and what needs the reader.",
  "blocked": false,
  "facts": [{ "k": "branch", "v": "feat/outbox" }],
  "panels": [
    { "role": "needs you", "type": "asks", "rows": [{ "ask": "A short question?", "why": "Why it matters." }] },
    { "role": "tasks", "type": "tasks", "rows": [{ "id": "T1", "name": "Add the table", "status": "done" }] },
    { "role": "review", "type": "findings", "rows": [] },
    { "role": "decisions", "type": "decisions", "rows": [] }
  ]
}
```

- `title` and `kind` come from the tour. The kind is always `execute`. Do not write `title`, `kind`, or `tree`.
- The builder makes two panels. `checks` comes from `verify.ran` (command, cwd, exit code). A row
  shows a result only when its `summary` is one short plain sentence. `files` comes from the tour's
  base and head. Do not write either panel: the build fails with "walkthrough builds checks and files itself".
- You write the other panels: `needs you` (first), `tasks`, `review`, and `decisions`. Each is
  required. Panel fields, row fields, and the voice lint are the same as in `brief`.
- A panel may carry `more`: a chapter `id` from this tour. So may a row in an `asks`, `checks`, `decisions`,
  `tasks`, `findings`, `claims`, `commands`, or `matrix` panel. It shows a link to that chapter. An unknown id fails the build.
- Panel letters follow the order on the page: `needs you` is A, `checks` is B, `files` is C.
- The digest block shows under the page header whether or not a sheet is present.
- When the build flags a file, it adds a first row to `needs you` and the stamp reads NEEDS YOU; your own asks follow it.
- Asks can carry `options`, `recommended`, and `multi` the same way; see the brief spec.
- One floating "Send feedback" button, bottom right, covers both: it adds the sheet answers, notes, and fix or skip
  choices to the tour notes. It is the same dock as the brief's, with the same toast and "✓ Sent" flip.
  Inside a claude.ai artifact viewer it also writes the doc `feedback/latest`, with the brief's fields. Tour
  chapter notes sit in `notes` by chapter id, plus `general`. "Back to sheet" shows only when the tour has a sheet.
- The tour header shows the project and branch as chips, read from `--repo-root` with git. The project is the
  main repo folder, even in a worktree; a detached head reads `detached at <sha>`. The chips are larger when
  there is no sheet. The page title reads `project · branch · title`.
- If a sheet build fails, the page at `--out` becomes a BUILD FAILED page that shows the error.
  A build without a sheet leaves the old page in place.

## PR Lens views

`prLens.graph` and `prLens.manifest` are POSIX paths relative to `review-tour.json`. Absolute
paths, URLs, `..`, backslashes, missing files, and symlink escapes fail the build. The graph must
be the `drawn.graph.json` written beside the manifest, with provenance matching this tour's base
and head. For a working-tree tour, its head is the current `HEAD` commit.

For `"head": "worktree"`, `prLens.worktreeHash` binds the rendered graph to the exact tracked and
untracked contents. Generate it immediately after PR Lens renders:

```bash
python3 <skill-dir>/scripts/build_tour.py \
  --repo-root . --print-worktree-hash <base>
```

Any later working-tree edit makes the build fail until PR Lens is rendered again and the hash is
recomputed. Omit `worktreeHash` for a committed head.

The build compares the graph's complete flattened view tree with the manifest. Every logical view
must appear exactly once per rendered theme, and all views must carry the same theme set. Asset
ids and paths are unique; byte counts and SHA-256 content hashes must match. The total embedded
SVG payload is capped at 16 MiB.

The manifest's graph content hash must match the canonical `drawn.graph.json`, preventing a stale
render from being paired with a newer graph that happens to retain the same view ids.

SVGs are parsed before embedding. Scripts, event handlers, DTDs, entities, executable content,
external resources, and resource-bearing elements fail the build. Internal fragment references
such as `url(#dots)` survive. Accepted SVG bytes are base64-encoded into `<picture>` elements, so
the output remains one self-contained HTML file with light/dark theme selection.

## Revisions

- `"head": "<sha>"` compares `base..head`. Both must resolve to a commit or the build fails.
- `"head": "worktree"` compares `base` to the working tree: tracked changes from
  `git diff base`, plus every file from `git ls-files --others --exclude-standard` as `A`. New
  side content is read from disk, old side from `git show base:path`.
- Reader progress is stored under `walkthrough:<head>` for a sha, and under a hash of the diff
  for a working tree, so editing the tree starts the reader fresh.

## What the build checks

- Every file in the diff lands somewhere; see Where a changed file lands. A placed path that is
  not in the diff fails. A path in both a chapter and `everythingElse` fails.
- `everythingElse` stays under its cap, and every group is valid; see `groups`.
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
- Every logical PR Lens view has exactly one asset for each rendered theme. The graph and
  manifest revisions, asset hashes, byte counts, paths, and SVG trust boundary all validate.

Prose fields are sanitized, never rejected; see Trust boundary above. A failure prints `build_tour: <the defect>` on stderr, exits 1, and writes nothing, so a failed
build leaves the previous page in place (a build with a `sheet` writes a BUILD FAILED page instead). Fix the spec, never the page.

## What the build derives

- Per file: status (`A`, `M`, `D`, `R`, `C`, `T`, or binary), added and removed line counts, and
  the names the added lines introduce (declarations, class methods, `describe` and `it` titles,
  Python `def` and `class`, Go and Rust declarations, shell functions, Markdown headings). Skipped
  entirely for `.html`, `.htm`, `.css`, `.json`, and `.txt`. Names under 3 characters, and names
  made only of `$` or `_`, are dropped; the whole list is suppressed for a file when more than a
  third of what is left is still under 4 characters. A file spanning several chapters lists only
  the names its own hunks introduce.
- Per hunk: the rendered rows with `+`, `-`, and context markers and real line numbers, a
  "Copy as prompt" payload (repo when set, revision, `path:start-end`, chapter title, hunk text),
  and a blob link when `repo` is set and the side has a commit to link to.
- Stats: `filesChanged`, `filesPlaced`, `everythingElse`, `linesAdded`, `linesRemoved`,
  `linesShown`, `linesChanged`, `coveragePercent`, `linesUnshownInOpenedFiles`,
  `linesUnshownInUnopenedFiles`, `hunksShown`, `chapters`, `attentionChapters`. `linesShown`
  counts distinct changed lines actually rendered by a hunk, on either side; `coveragePercent` is
  `linesShown` over `linesChanged`. `linesUnshownInOpenedFiles` counts unshown changed lines in
  files that have at least one hunk on the page; `linesUnshownInUnopenedFiles` counts the rest, in
  files that are never opened (no hunk in any chapter, or listed in `everythingElse`). `flagged`
  counts flagged files. `digest` holds `seed`, `seedSource`, `counts` (files per tier), `lines` (changed lines:
  `total`, `read` for flagged, read, and skim files, `matched`, `word`, and `sampled`, the changed
  lines the samples show), `tiers` (every path to its tier), `groups` (`id`, `kind`, `tier`,
  `files`, and `samples` as `path`, `side`, `start`, `end`), and `flags` (`path`, `group`,
  `reason`). `--data-out` writes the stats as JSON.
- The digest block under the page header: a budget line, a bar of files per tier, a map with one
  square per file that links to its card, and a line that splits the changed lines by tier.
- The "Changed lines only" toggle is hidden when no rendered hunk holds a context row, since
  there is nothing for it to hide.
- Hunk rows are syntax-highlighted at build time by file extension (python, js/ts, go, rust, shell, json, css, html, markdown, yaml, toml, sql, make); unknown types render plain.

## Anchors

- Chapter: `#ch-<id>`. File card: `#f-<chapter id>-<slug of path>`.
- Hunk: `#f-<chapter id>-<slug of path>-<side>-<start>`.
- Digest block: `#digest`. Flagged card: `#flag-<slug of path>`. Group card: `#g-<group id>`,
  derived groups included. Sample card: `#f-sample-<group id>-<slug of path>`.
- A link to a card inside a closed card opens every card around it.

## Outputs

- `--out` writes a full document: doctype, `<html>`, `<head>`, `<body>`.
- `--fragment` writes the same content without those wrappers: `<title>`, `<style>`, the body,
  then `<script>`. That is what the Claude Code Artifact tool wants, since it supplies the
  document itself.
- Both are self-contained. No fonts, scripts, or images are fetched.
- On success stdout prints `build_tour: ok files=... placed=... else=... hunks=... chapters=...
  pr-lens=... lines shown ... tiers flagged=.. read=.. skim=.. matched=.. word=..`. When files are
  flagged, stderr also prints `build_tour: warning: <n> files broke a rule: <path> (<group id>),
  ...` and the exit code stays 0.
- Every PR Lens logical view is embedded before the prose tour, in graph order. Light and dark
  assets become one `<picture>` when both exist.
