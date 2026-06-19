---
name: project-skill-audit
description: "Audit a project's real recurring work — from session history, persistent memory, and existing skills — then recommend the highest-value skills to create or update, preferring updates over duplicates. Use when asked what skills a project needs, for skill ideas grounded in real usage (not brainstorming), or to review whether existing project-local skills are stale or redundant."
---

# Project Skill Audit

Recommend skills from **evidence of how the project is actually worked on**, not from a generic wishlist. The signal is a *repeated procedure, validation flow, or failure mode* — a recurring topic is not enough. Prefer updating an existing skill over adding a near-duplicate.

This skill **reports**: it produces an audit + ranked recommendations and stops. When the user picks one to build, hand off to [`skill-creator`](../skill-creator/SKILL.md) — it owns drafting, testing, and the description optimizer.

## What counts as evidence

In rough order of strength:

1. **Repeated procedures** — the same multi-step sequence performed across several sessions (a build/validate dance, a release flow, a data-migration ritual).
2. **Repeated failure shields** — the same mistake made and corrected more than once; context that had to be rediscovered repeatedly.
3. **Recurring validation commands** — the exact check that proves a change correct, run again and again.
4. **Ownership / boundary confusion** — the same "which layer owns this?" question recurring across changes.

A pattern that appears **once** is a task, not a skill. Don't manufacture recurrence.

## Workflow

### 1. Map the project surface

Read the closest project guidance first: `AGENTS.md` / `CLAUDE.md`, `README.md`, any roadmap/ledger/ADR or architecture docs, and the validation expectations they state. This is the durable baseline; usage history refines it.

### 2. Locate the evidence stores (host-neutral)

You need two stores: **session history** (what was actually done) and **persistent memory** (what was worth remembering). Resolve them for the host you're on, then degrade visibly if absent:

| Host | Session transcripts | Persistent memory |
|---|---|---|
| **Claude Code** | `~/.claude/projects/<encoded-cwd>/*.jsonl` | `~/.claude/projects/<encoded-cwd>/memory/MEMORY.md`; in-repo `CLAUDE.md` |
| **Codex** | `$CODEX_HOME/sessions/*.jsonl` (default `~/.codex`); `$CODEX_HOME/memories/rollout_summaries/` | `$CODEX_HOME/memories/MEMORY.md` |
| **Other / unknown** | whatever transcript store the host exposes | in-repo `AGENTS.md` + any agent memory file |

**Degrade rung:** if no session/memory store is reachable (fresh host, no history, sandbox), say so plainly and audit from **repo + git history only** (`git log`, recurring touched areas, docs). State that the usage-history lens was unavailable — a repo-only audit is weaker and the reader must know.

### 3. Read history targeted, not bulk

If a memory summary is already in context, start there. Then search the memory index (`rg` the repo name, basename, and `cwd`) and open only the **1–3 most relevant** summaries or transcripts — those whose path/keywords match this project. Fall back to raw session logs only when a summary is missing a concrete detail (an exact command, a failure string, a diff). **Do not bulk-load all history.**

Extract: what was asked for repeatedly · which steps kept recurring · what broke repeatedly · which commands proved correctness · which project context had to be rediscovered.

### 4. Inventory existing skills before proposing anything

Scan project-local skill folders relative to the repo root — `.claude/skills/`, `.codex/skills/`, `.agents/skills/`, `./skills/` — and read each `SKILL.md` (and any host manifest beside it). Only after that, check shared/global skills, so you don't propose a local skill for something a generic one already covers well. A global skill existing does **not** kill a local one — project-specific guardrails can still justify a specialization.

### 5. Separate "update" from "new"

- **Update** when an existing skill is the right bucket but has drifted: stale triggers, missing guardrails, outdated paths/commands, weak validation, manifest/`SKILL.md` divergence, or a body too generic to match how the project is really worked.
- **New** only when the workflow is distinct enough that stretching an existing skill would make it vague.
- **Neither** when it's a one-off, a generic skill already fits with no project-specific value-add, or the pattern hasn't recurred enough to earn its maintenance cost.

## Output

A compact audit:

1. **Existing skills** — each project-local skill found and the workflow it covers.
2. **Suggested updates** — per candidate: skill name · why it's stale/incomplete · the single highest-value change.
3. **Suggested new skills** — per candidate: name (short, hyphen-case, verb-led) · why it should exist · what triggers it · the core workflow it encodes · **the evidence** ("this validation sequence appeared in 4 sessions").
4. **Priority order** — top recommendations ranked by expected value.

## Failure shields

Two traps the workflow above doesn't already guard against:

- Don't trust a single stale memory note if the repo clearly moved on since.
- Don't confuse the project's current implementation tasks with its reusable skill needs — a backlog item is not a skill.

## Follow-up

If the user wants to build or update a recommended skill, switch to [`skill-creator`](../skill-creator/SKILL.md) and implement the chosen one — this skill's job ends at the recommendation.
