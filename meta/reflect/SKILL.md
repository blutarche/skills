---
name: reflect
description: Spawn three parallel review subagents over the active transcript, surface learnings, and route each to a concrete edit on an existing skill. Use when the user says reflect.
license: MIT
disable-model-invocation: true
---

# Reflect

Adapted from pstack's `reflect` (MIT, © 2026 Lauren Tan); see [`CREDITS.md`](../../CREDITS.md).

## When to skip

Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## Process

### 1. Locate the active transcript

The parent finds its own transcript file before fanning out. Look only in the current agent's own location for this project. Never glob across other projects' transcripts: that crosses workspace boundaries and reads private chats from unrelated projects.

- **Claude Code:** `~/.claude/projects/<cwd with every / replaced by ->/*.jsonl`, newest first.
- **Codex:** `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, today's directory first.
- **Cursor:** the `agent-transcripts/` directory the system prompt names. Three layouts: legacy flat (`<id>.jsonl`), current nested (`<id>/<id>.jsonl`), and subagent (`<parent>/subagents/<child>.jsonl`).
  ```bash
  ls -t <agent-transcripts>/*.jsonl <agent-transcripts>/*/*.jsonl <agent-transcripts>/*/subagents/*.jsonl 2>/dev/null | head -10
  ```
- **Anything else (Hermes, unknown agent):** skip the lookup and use the digest fallback below.

For each candidate (newest first, at most ~10), read the first user message and check that it equals this conversation's opening prompt. Take the matching path. If no candidate matches, or the agent is not listed, write a tight digest of the session and pass that instead.

### 2. Spawn three reviewers in parallel

In one step, spawn three parallel subagents using whatever subagent mechanism the agent has (Claude Code: the Agent tool). Reviewers never edit files. They may use MCP tools to look up context the transcript references.

| Lens | Prompt template (read at this step) |
|---|---|
| Judgment | `references/judgment-reviewer.md` |
| Tooling | `references/tooling-reviewer.md` |
| Divergent | `references/divergent-reviewer.md` |

The tooling lens should come from a different model family than the other two. If the `council` skill is available, run that lens through it. Otherwise run it as a same-family subagent and say so in the step 6 summary.

Pass each template verbatim, substituting the transcript path or digest where marked. Reviewers return findings in their response body.

### 3. Synthesize

Spawn one more subagent with `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. The synthesizer's quality check includes spot-verifying citations, which can require MCP access. It returns a structured Accepted / Rejected / Backlog list.

### 4. Structural enforcement check

Sanity-check the synthesizer's Accepted list. A lesson that a lint, script, hook, or check would enforce more reliably than prose moves from Accepted to Backlog, not a prose edit.

### 5. Apply

Before applying any Accepted edit, present the synthesizer's full Accepted/Rejected/Backlog output to the user and wait for explicit approval. The user picks which subset to apply and may redirect routings. Skill changes affect every future agent. Do not auto-apply.

Edit the source skill in its repo. Installed copies under `~/.claude/skills` and `~/.agents/skills` are symlinks; never edit those paths.

For each approved Accepted item, follow the Routing field exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): parent does directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): follow `writing-great-skills` (user-invoked: read its `SKILL.md` from the installed skills directory and follow it; if it isn't installed, apply its discipline inline), then test the edited skill on a sample prompt.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): rewrite the description per `writing-great-skills` (what the skill does, then `Use when …` cues), then test it on a sample prompt.
- `new skill: <kebab-name>`: create it per `writing-great-skills` and the target repo's skill conventions, then test it on a sample prompt. Do not invent the shape ad hoc.

Backlog items are listed in the reply. With user approval, write each as one MemPalace drawer in the `lessons` room, format `YYYY-MM-DD <rule> — why: <evidence>`. If MemPalace is unavailable, only list them.

Run `./scripts/validate-skills.sh` (in the skills repo) on every touched skill before declaring done. Skip if the repo ships no validator.

### 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog: `<rule>`. One line each; note which were written to MemPalace.
- Dropped: one line per rejected finding + reason from the synthesizer.
- Tooling lens: state whether it ran through `council` or as a same-family subagent.
