---
name: walkthrough
description: "Build a self-contained HTML walkthrough of a finished implementation (branch or working-tree diff): PR Lens views, chapters by concept, git-validated lines, verification, feedback notes. Use when the user asks to walk through, explain, share, or tour a diff or implementation result before reviewing it."
---

# Walkthrough

A **pure explainer**: every PR Lens architecture and data-flow view first, then chapters cut by
concept in reading order. No verdicts, findings, or severities. If a review is wanted, use
another skill.

**REQUIRED SUB-SKILL:** Use `pr-lens` to render the architecture and data-flow views embedded in
the shared page. Its graph orients the explanation; the diff and `build_tour.py` remain
authoritative for every claim, file, hunk, and line number.

All prose lives in `review-tour.json`. The agent never edits HTML: `scripts/build_tour.py`
validates the spec against `git diff` and renders the page. A rejected spec is a fact about the
diff, not a formatting problem.

This skill is read-only with respect to the repository. It writes only under the temp directory.

The page opens with a reading budget, because an agent's diff can touch hundreds of files. The
build puts every changed file in one of five tiers. **Flagged**: a rule claimed the file but does
not explain it. **Read** and **skim**: chapters, by risk. **Matched**: the build proved a rule
explains every change. **Agent's word**: the rest, with random samples to spot-check. A file the
reader may skip is either matched by the build or labeled as the agent's word.

## Steps

### 1. Fix the revision

Base: the first of `main` or `master` that exists; if neither does, ask which branch to compare
against. Then `BASE=$(git merge-base <base> HEAD)`.

Head: `worktree` when `git status --porcelain` is non-empty (the default, so uncommitted work is
included), otherwise `git rev-parse HEAD`.

Arguments override the default: a commit range uses its two ends; a PR number means
fetch it without checking it out: take `<baseRefName>` from `gh pr view <n> --json baseRefName`,
run `git fetch origin <baseRefName>`, then `git fetch origin pull/<n>/head` (last, so `FETCH_HEAD`
is the PR); head = `git rev-parse FETCH_HEAD`, base = `git merge-base origin/<baseRefName> <head>`.
Read the PR's files with `git show <head>:<path>`, not from the working tree. Never switch the
user's branch. Local git only in this version. A path filter is
not supported; if the user asks for one, say so and walk the whole diff.

Done when: `BASE` and the head value are written down, and `git diff --name-status $BASE..<head>`
(or `git diff --name-status $BASE` for a working tree) is in front of you.

### 2. Map and read the change

Set `REPO_ROOT=$(git rev-parse --show-toplevel)` and create `$DIR/pr-lens/.pr-lens`, where `DIR`
is `${TMPDIR:-/tmp}/walkthrough/<repo-name>-<branch-slug>`. Follow `pr-lens` for the exact
`BASE` and head fixed in step 1, but write its graph to `$DIR/pr-lens/.pr-lens/graph.json` and
run its validate and render commands from `$DIR/pr-lens`. Keep every PR Lens artifact there so
this skill remains read-only with respect to the repository. Skip canvas publishing and pull
request attachment: the walkthrough embeds the rendered views into its own deliverable.

When the head is `worktree`, fingerprint it immediately after rendering:

```bash
WORKTREE_HASH=$(python3 <skill-dir>/scripts/build_tour.py \
  --repo-root "$REPO_ROOT" --print-worktree-hash "$BASE")
```

Read the validated graph and render manifest for the intended contract, system boundaries,
unchanged neighbours, blast radius, and ordered flows. Then run `git diff --stat` and read the
hunks of every changed file. Reconcile the graph against the diff; never repeat an inference the
code does not support. You cannot cut chapters from a file list or accept the graph on faith.

Done when: PR Lens validation and rendering succeed, every graph view has a manifest asset, and
you can say in one sentence what changed and why without naming a folder.

### 3. Write the spec

Write `review-tour.json` in `${TMPDIR:-/tmp}/walkthrough/<repo-name>-<branch-slug>/`. Format:
`references/spec.md`. Rules: `references/authoring.md`. Shape to copy:
`examples/review-tour.example.json`.

Set `prLens.graph` to `pr-lens/.pr-lens/drawn.graph.json` and `prLens.manifest` to
`pr-lens/.pr-lens/manifest.json`. Both paths are relative to `review-tour.json`. When the head is
`worktree`, also set `prLens.worktreeHash` to `$WORKTREE_HASH`.

- Chapters cut by concept in reading order: contract, then the heart, then consequences, then
  glue. One to six of them. Use the PR Lens contract, boundaries, blast radius, and flows to
  choose those concepts, after reconciling each against the diff.
- The hunk rule: a hunk appears only when the prose claims something about it. Every other file
  in the chapter is a card.
- Every changed file lands in a chapter, a group, or `everythingElse`. Use a substitution group
  for a mechanical change across many files, and keep `everythingElse` to a few leftovers. The
  build finds moves, line-ending changes, deletions, and binary files itself.
- `focus` names chapters by their `#ch-<id>` anchor.
- `verify.ran` lists the commands you actually ran this session with their real exit codes. A
  command you did not run is written out as not run, with `exit: null`.
- `verify.manual` gives steps the reader can run, each with its expected result.

`execute` fills the optional `sheet` block for interactive runs, so one page carries the run facts and the tour. See `references/spec.md`.

Done when: the spec is valid JSON and every changed file from step 1 appears in it.

### 4. Build

```bash
python3 <skill-dir>/scripts/build_tour.py \
  --spec  "$DIR/review-tour.json" \
  --repo-root . \
  --out "$DIR/tour.html" \
  --fragment "$DIR/tour.fragment.html"
```

A failure names the defect: a range with no changed line, a file placed nowhere, a group glob
that matches nothing, a full `everythingElse`, a line shown twice, a missing PR Lens view, stale
asset bytes, or unsafe SVG content. A file that breaks its group's rule does not fail the build:
it prints a warning and goes to the top of the page. Read the warning before you deliver. Fix
the source artifact or spec, never the page, and build again.

Once the build prints `ok`, open the page and look before delivering it: render a screenshot of
`tour.html` with a headless browser if one is available; at minimum, Read `tour.html` and confirm
every PR Lens view, the focus list, every chapter title, and the verify table each appear once, in
order.

Done when: the build prints
`build_tour: ok files=... placed=... else=... hunks=... chapters=... pr-lens=... ... tiers ...`,
those numbers match what you expected, and you have looked at the page as described above.

### 5. Deliver

**Always:** `open "$DIR/tour.html"` on macOS, `xdg-open` on Linux. Print the local path. Feedback
comes back through the page: Notes, then the floating "Send feedback" button, then paste into the chat.

**On top of that, only when the user explicitly asks to publish or share the tour online:** on
Claude Code, publish `tour.fragment.html` as an artifact (title = the spec title, `icon` = one
generic word such as `compass`), and give the user the link. Also pass `capabilities: {db: {}}` so Send feedback can save notes for the agent. Feedback comes back as comment threads on the artifact;
read them with the ArtifactComments tool when the user says they have commented. If there is
no Artifact tool, say the tour was not published and point back to the local path already given.

Done when: the local file was opened and its path printed, and, if a publish was requested,
either the user has a link or has been told it was not published and pointed back to the path.

### 6. Stop

Report the local path, and the link if a requested publish succeeded (or a note that it did not),
the chapter count, and one line on how to send feedback. Do not wait for comments. Do not apply
feedback inside this skill; that is the next request.

## Revision-bound

The banner names the revision and reader progress is scoped to it. If the branch moves or the
tree changes, rebuild; never patch a line number by hand.

## Files

- `scripts/build_tour.py`: validator and renderer, stdlib only, Python 3.10 or newer.
  `--data-out` writes the derived stats as JSON. `--seed N` fixes the spot-check samples for tests; by default the change sets them.
- `scripts/digest.py`: sorts changed files into tiers, proves substitution groups, and draws
  samples. `build_tour.py` imports it.
- `scripts/test_build_tour.py`: `python3 -m unittest scripts/test_build_tour.py` from this
  directory. Run it after touching the build.
- `templates/tour-shell.html`: the page shell with the CSS, the JavaScript, and the markers the
  build splices into. It holds no prose.
- `lib/`: symlink to the repo's shared `_lib/` page machinery (theme, layout, `pagelib.py`).
  Never edit through this symlink; edit `_lib/` itself.
