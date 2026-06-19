---
name: finish
description: Cleanly wrap up a finished development branch — verify tests pass, detect repo/worktree state, present a merge / open-PR / keep / discard choice, then before any integration drive the whole branch through a comprehensive cross-model review until it is clean, execute the chosen path, and clean up. Use when implementation is complete, tests pass, and you need to integrate or retire the work.
license: MIT
---

# Finish (workflow)

## Overview

Wrap up completed development by verifying the work, offering structured options, reviewing the whole branch clean before it ships, and executing the chosen path.

**Core flow:** Verify tests → Detect environment → Determine base → Present options → **(Options 1 & 2) Review gate: commit pending work → comprehensive cross-model review until clean** → Execute → Clean up.

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

**Normal repo or named-branch worktree — present exactly these 4 options:**

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and open a Pull Request
3. Keep the branch as-is (handle it later)
4. Discard this work

Which option?
```

**Detached HEAD — merge-locally (Option 1) isn't available; present these, keeping the same numbers as Step 6 so execution matches:**

```
Implementation complete. You're on a detached HEAD (externally managed workspace).

2. Push as a new branch and open a Pull Request
3. Keep as-is (handle it later)
4. Discard this work

Which option?
```

(The numbers intentionally skip 1 — they index Step 6's options directly, so "4" always means Discard, never Keep.)

Keep the menu concise — no extra explanation. Wait for the choice.

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

### 5b — Drain any pending background reviews (housekeeping)

The deferred commit-hook may have dropped `codex exec` verdict files under the repo's `.claude/council-reviews/`. Clear them so stale per-commit verdicts don't linger — the comprehensive pass in 5c supersedes them, but don't leave them on disk:

```bash
# Derive from the repo root, not $CLAUDE_PROJECT_DIR (unset outside Claude Code):
REVIEW_DIR="$(git rev-parse --show-toplevel)/.claude/council-reviews"
if [ -d "$REVIEW_DIR" ] && [ -n "$(ls -A "$REVIEW_DIR" 2>/dev/null)" ]; then
  echo "Pending per-commit reviews (fold into the comprehensive pass, then clear):"
  ls -1 "$REVIEW_DIR"
fi
```

Read each, fold any unresolved finding into the 5c loop's first round, then delete the resolved file.

### 5c — Comprehensive review loop (until two consecutive clean passes)

**Pick the reviewer, in order of preference:**

- **`/codex:review`** if it is available in this session — your configured Codex reviewer, the primary. It only *reports*; you own the adjudication and fix loop below.
- **otherwise `vet`** — `scrutinize` + `council` over `--base <BASE>`. `vet` bundles the fix loop, and `council` carries the degrade ladder (fresh-subagent `scrutinize` → inline) when Codex itself is unreachable, disclosing the rung. This is why the skill names no hard dependency on the plugin: `vet`/`council` is the portable equivalent, so machines without `/codex:review` still get a real cross-model review.

**Loop over the whole-branch diff (`<BASE>...HEAD`):**

1. Run the chosen reviewer on the full diff.
2. **Adjudicate disbelieve-it-back** — every finding is a claim to verify against the actual code, not an order. Reject the wrong ones out loud (see `council` / `vet`).
3. **If any finding is accepted:** fix it — hand off to `receiving-code-review`, then `/simplify` or `slop-cleanup` as the finding warrants, **re-verify tests** (Step 1's command), and commit the fix with **`git-commit`**. Reset the clean streak to 0 and go to 1.
   **If none accepted:** clean streak += 1.
4. **Stop when the clean streak reaches 2** — two *consecutive* passes that surface zero accepted findings. A single clean pass from a non-deterministic reviewer can be a fluke; require it twice in a row before calling the branch clean.

**Bounded — never spin.** Cap at 5 fix rounds. If the loop hasn't reached two consecutive clean passes by then, **stop and surface the remaining findings to the user** — do not push or merge a branch that won't converge, and do not loop forever. (Per the bounded-retry rule: the escalation matters more than the loop.)

Only once the branch is clean (two consecutive clean passes) does it proceed to Step 6 for the chosen integration.

## Step 6 — Execute the Choice

### Option 1 — Merge Locally

(Step 5 review gate has already passed — the branch is clean.)

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

Only after the merge and tests succeed: clean up the worktree (Step 7), then delete the branch:

```bash
git -C "$MAIN_ROOT" branch -d <feature-branch>
```

### Option 2 — Push and Open a PR

(Step 5 review gate has already passed — push a branch that is already clean, so the server-side reviewer has nothing to drip.)

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
- **Normal repo (no worktree):** the branch is checked out here — switch off it, then delete (no Step 7 worktree to remove):
  ```bash
  git switch <base-branch>
  git branch -D <feature-branch>
  ```
- **Detached HEAD (externally-managed):** no branch to delete and the workspace isn't ours — just abandon the commits (unreachable; git gc reclaims them). Step 7 is a no-op here.

## Step 7 — Clean Up the Workspace

Runs only for Options 1 and 4. Options 2 and 3 always preserve the worktree.

**Delegate worktree teardown to the `git-worktree` skill (teardown), passing the `WT` path captured in Step 2.** Pass `WT` explicitly — by now you may have `cd`'d to the main root (Options 1/4 do, for merge safety), and teardown must operate on the captured worktree path, not the current directory. The skill owns the mechanism: provenance check (ours = under `.worktrees/`/`worktrees/` with the `council-worktree` marker in the worktree's git-metadata dir), then remove + prune from the main root. A normal repo (`GIT_DIR == GIT_COMMON`) has no worktree to remove; an externally-managed workspace is left in place. Don't re-implement that logic here — invoke the skill so there's one mechanism shared with autonomous `execute` (which created the worktree via the same skill's setup).

Use `--force` removal only on the Option 4 discard path.

## Quick Reference

| Option | Review gate first | Merge | Push | Keep Worktree | Delete Branch |
|---|---|---|---|---|---|
| 1. Merge locally | yes | yes | – | – | yes |
| 2. Open PR | yes | – | yes | yes | – |
| 3. Keep as-is | – | – | – | yes | – |
| 4. Discard | – | – | – | – | yes (force) |

## Red Flags

**Never:**
- Proceed with failing tests
- Merge or push before the review gate reaches two consecutive clean passes (Options 1 & 2)
- Loop the review gate unbounded — cap at 5 fix rounds and escalate
- Push commit-by-commit and let a server-side reviewer drip comments — review the whole diff clean first
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
- Commit pending work with `git-commit` before reviewing (Options 1 & 2) — the review and the integration both operate on commits
- Run the comprehensive review gate before any integration (Options 1 & 2), on the whole branch diff, not per commit
- Require two consecutive clean review passes before integrating
- Get a typed `discard` confirmation for Option 4
- Clean up the worktree for Options 1 and 4 only
- `cd` to the main repo root before removing a worktree
- Run `git worktree prune` after removal
```