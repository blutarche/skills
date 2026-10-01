---
name: finish
disable-model-invocation: true
description: "Wrap up a finished branch: verify, cross-model review loop, merge / PR / keep / discard, cleanup."
license: MIT
---

# Finish (workflow)

Follow the steps in order. Each gate must pass before moving on.

## Step 1 — Verify Tests (gate)

Run the project's test suite before offering any options. Read the real output and exit code before calling it green.

**If tests fail:** stop and show the failures. Don't proceed to merge/PR until they pass. If a failure is an intermittent/flaky test rather than a real regression, use **`diagnose`**'s flaky-tests section to make it deterministic; never paper over it to get past this gate.

## Step 2 — Detect Environment (gate)

Determine the workspace state; it decides which menu to show and how cleanup works.

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
WT=$(git rev-parse --show-toplevel)   # capture the worktree path before any cd — Step 7 passes it to git-worktree teardown
```

| State | Menu | Cleanup |
|---|---|---|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 4 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 4 options | Provenance-based (Step 7) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 3 options (no local merge) | None (externally managed) |

Detect detached HEAD with:

```bash
git symbolic-ref -q HEAD >/dev/null || echo "detached HEAD"
```

## Step 3 — Determine Base Branch

The menu, the merge command, and the review gate's diff range all need a base **branch name**, not a commit SHA. Pick the first base branch that exists:

```bash
BASE=""
for b in main master; do
  git rev-parse --verify --quiet "$b" >/dev/null && BASE="$b" && break
done
echo "${BASE:-<unknown>}"
```

If neither exists (`BASE` empty), **ask** — don't assume `main`: "I can't find a `main` or `master` branch — what's the base branch for this work?"

## Step 4 — Present Options (gate)

Ask via the host's question tool when available (one question); otherwise present short prose options. Keep it concise — no extra explanation — and wait for the choice.

**Normal repo or named-branch worktree — present exactly these 4 options** ("Implementation complete. What would you like to do?"):

1. Merge back to `<base-branch>` locally
2. Push and open a Pull Request
3. Keep the branch as-is (handle it later)
4. Discard this work

**Detached HEAD — merge-locally (Option 1) isn't available; present these, keeping the same numbers as Step 6 so execution matches** ("Implementation complete. You're on a detached HEAD (externally managed workspace)."):

2. Push as a new branch and open a Pull Request
3. Keep as-is (handle it later)
4. Discard this work

(The numbers intentionally skip 1 — they index Step 6's options directly, so "4" always means Discard, never Keep.)

## Step 5 — Review Gate (Options 1 & 2 only)

**Runs only when the chosen option integrates the work — Merge locally (1) or Push/PR (2).** Keep (3) and Discard (4) skip straight to Step 6: nothing is shipping, so there is nothing to review clean.

Before the branch merges or leaves the machine, the **whole branch diff** must pass a clean cross-model review.

**Why the whole diff, before the push — not commit-by-commit after.** A half-reviewed branch pushed in pieces lets a server-side reviewer (e.g. a GitHub-configured Codex reviewer) drip comments commit-by-commit, forcing a fix → push → new-comments ping-pong. One thorough local review of the *entire* diff, with everything fixed before it ever leaves the machine, collapses that loop — the server-side reviewer meets an already-clean change. The same applies to a local merge: review the whole change once, not each commit.

### 5a — Commit any pending work

The review diff (`<BASE>...HEAD`) and the integration both operate on **commits** — uncommitted changes are invisible to the review and would be dropped by merge or left behind by push. So before reviewing, the working tree must be clean:

```bash
git status --porcelain   # if non-empty, there is uncommitted work to commit first
```

If anything is uncommitted, hand off to the **`git-commit`** skill — it produces clean, atomic, bisect-safe commits in the repo's convention. (It does **not** push; the push in Option 2 stays separate.) Do not stage-and-commit ad hoc here; let `git-commit` own the message and the splitting.

### 5b — Comprehensive review loop (until two consecutive clean passes)

**Pick the reviewer, in order of preference:**

- **`/codex:review`** if it is available in this session — your configured Codex reviewer, the primary. It only *reports*; you own the adjudication and fix loop below.
- **otherwise `vet`** — `scrutinize` + `council` over `--base <BASE>`. `vet` bundles the fix loop, and `council` carries the degrade ladder (fresh-subagent `scrutinize` → inline) when Codex itself is unreachable, disclosing the rung. This is why the skill names no hard dependency on the plugin: `vet`/`council` is the portable equivalent, so machines without `/codex:review` still get a real cross-model review.

**Loop over the whole-branch diff (`<BASE>...HEAD`):**

1. Run the chosen reviewer on the full diff.
2. **Adjudicate disbelieve-it-back** — every finding is a claim to verify against the actual code, not an order. Reject the wrong ones out loud (see `council` / `vet`).
3. **If any finding is accepted:** fix it — hand off to `receiving-code-review`, then `/simplify` or `slop-cleanup` as the finding warrants, **re-verify tests** (Step 1's command), and commit the fix with **`git-commit`**. Reset the clean streak to 0 and go to 1.
   **If none accepted:** clean streak += 1.
4. **Stop when the clean streak reaches 2** — two *consecutive* passes that surface zero accepted findings. A single clean pass from a non-deterministic reviewer can be a fluke; require it twice in a row before calling the branch clean.

**Bounded — never spin.** Cap at 5 fix rounds. If the loop hasn't reached two consecutive clean passes by then, **stop and surface the remaining findings to the user** — do not push or merge a branch that won't converge.

Only once the branch is clean (two consecutive clean passes) does it proceed to Step 6 for the chosen integration.

## Step 6 — Execute the Choice

### Option 1 — Merge Locally

(Step 5 review gate has already passed — the branch is clean.)

Don't switch any existing checkout's branch to merge. Merge in the worktree where the base branch is already checked out (the main root counts); if it is checked out nowhere, merge in a temporary worktree of your own.

```bash
BASE=<base-branch>   # from Step 3 — set here because shell variables don't survive across tool calls

# Move to the main repo root for CWD safety (works in normal repos and worktrees):
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"

# Find the worktree that has the base branch checked out (empty if none):
BASE_WT=$(git worktree list --porcelain | awk -v b="refs/heads/$BASE" '$1=="worktree"{p=substr($0,10)} $1=="branch"&&$2==b{print p; exit}')

# Base checked out nowhere: check it out in a temporary worktree (a fresh tree has no gitignored deps — install them if the tests need them)
TMP_WT=""
if [ -z "$BASE_WT" ]; then
  TMP_WT="$(mktemp -d "${TMPDIR:-/tmp}/finish-base.XXXXXX")"
  git worktree add "$TMP_WT" "$BASE"
  BASE_WT="$TMP_WT"
fi

# Merge — confirm success before removing anything:
git -C "$BASE_WT" rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1 && git -C "$BASE_WT" pull   # only if base has an upstream
git -C "$BASE_WT" merge <feature-branch>

# Re-run tests on the merged result, in "$BASE_WT":
( cd "$BASE_WT" && <test command> )

# Only if the merge and tests succeeded; if they failed, leave the temporary worktree for inspection and surface it:
[ -z "$TMP_WT" ] || git worktree remove "$TMP_WT"
```

Only after the merge and tests succeed: clean up the feature worktree (Step 7), then delete the branch:

```bash
git -C "$MAIN_ROOT" branch -d <feature-branch>
```

In a normal repo (no worktree) the feature branch is still checked out in `$MAIN_ROOT`, so git refuses the delete. Don't switch off it; tell the user the branch can be deleted once they switch.

### Option 2 — Push and Open a PR

(Step 5 review gate has already passed.)

```bash
# Detached HEAD has no branch to push — push HEAD to a new remote branch; the checkout is left untouched:
git symbolic-ref -q HEAD >/dev/null || git push -u origin HEAD:refs/heads/<new-branch>   # detached HEAD only; pick <new-branch>

git symbolic-ref -q HEAD >/dev/null && git push -u origin <branch>   # on a named branch: push the feature branch (below, <branch> means <new-branch> if you were detached)

gh pr create --head <branch> --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

Don't force-push unless explicitly asked. Do not clean up the worktree — it is needed to iterate on PR feedback.

### Option 3 — Keep As-Is

Report: "Keeping branch `<name>`. Worktree preserved at `<path>`." Do not clean up. (No review gate — nothing is shipping.)

### Option 4 — Discard (typed confirmation required)

What "discard" deletes depends on the environment detected in Step 2 — show the accurate list:
- **Normal repo (no worktree):** branch `<name>` and its commits. (Step 7 has no worktree to remove here.)
- **Named-branch worktree (ours):** branch `<name>`, its commits, and the worktree.
- **Detached HEAD (externally-managed workspace):** the commits only (they become unreachable). There's no branch, and **the workspace is the host's, not ours — it is left in place** (Step 2 classifies it as externally managed). Don't promise to delete a workspace you didn't create.

```
This will permanently delete:
- <branch + its commits + worktree>   (normal repo / our worktree)
- <the commits, now unreachable>      (detached HEAD — workspace left in place)

Type 'discard' to confirm.
```

Wait for the exact word `discard`. If confirmed, order matters — **git refuses to delete a branch any worktree still has checked out, so remove the worktree before the branch.** By environment (Step 2):

- **Named-branch worktree (ours):** run Step 7 teardown **first** (removes the worktree, freeing the branch), then delete the branch from the main root:
  ```bash
  # (Step 7 git-worktree teardown removes $WT first)
  git -C "$MAIN_ROOT" branch -D <feature-branch>
  ```
- **Normal repo (no worktree):** the branch is checked out here, and git refuses to delete a checked-out branch. Don't switch the checkout's branch to get around that: tell the user to switch off it and run `git branch -D <feature-branch>` (no Step 7 worktree to remove).
- **Detached HEAD (externally-managed):** no branch to delete and the workspace isn't ours — just abandon the commits (unreachable; git gc reclaims them). Step 7 is a no-op here.

## Step 7 — Clean Up the Workspace

Runs only for Options 1 and 4. Options 2 and 3 always preserve the worktree.

**Delegate worktree teardown to the `git-worktree` skill (teardown), passing the `WT` path captured in Step 2.** Pass `WT` explicitly — by now you may have `cd`'d to the main root (Options 1/4 do), and teardown must operate on the captured worktree path, not the current directory. A normal repo (`GIT_DIR == GIT_COMMON`) has no worktree to remove; an externally-managed workspace is left in place. Don't re-implement the provenance check or removal here.

Use `--force` removal only on the Option 4 discard path.

## Quick Reference

| Option | Review gate first | Merge | Push | Keep Worktree | Delete Branch |
|---|---|---|---|---|---|
| 1. Merge locally | yes | yes | – | – | yes |
| 2. Open PR | yes | – | yes | yes | – |
| 3. Keep as-is | – | – | – | yes | – |
| 4. Discard | – | – | – | – | yes (force) |
