# Executor: `codex` (OpenAI Codex CLI)

Tool-specific invocation for the `delegate-coding` skill. The method (two-tier verify, merge-as-commit-point, bounded retry, escalation) lives in `../SKILL.md`; this file only covers *how to drive codex as the executor*. **Verified end-to-end against codex-cli 0.141.0 on 2026-06-19.**

`codex exec` runs non-interactively (the same headless entry point the `council` skill uses). It has its own sandbox, so the invocation differs from cursor in two ways that bit during validation — read the commit and resume notes below before using it.

## Preflight

```bash
command -v codex >/dev/null || echo "codex not installed"   # → fall back to another executor / execute
codex --version
```

Codex auth is a one-time `codex login` (or `CODEX_HOME`/API-key setup). If unauthenticated, stop and tell the user — you can't do it for them.

## Isolation (no native worktree)

Codex has no worktree flag. Create the isolated worktree via the **`git-worktree` skill** (or `git worktree add <path> -b <branch>`), bootstrap its env so Tier-1 can run, then pin codex to it with **`-C <worktree>`** (sets the working root — cleaner than `cd`).

## Stage 3 — delegate (first pass)

```bash
codex exec -C <worktree-path> -s workspace-write --json \
  -o /tmp/codex_last.txt \
  "<delegation prompt>"  > events.jsonl
```

- `-C <dir>` — working root (the worktree).
- `-s workspace-write` — let it write files + run commands in the workspace unattended (approval mode `never`). `read-only` and `danger-full-access` are the other options.
- `--json` — emit JSONL events to stdout; the **session/thread id is a UUID in these events** (grep `[0-9a-f-]{36}`). You need it for resume.
- `-o <file>` — write the agent's final message to a file (cleaner than parsing the result text out of JSONL).

**Commit gotcha (verified): do NOT ask codex to commit in a linked worktree.** A linked worktree's git index lives under the *main* repo's `.git/worktrees/...`, which is outside the `workspace-write` sandbox, so `git commit` fails ("cannot write the worktree's git index"). Instead, let codex only edit files, and have **the orchestrator commit** after Tier-1 passes:

```bash
( cd <worktree-path> && python3 -m pytest -q )      # your Tier-1, verified by you
git -C <worktree-path> add -A && git -C <worktree-path> commit -m "<msg>"
```

(Alternatives if you really want codex to commit: `--add-dir <main-repo>` to widen the sandbox, or `--dangerously-bypass-approvals-and-sandbox`. The orchestrator-commit path is simpler and was the one validated.)

## Stage 5 — bounded retry (resume the same session)

```bash
( cd <worktree-path> && codex exec resume -o /tmp/codex_last.txt <session-id> "<exact failure + what to fix>" )
```

**Verified resume constraints (these caused repeated arg-parse failures until pinned down):**
- Arg order is `codex exec resume [OPTIONS] <SESSION_ID> <PROMPT>` — options first, then id, then prompt.
- **`resume` does not accept `-s` or `-C`.** The sandbox is inherited from the original session; set the directory by `cd`-ing into the worktree.
- `--last` resumes the most recent session if you didn't capture the id.

Cap at the default 3 retries, then escalate (you finish) per the method.

## Notes

- **`is_error` / exit code is the real success signal**, not the agent's prose — verify Tier-1 yourself on the worktree.
- Codex's `gpt-5.x-codex` family is the cheap executor tier; omit `-m` to use the account default.
