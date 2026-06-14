---
name: finish
description: Cleanly wrap up a finished development branch — verify tests pass, drain any pending background reviews, detect repo/worktree state, present a merge / open-PR / keep / discard choice, then execute it and clean up. Use when implementation is complete, tests pass, and you need to integrate or retire the work.
license: MIT
---

# Finish (workflow)

## Overview

Wrap up completed development by verifying the work, draining outstanding reviews, offering structured options, and executing the chosen path.

**Core flow:** Verify tests → Drain the council → Detect environment → Determine base → Present options → Execute → Clean up.

Follow the steps in order. Each gate must pass before moving on.

## Step 1 — Verify Tests (gate)

Run the project's test suite before offering any options:

```bash
# Use whatever the project uses, e.g.:
npm test        # or
cargo test      # or
pytest          # or
go test ./...
```

**If tests fail:** stop here.

```
Tests failing (<N> failures). These must pass before finishing:

<show failures>

Not proceeding to merge/PR until tests pass.
```

Apply the **`verification-before-completion`** skill here — read the real output and exit code before calling the suite green. If a failure is an intermittent/flaky test rather than a real regression, use **`de-flaking-tests`** to make it deterministic; never paper over it to get past this gate.

Do not continue until tests pass.

## Step 1.5 — Drain the Council (hard block)

Before any integration (merge / PR / done), **resolve every pending background review.** This is the one place in the pipeline where blocking is correct: nothing ships past `finish` while a cross-model judge still has the change in flight.

The background reviews are the `codex exec` verdict files the deferred commit-hook writes under `.claude/council-reviews/`. Drain them:

```bash
# Derive from the repo root, not $CLAUDE_PROJECT_DIR (which is unset outside Claude Code —
# the commit-hook must write to this same git-root path so the drain finds them in any host):
REVIEW_DIR="$(git rev-parse --show-toplevel)/.claude/council-reviews"
if [ -d "$REVIEW_DIR" ] && [ -n "$(ls -A "$REVIEW_DIR" 2>/dev/null)" ]; then
  echo "Pending council reviews — resolve before finishing:"
  ls -1 "$REVIEW_DIR"
fi
```

For each pending verdict: read it, adjudicate it (disbelieve-it-back — verify each finding against the code; see `vet`), apply or reject, then clear the resolved file. **Do not proceed to integration while any review remains unresolved.**

Do not continue to Step 2 until the council is drained (or there is nothing to drain).

## Step 2 — Detect Environment (gate)

Determine the workspace state; it decides which menu to show and how cleanup works.

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
WT=$(git rev-parse --show-toplevel)   # capture the worktree path before any cd — Step 6 passes it to git-worktree teardown
```

| State | Menu | Cleanup |
|---|---|---|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 4 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 4 options | Provenance-based (Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 3 options (no local merge) | None (externally managed) |

Detect detached HEAD with:

```bash
git symbolic-ref -q HEAD >/dev/null || echo "detached HEAD"
```

## Step 3 — Determine Base Branch

The menu and merge command need a base **branch name**, not a commit SHA. Pick the first base branch that exists:

```bash
BASE=""
for b in main master; do
  git rev-parse --verify --quiet "$b" >/dev/null && BASE="$b" && break
done
echo "${BASE:-<unknown>}"
```

If neither exists (`BASE` empty), **ask** — don't assume `main`: "I can't find a `main` or `master` branch — what's the base branch for this work?"

## Step 4 — Present Options (gate)

**Normal repo or named-branch worktree — present exactly these 4 options:**

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and open a Pull Request
3. Keep the branch as-is (handle it later)
4. Discard this work

Which option?
```

**Detached HEAD — merge-locally (Option 1) isn't available; present these, keeping the same numbers as Step 5 so execution matches:**

```
Implementation complete. You're on a detached HEAD (externally managed workspace).

2. Push as a new branch and open a Pull Request
3. Keep as-is (handle it later)
4. Discard this work

Which option?
```

(The numbers intentionally skip 1 — they index Step 5's options directly, so "4" always means Discard, never Keep.)

Keep the menu concise — no extra explanation. Wait for the choice.

## Step 5 — Execute the Choice

### Option 1 — Merge Locally

```bash
# Move to the main repo root for CWD safety (works in normal repos and worktrees):
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"

# Merge — confirm success before removing anything:
git checkout <base-branch>
git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1 && git pull   # only if base has an upstream
git merge <feature-branch>

# Re-run tests on the merged result:
<test command>
```

Only after the merge and tests succeed: clean up the worktree (Step 6), then delete the branch:

```bash
git -C "$MAIN_ROOT" branch -d <feature-branch>
```

### Option 2 — Push and Open a PR

```bash
# Detached HEAD has no branch to push — create one first:
git symbolic-ref -q HEAD >/dev/null || git switch -c <new-branch>   # detached HEAD only; pick <new-branch>

git push -u origin <branch>   # the branch you are now on: the existing feature branch, or <new-branch> created above if you were detached

gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

Do not clean up the worktree — it is needed to iterate on PR feedback.

### Option 3 — Keep As-Is

Report: "Keeping branch `<name>`. Worktree preserved at `<path>`." Do not clean up.

### Option 4 — Discard (typed confirmation required)

What "discard" deletes depends on the environment detected in Step 2 — show the accurate list:
- **Normal repo (no worktree):** branch `<name>` and its commits. (Step 6 has no worktree to remove here.)
- **Named-branch worktree (ours):** branch `<name>`, its commits, and the worktree.
- **Detached HEAD (externally-managed workspace):** the commits only (they become unreachable). There's no branch, and **the workspace is the host's, not ours — it is left in place** (Step 2 classifies it as externally managed). Don't promise to delete a workspace you didn't create.

```
This will permanently delete:
- <branch + its commits + worktree>   (normal repo / our worktree)
- <the commits, now unreachable>      (detached HEAD — workspace left in place)

Type 'discard' to confirm.
```

Wait for the exact word `discard`. If confirmed, order matters — **git refuses to delete a branch any worktree still has checked out, so remove the worktree before the branch.** By environment (Step 2):

- **Named-branch worktree (ours):** run Step 6 teardown **first** (removes the worktree, freeing the branch), then delete the branch from the main root:
  ```bash
  # (Step 6 git-worktree teardown removes $WT first)
  git -C "$MAIN_ROOT" branch -D <feature-branch>
  ```
- **Normal repo (no worktree):** the branch is checked out here — switch off it, then delete (no Step 6 worktree to remove):
  ```bash
  git switch <base-branch>
  git branch -D <feature-branch>
  ```
- **Detached HEAD (externally-managed):** no branch to delete and the workspace isn't ours — just abandon the commits (unreachable; git gc reclaims them). Step 6 is a no-op here.

## Step 6 — Clean Up the Workspace

Runs only for Options 1 and 4. Options 2 and 3 always preserve the worktree.

**Delegate worktree teardown to the `git-worktree` skill (teardown), passing the `WT` path captured in Step 2.** Pass `WT` explicitly — by now you may have `cd`'d to the main root (Options 1/4 do, for merge safety), and teardown must operate on the captured worktree path, not the current directory. The skill owns the mechanism: provenance check (ours = under `.worktrees/`/`worktrees/` with the `council-worktree` marker in the worktree's git-metadata dir), then remove + prune from the main root. A normal repo (`GIT_DIR == GIT_COMMON`) has no worktree to remove; an externally-managed workspace is left in place. Don't re-implement that logic here — invoke the skill so there's one mechanism shared with autonomous `execute` (which created the worktree via the same skill's setup).

Use `--force` removal only on the Option 4 discard path.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Delete Branch |
|---|---|---|---|---|
| 1. Merge locally | yes | – | – | yes |
| 2. Open PR | – | yes | yes | – |
| 3. Keep as-is | – | – | yes | – |
| 4. Discard | – | – | – | yes (force) |

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without re-verifying tests on the result
- Delete work without typed confirmation
- Force-push unless explicitly asked
- Remove a worktree before confirming merge success
- Remove a worktree you did not create (provenance check)
- Run `git worktree remove` from inside that worktree

**Always:**
- Verify tests before offering options
- Detect the environment before choosing a menu
- Present exactly 4 options (or 3 for detached HEAD)
- Get a typed `discard` confirmation for Option 4
- Clean up the worktree for Options 1 and 4 only
- `cd` to the main repo root before removing a worktree
- Run `git worktree prune` after removal
