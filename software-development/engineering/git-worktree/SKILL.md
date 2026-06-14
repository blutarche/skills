---
name: git-worktree
description: "Create/enter an isolated feature worktree and bootstrap-or-surface its environment (setup), and remove/prune it (teardown). Use when starting isolated agentic work (e.g. autonomous execute) or wrapping it up (finish)."
---

# Git Worktree (atomic skill)

Two operations on a git worktree: **setup** (create + enter + make it runnable) and **teardown** (remove + prune). This is one mechanism so callers don't each reinvent it — `execute` (autonomous mode) calls setup; `finish` calls teardown.

A worktree is an isolated checkout of the same repo on its own branch, so an agent can work without disturbing the main tree. The trap is that a fresh worktree is **code-only**: it has no `node_modules`, no `.env`, no build cache — running tests in it before it's set up gives false failures. So setup is not just `git worktree add`; it must make the tree actually runnable, or stop and say it can't.

## Setup

1. **Create + enter the worktree.**

   ```bash
   MAIN=$(git rev-parse --show-toplevel)           # capture the main tree NOW — needed for env copy after we cd
   WT="$MAIN/.worktrees/<branch>"                  # under the repo's .worktrees/ convention
   git worktree add "$WT" -b "<branch>" "<base>"  # name <base> (e.g. origin/main, HEAD) — don't omit it
   touch "$(git -C "$WT" rev-parse --git-dir)/council-worktree"  # provenance marker in git metadata, NOT the working tree
   cd "$WT"                                         # actually enter it; "create + enter" means both
   ```

   **Name the base ref** — omitting it silently branches from whatever HEAD happens to be. **Put the marker in the worktree's git-metadata dir** (`.git/worktrees/<name>/council-worktree`), never as a file in the working tree — an untracked marker in the tree would make `git worktree remove` (which refuses a dirty tree without `--force`) fail on the marker itself. The `.worktrees/` path plus this metadata marker are how teardown recognises the worktree as ours.

2. **Bootstrap or surface the environment.** A fresh tree has none of the untracked, gitignored build state the project needs.

   Detect the project's setup and run it — for example:
   - JS/TS: the lockfile-appropriate install (`npm ci` / `pnpm install` / `yarn`).
   - Python: create/sync the venv (`uv sync`, `poetry install`, `pip install -e .`).
   - copy any gitignored env the project relies on (`.env`, local config) from the main tree `$MAIN` (captured in step 1) if present.

   **If the setup can't be determined** — no recognisable manifest, or an env file you can't safely reproduce — **STOP and surface it**: `set up the env at <path> before autonomous runs` (name what's missing). **Never run tests in a half-built tree** and call the result a failure; an unbootstrapped tree is a setup gap, not a code defect.

## Teardown

**The caller passes the target worktree path (`WT`)** — captured from the caller's own state *before* it changes directory. Do **not** rediscover the target from the current directory here: a caller that has already `cd`'d to the main root (e.g. `finish`, for merge safety) would otherwise look at the wrong tree and conclude there's nothing to remove, leaking the worktree.

1. **Provenance check — only remove a worktree this workflow created.** Given `WT`:

   - `WT` isn't in `git worktree list` → **nothing to remove**. Done.
   - `WT` is the main checkout itself (its `git -C "$WT" rev-parse --git-dir` equals `git -C "$WT" rev-parse --git-common-dir`, i.e. not a linked worktree) → **nothing to remove**. Done.
   - `WT` is under `.worktrees/`/`worktrees/` **and** its git-metadata marker exists (`[ -f "$(git -C "$WT" rev-parse --git-dir)/council-worktree" ]`) → ours; remove it. (Require the marker — path convention alone could match a worktree someone else created under the same dir.)
   - Otherwise → externally managed; **leave it in place**.

2. **Remove + prune** — from the main root, never from inside the worktree:

   ```bash
   MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
   cd "$MAIN_ROOT"                     # never run remove from inside the worktree
   git worktree remove "$WT"           # add --force ONLY on an explicit discard
   git worktree prune                  # clear any stale registrations
   ```

## Notes

- One thing well: this skill owns the worktree lifecycle mechanism. The *decisions* (which branch, when to tear down, merge vs discard) live in the calling workflow.
- `--force` removal only on an explicit discard path — never to paper over uncommitted work you didn't expect.
- Run `git worktree prune` after every removal so stale registrations don't accumulate.
