# Executor: `claude` (headless, cheaper model)

Tool-specific invocation for the `delegate-coding` skill. The method (two-tier verify, merge-as-commit-point, bounded retry, escalation) lives in `../SKILL.md`; this file only covers *how to drive a headless, cheaper Claude as the executor*.

Your "brain" is an expensive Claude (Opus); when the spec is clear, hand the *coding* to a **cheaper** Claude — Haiku or Sonnet — running as a separate headless `claude -p` process in an isolated worktree. Same vendor, much lower cost per token, plenty capable for well-specified mechanical work.

> **When NOT to use this — use `execute` instead.** If you want in-process subagent orchestration (Task-tool subagents, two-stage spec + `scrutinize`/`council` review, `/goal`-driven continuous loops), that's the `execute` workflow's autonomous-subagent mode. This reference is specifically for the *headless CLI in a worktree, for cost* path — a peer of cursor-agent/codex, not a replacement for `execute`.

## Preflight

```bash
command -v claude >/dev/null || echo "claude CLI not installed"   # → fall back to execute / inline
```

`claude` is already authenticated for the session you're in, so there's usually no separate login step. Confirm the cheaper model is available to the account (`claude --model haiku -p "say ok"` as a smoke test).

> Unlike codex, `claude` isn't sandboxed away from the main repo's `.git`, so the executor **can self-commit in the linked worktree**. The `--output-format json` result carries `result`, `session_id`, and `is_error`.

## Isolation (no native worktree)

`claude` has no `--worktree` flag, so create the isolated worktree yourself via the **`git-worktree` skill** (setup), then point the executor at it. Bootstrap its env (the skill's setup runs the project install, or stops and surfaces that it must be set up) so Tier-1 (`tsc`, unit tests) can actually run — a fresh worktree has no `node_modules`.

## Stage 3 — delegate (first pass)

Run the cheaper Claude headless, scoped to the worktree:

```bash
claude -p "<delegation prompt>" \
  --model haiku \
  --output-format json \
  --permission-mode bypassPermissions \
  --add-dir <worktree-path>
```

- `-p / --print` — non-interactive; prints the result and exits.
- `--model haiku` (or `sonnet`) — the cheaper executor model. Don't use the brain's model here.
- `--output-format json` — capture the result and the **session id** (for `--resume`). `stream-json` is available if you want incremental output.
- `--permission-mode bypassPermissions` — run unattended (it's confined to a throwaway worktree). Verify the exact mode name with `claude --help`; `--add-dir` grants the worktree as a working root.
- Run it with the worktree as cwd (or via `--add-dir`) so all edits land there, not in your main tree.

## Stage 5 — bounded retry (resume the same session)

```bash
( cd <worktree-path> && claude -p "<exact failure output + what to fix>" --resume <sessionId> --output-format json --permission-mode bypassPermissions )
```

Capture the `session_id` from the first run's JSON; `--resume` continues that session so the executor keeps its context across retry rounds. **Run it with the worktree as cwd** — like other CLI agents, a resumed `claude -p` operates in the launch directory, so resuming from your main repo would edit the wrong tree. Cap at the default 3, then escalate (you finish) per the method.

## Notes

- **Cost check:** the savings come from the model tier (Haiku/Sonnet ≪ Opus). If the task keeps bouncing back over the retry cap, a cheaper model was the wrong call — escalate to the brain rather than burning rounds.
- **Commit when green:** instruct the executor to commit in the worktree once Tier-1 passes, so there's a clean branch to merge (Stage 6).
