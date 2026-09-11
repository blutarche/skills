---
name: walkthrough
description: Build a browser walkthrough of a finished implementation (branch or working-tree diff) as one self-contained HTML page: chapters by concept, only the hunks the prose claims, every line validated against git, plus a verify section and notes that export as feedback. Use when the user asks to walk through, explain, or tour a diff or implementation result before reviewing it.
---

# Walkthrough

One page a reader opens instead of the raw diff. It is a **pure explainer**: chapters cut by
concept in reading order, each showing only the hunks its prose makes a claim about, every line
number checked against the real diff by the build. No verdicts, no findings, no severities. If a
review is wanted, that is a different skill.

All prose lives in `review-tour.json`. The agent never edits HTML: `scripts/build_tour.py`
validates the spec against `git diff` and renders the page. A rejected spec is a fact about the
diff, not a formatting problem.

This skill is read-only with respect to the repository. It writes only under the temp directory.

## Steps

### 1. Fix the revision

Base: the first of `main` or `master` that exists; if neither does, ask which branch to compare
against. Then `BASE=$(git merge-base <base> HEAD)`.

Head: `worktree` when `git status --porcelain` is non-empty (the default, so uncommitted work is
included), otherwise `git rev-parse HEAD`.

Arguments override the default: a commit range uses its two ends; a PR number means
`gh pr checkout <n>` first, then the same flow. Local git only in this version. A path filter is
not supported; if the user asks for one, say so and walk the whole diff.

Done when: `BASE` and the head value are written down, and `git diff --name-status $BASE..HEAD`
(or `git diff --name-status $BASE` for a working tree) is in front of you.

### 2. Read the change

`git diff --stat`, then read the hunks of every changed file. Find the heart of the change and
the contract it exposes. You cannot cut chapters from a file list; you need to know what the
change does.

Done when: you can say in one sentence what changed and why, without naming a folder.

### 3. Write the spec

Write `review-tour.json` in `${TMPDIR:-/tmp}/walkthrough/<repo-name>-<branch-slug>/`. Format:
`references/spec.md`. Rules: `references/authoring.md`. Shape to copy:
`examples/review-tour.example.json`.

- Chapters cut by concept in reading order: contract, then the heart, then consequences, then
  glue. One to six of them.
- The hunk rule: a hunk appears only when the prose claims something about it. Every other file
  in the chapter is a card.
- Every changed file lands in a chapter or in `everythingElse`.
- `focus` names chapters by their `#ch-<id>` anchor.
- `verify.ran` lists the commands you actually ran this session with their real exit codes. A
  command you did not run is written out as not run, with `exit: null`.
- `verify.manual` gives steps the reader can run, each with its expected result.

Done when: the spec is valid JSON and every changed file from step 1 appears in it.

### 4. Build

```bash
python3 <skill-dir>/scripts/build_tour.py \
  --spec  "$DIR/review-tour.json" \
  --repo-root . \
  --out "$DIR/tour.html" \
  --fragment "$DIR/tour.fragment.html"
```

A failure names the defect: a range with no changed line, a file placed nowhere, a line shown
twice. Fix the spec, never the page, and build again.

Done when: the build prints `build_tour: ok files=... placed=... else=... hunks=... chapters=...`
and those numbers match what you expected.

### 5. Deliver

**Claude Code with the Artifact tool:** publish `tour.fragment.html` as an artifact (title = the
spec title, favicon a compass), and give the user the link. Feedback comes back as comment
threads on the artifact; read them with the tool's `comments` action when the user says they have
commented.

**Any other agent, or no Artifact tool:** `open "$DIR/tour.html"` on macOS, `xdg-open` on Linux.
Feedback comes back through the page: Notes, then "Copy feedback", then paste into the chat.

Print the local path either way.

Done when: the user has a link or a path, and knows which of the two feedback routes applies.

### 6. Stop

Report the link or path, the chapter count, and one line on how to send feedback. Do not wait for
comments. Do not apply feedback inside this skill; that is the next request.

## Rules that decide the shape

- **Hunk rule.** A hunk is shown only when the prose makes a claim about it. The reader can open
  the file; the page says where to look and why.
- **Coverage is derived.** The build refuses a changed file with no home and a placed file that
  is not in the diff. `everythingElse` keeps the count honest.
- **Counts come from the build**, never from prose. Prose says why; the strip says how many.
- **Revision-bound.** The banner names the revision and reader progress is scoped to it. If the
  branch moves or the tree changes, rebuild; never patch a line number by hand.
- **Voice.** Sentences of at most 25 words. No verdicts, no emoji, no em dashes. A chapter title
  says what changed, not which folder. An overview claims something the reader can check.
- **Anti-patterns.** A chapter per folder. Every hunk shown for completeness. Line numbers typed
  from memory. Counting files in prose. Grading the change.

## Files

- `scripts/build_tour.py`: validator and renderer, stdlib only, Python 3.10 or newer.
  `--data-out` writes the derived stats as JSON.
- `scripts/test_build_tour.py`: `python3 -m unittest scripts/test_build_tour.py` from this
  directory. Run it after touching the build.
- `templates/tour-shell.html`: the page shell with the CSS, the JavaScript, and the markers the
  build splices into. It holds no prose.
- `references/spec.md`: the `review-tour.json` format and every check the build runs.
- `references/authoring.md`: chapter, overview, hunk, verify, and voice rules.
- `examples/review-tour.example.json`: a complete spec to copy the shape from.
