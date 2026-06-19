# Executor: `cursor-agent`

Tool-specific invocation for the `delegate-coding` skill. The method (two-tier verify, merge-as-commit-point, bounded retry, escalation) lives in `../SKILL.md`; this file only covers *how to drive cursor-agent*.

`cursor-agent` is Cursor's headless CLI. In print mode it has full write + shell access and can run in its own isolated git worktree, which is exactly the executor shape this skill wants.

## Preflight

```bash
command -v cursor-agent >/dev/null || echo "cursor-agent not installed"   # → fall back to execute
cursor-agent status                                                       # must report logged in
```

If `cursor-agent status` says **"Not logged in"**, stop and tell the user to run `cursor-agent login` — a one-time, browser-based auth you can't do for them. Don't proceed; there's nothing to delegate to.

## Model — inherit a Composer default (set it once)

Don't pass `--model` per call — the id version-bumps, so pinning it in the skill rots. Instead set the CLI's default to the cheap Composer model **once**; delegations then inherit it and the skill stays model-agnostic.

**Set the right knob.** The default that governs headless `cursor-agent -p` lives in **`~/.cursor/cli-config.json`** (`model` + `selectedModel`), *not* the `(default)` shown by `cursor-agent --list-models` — that's a server label the local config overrides. (Verified 2026-06-19: with cli-config set to `gpt-5.5`, a headless run with no `--model` used `gpt-5.5-high` and spent premium quota, despite `--list-models` marking Composer as default.) Set it either way:

- **Interactive (recommended):** run `cursor-agent`, open the model picker, choose **Composer** → it persists to cli-config.json.
- **Direct:** set `model.modelId` and `selectedModel.modelId` in `~/.cursor/cli-config.json` to the Composer id (e.g. `composer-2.5-fast`).

Confirm: `cursor-agent` runs should record Composer (`strings ~/.cursor/chats/*/<session-id>/store.db | grep modelName`). Then omit `--model` in delegations; pass it only as a deliberate premium escape hatch.

## Stage 3 — delegate (first pass)

```bash
cursor-agent -p "<delegation prompt>" \
  --output-format json \
  --force --trust \
  --worktree <task-slug>
```

- `-p` — headless print mode (full write + shell access).
- `--force` (alias `--yolo`) — auto-approve commands so it runs unattended.
- `--trust` — required for headless workspace trust (only works with `-p`).
- `--worktree <task-slug>` — isolated worktree at `~/.cursor/worktrees/<repo>/<task-slug>`; cursor manages it.
- `--output-format json` — so you can capture the result and the session id (for `--resume`).

Other flags that may help: `--workspace <path>` (point at an explicit dir), `--skip-worktree-setup` (skip `.cursor/worktrees.json` setup scripts), `--approve-mcps`, `--sandbox enabled|disabled`. `create-chat` returns a fresh chat id if you'd rather create the session up front.

**Parsing the output (verified).** With `--output-format json`, stdout is *not* pure JSON: it prints a human line first, then the JSON object as the **last line**. Parse the last line:

```bash
WORKTREE=$(grep -m1 '^Using worktree:' stdout.txt | sed 's/^Using worktree: //')   # the worktree path
tail -1 stdout.txt | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["session_id"], d["is_error"])'
```

Verified JSON fields: `result` (the agent's text), `session_id` (use this for `--resume` — *not* `chatId`), `is_error` (bool — your real success signal, not the prose), `usage`, `duration_ms`. The worktree path comes on the leading `Using worktree: …` line, matching `~/.cursor/worktrees/<repo>/<task-slug>`.

## Stage 5 — bounded retry (resume the same session)

**Run resume with the worktree as cwd (verified, load-bearing).** `--resume` does **not** reattach to the session's worktree — it operates in whatever directory you launch it from. If you resume from your main repo, it edits *and can commit* there (confirmed: a stray resume committed into the wrong repo). Always `cd` into the worktree first:

```bash
( cd ~/.cursor/worktrees/<repo>/<task-slug> \
  && cursor-agent --resume <session_id> -p "<exact failure output + what to fix>" --output-format json --force --trust )
```

## Verified end-to-end (2026-06-19)

A live run confirmed: `--worktree` creates and works in `~/.cursor/worktrees/<repo>/<slug>`; the agent commits in the worktree when told to; `--output-format json` shape (above); `--resume` continues the session **when launched from the worktree**; and `git merge --no-ff <worktree-branch>` brings the work into the main tree cleanly. Two gotchas were found the hard way and are folded into the steps above: last-line JSON parsing, and the resume-cwd rule.

## Verified on a real deps repo (2026-06-20)

Ran on `blutils` (Preact/Vite/TS, pnpm): the delegation prompt told cursor to `pnpm install` if `node_modules` was missing, then `pnpm typecheck` — and **Tier-1 (`tsc --noEmit`) passed inside the cursor worktree** (independently re-run), code was correct first try, committed in the worktree. So the dep-bootstrap path works *when the prompt instructs the install*. A fresh worktree has none of your gitignored deps, so **always include the install step in the Tier-1 instructions** (or rely on `.cursor/worktrees.json` setup scripts if the repo has them); don't assume deps are present.

## Cleanup

Cursor's worktree auto-cleans in some cases; otherwise remove it after merge with `git worktree remove ~/.cursor/worktrees/<repo>/<task-slug>` (or leave it to the `finish` workflow).
