# Executor: Cursor CLI (`agent`)

Tool-specific invocation for the `delegate-coding` skill. The method (two-tier verify, merge-as-commit-point, bounded retry, escalation) lives in `../SKILL.md`; this file only covers *how to drive the Cursor CLI*.

The command is **`agent`** — Cursor's headless CLI ([cursor.com/docs/cli](https://cursor.com/docs/cli)). In print mode it has full write + shell access and can run in its own isolated git worktree, which is exactly the executor shape this skill wants.

> **Name note (this trips people up).** The official command is `agent`. `cursor-agent` is the **legacy alias** — the installer still drops a `cursor-agent` symlink to the same binary, so old invocations keep working, but the docs now use `agent` exclusively. Use `agent`. If a machine has a third-party wrapper shadowing `cursor-agent` on `PATH` (e.g. a "Superset" multiplexer), calling `agent` sidesteps it and hits Cursor's binary directly.

## Install & preflight (fail loud)

Official install (macOS/Linux/WSL): `curl https://cursor.com/install -fsS | bash` ([docs/cli/installation](https://cursor.com/docs/cli/installation)).

```bash
command -v agent >/dev/null || echo "Cursor CLI not installed"   # → fall back to execute
agent status                                                     # must report logged in
```

If `agent status` says **"Not logged in"**, stop and tell the user to run `agent login` — a one-time, browser-based auth you can't do for them. Don't proceed; there's nothing to delegate to.

## Model — inherit a Composer default (set it once)

Don't pass `--model` per call — the id version-bumps, so pinning it in the skill rots. Instead set the CLI's default to the cheap Composer model **once**; delegations then inherit it and the skill stays model-agnostic.

**Set the right knob.** The default that governs headless `agent -p` lives in **`~/.cursor/cli-config.json`** (`model` + `selectedModel`), *not* the `(default)` shown by `agent --list-models` — that's a server label the local config overrides. (Verified 2026-06-19: with cli-config set to `gpt-5.5`, a headless run with no `--model` used `gpt-5.5-high` and spent premium quota, despite `--list-models` marking Composer as default.) Set it either way:

- **Interactive (recommended):** run `agent`, pick the model with the `/model` slash command → choose **Composer** → it persists to cli-config.json.
- **Direct:** set `model.modelId` and `selectedModel.modelId` in `~/.cursor/cli-config.json` to the Composer id (e.g. `composer-2.5`).

Confirm: `agent` runs should record Composer (`strings ~/.cursor/chats/*/<session-id>/store.db | grep modelName`). Then omit `--model` in delegations; pass it only as a deliberate premium escape hatch.

## Stage 3 — delegate (first pass)

```bash
agent -p "<delegation prompt>" \
  --output-format json \
  --force --trust \
  --worktree <task-slug>
```

- `-p` / `--print` — headless print mode (full write + shell access).
- `--force` (alias `--yolo`) — auto-approve commands so it runs unattended.
- `--trust` — required for headless workspace trust (only works with `-p`).
- `--worktree <task-slug>` (`-w`) — isolated worktree at `~/.cursor/worktrees/<repo>/<task-slug>`; cursor manages it. `--worktree-base <branch>` bases it on a ref other than current HEAD.
- `--output-format json` — so you can capture the result and the session id (for `--resume`). `text` (default) and `stream-json` are the other formats.

Other flags that may help: `--workspace <path>` (point at an explicit dir), `--skip-worktree-setup` (skip `.cursor/worktrees.json` setup scripts), `--approve-mcps`, `--sandbox enabled|disabled`.

**Parsing the output (verified).** With `--output-format json`, stdout is *not* pure JSON: it prints a human line first, then the JSON object as the **last line**. Parse the last line:

```bash
WORKTREE=$(grep -m1 '^Using worktree:' stdout.txt | sed 's/^Using worktree: //')   # the worktree path
tail -1 stdout.txt | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["session_id"], d["is_error"])'
```

JSON fields (per [docs/cli/reference/output-format](https://cursor.com/docs/cli/reference/output-format)): `type`, `subtype`, `is_error` (bool — your real success signal, not the prose), `duration_ms`, `duration_api_ms`, `result` (the agent's text), `session_id` (the thread id — use this for `--resume`; there is **no** `chatId` field), `request_id`. The worktree path comes on the leading `Using worktree: …` line, matching `~/.cursor/worktrees/<repo>/<task-slug>`.

## Stage 5 — bounded retry (resume the same session)

Resume by thread id with `--resume <session_id>` (or `--continue` for the most recent session, alias of `--resume=-1`; `agent ls` browses prior chats).

**Run resume with the worktree as cwd (verified, load-bearing).** `--resume` does **not** reattach to the session's worktree — it operates in whatever directory you launch it from. If you resume from your main repo, it edits *and can commit* there (confirmed: a stray resume committed into the wrong repo). Always `cd` into the worktree first:

```bash
( cd ~/.cursor/worktrees/<repo>/<task-slug> \
  && agent --resume <session_id> -p "<exact failure output + what to fix>" --output-format json --force --trust )
```

## Verified end-to-end (2026-06-19; command names refreshed against the official docs 2026-06-22)

A live run confirmed: `--worktree` creates and works in `~/.cursor/worktrees/<repo>/<slug>`; the agent commits in the worktree when told to; `--output-format json` shape (above); `--resume` continues the session **when launched from the worktree**; and `git merge --no-ff <worktree-branch>` brings the work into the main tree cleanly. Two gotchas were found the hard way and are folded into the steps above: last-line JSON parsing, and the resume-cwd rule. (Those runs used the `cursor-agent` alias; the binary is identical, so the behavior carries over verbatim to `agent`.)

## Verified on a real deps repo (2026-06-20)

Ran on `blutils` (Preact/Vite/TS, pnpm): the delegation prompt told cursor to `pnpm install` if `node_modules` was missing, then `pnpm typecheck` — and **Tier-1 (`tsc --noEmit`) passed inside the cursor worktree** (independently re-run), code was correct first try, committed in the worktree. So the dep-bootstrap path works *when the prompt instructs the install*. A fresh worktree has none of your gitignored deps, so **always include the install step in the Tier-1 instructions** (or rely on `.cursor/worktrees.json` setup scripts if the repo has them); don't assume deps are present.

## Cleanup

Cursor's worktree auto-cleans in some cases; otherwise remove it after merge with `git worktree remove ~/.cursor/worktrees/<repo>/<task-slug>` (or leave it to the `finish` workflow).
