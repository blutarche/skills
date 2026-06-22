---
name: delegate-coding
description: "Execute an approved implementation spec by delegating the coding to a cheaper/faster headless agent CLI (cursor-agent, codex, or a cheaper claude) while the main agent plans, verifies, and owns the merge. Use when you have a clear, self-contained task or plan and want another agent to write the code instead of doing it inline — for cross-family diversity, parallelism, or cost on large/repetitive work — e.g. 'have cursor do this', 'delegate this to cursor-agent', 'let codex implement this', 'let the cheap model write it', or any time the implementation is well-specified and mechanical enough to hand off. Also invoke explicitly as /delegate-coding. Does NOT write the plan; pair it with `plan` / `writing-plans` upstream."
---

# Delegate Coding

Take an approved, self-contained implementation spec and drive it to verified code by handing the **coding** to a cheaper/faster headless agent CLI — the Cursor CLI (`agent`), `codex`, or similar — while you (the main agent) keep the parts where your judgment earns its cost: planning, verifying, and owning the merge.

The point is the asymmetry: a cheap, fast executor for the mechanical edits; a smart verifier for the gate. That only pays off if the verify gate is real, so the gate is the non-negotiable core of this skill, not an afterthought.

**The decision rule — delegate the middle band.** Your expensive "brain" (e.g. Opus) is for the work only it can do: shaping the plan and verifying the result. Route by the task, not by reflex:

- **Too trivial** (a one-liner, a single-file rename, a typo, a quick fix) → **do it inline.** The delegation overhead — worktree, verify gate, round-trip — costs more dev time than it saves. Forcing trivial work through delegation is bad DX, not a win.
- **The sweet spot** (non-trivial but cleanly specifiable, so a cheaper agent can execute it faithfully behind a real gate) → **delegate.** Most feature work, migrations, CRUD/resolvers, refactor-by-pattern, config bumps live here. Prefer a *different family* (cursor/codex) over the cheaper-claude executor when you want cross-family diversity, not just cost.
- **Too hard to delegate safely** → **keep it with the brain**, for one of two distinct reasons:
  - (a) the task genuinely needs implementation-time judgment a cheaper model lacks (subtle architecture, security-sensitive, deeply ambiguous) → Claude codes it directly;
  - (b) your *plan* isn't thorough enough to keep a dumber model on rails → **notice that** and harden the plan first (`plan` / `writing-plans`). Shipping a thin spec to a weak model is exactly how it goes off the rails — the failure looks like the delegate's fault but it's an under-planning fault.

The tell for (b): if you catch yourself hand-waving a step, that step is the brain's job. Fix the plan or do that part inline; don't outsource the hand-wave.

Cost breaks even on small tasks and wins as they grow; the durable reasons to delegate are cross-family diversity and parallelism.

**This file is the tool-agnostic method.** The per-tool invocation (preflight, headless flags, worktree, resume, output parsing) lives in `references/<tool>.md` — read the one for your executor when you reach Stage 3. Pick the executor that fits your intent — cheapest for a cost play, a different family for diversity:

| Executor | Reference | Isolation | What it is |
|----------|-----------|-----------|-----------|
| `agent` (Cursor CLI) | [`references/cursor-agent.md`](references/cursor-agent.md) | native `--worktree` | Cursor's headless CLI (`agent`; legacy alias `cursor-agent`); cheap default model (Composer). |
| `codex` | [`references/codex.md`](references/codex.md) | via the `git-worktree` skill | OpenAI Codex CLI (`codex exec`). |
| `claude` | [`references/claude.md`](references/claude.md) | via the `git-worktree` skill | Headless `claude -p` on a cheaper model (Haiku/Sonnet). For in-process subagent orchestration with cross-model review, use `execute` instead. |

## Operational guardrails

- **No plan yet?** Don't delegate raw input — shape it first (`plan`, `writing-plans`), then come back. Delegation executes a spec; it doesn't author one.
- **Fall back to `execute`** if no executor CLI is installed or authenticated (see Preflight) — don't simulate the delegation.

## The core idea: a clean division of labor

The whole design turns on one fact: a **git worktree shares `.git` but has its own working files**, so gitignored things — `.env`, `node_modules`, build caches — are *absent* from the executor's worktree, and running services/ports are configured for your main tree. That makes full, env-dependent verification fragile inside the worktree. So split verification into two tiers, with **the merge as the commit point**:

| Tier | Where it runs | Who owns it | What it covers |
|------|---------------|-------------|----------------|
| **Tier 1** — env-independent | the executor's worktree | the executor, self-looping | typecheck (`tsc --noEmit`), lint, build, pure unit tests |
| **Tier 2** — env-dependent | your main working tree, **after merge** | you (main agent) | integration/e2e, anything needing `.env` / services / DBs, `/goal` acceptance |

The flow is single-direction, no merge-thrash:

```
spawn executor in an isolated worktree  →  codes + iterates until Tier-1 checks pass (cheap, internal)
you review the diff in the worktree
        │
   ┌────┴───────────────────────────────┐
   │  merge worktree branch → main tree  │  ← COMMIT POINT
   └─────────────────────────────────────┘
you run Tier-2 (envs, services, /goal) in the main tree
   pass → done
   fail → you continue directly (the escalation, below)
```

**The single rule that keeps this robust: the gate the executor iterates against must be env-independent.** If your real acceptance check needs envs or services, that check is yours, post-merge — never push it into the worktree.

## Preflight (fail loud)

Before delegating anything, confirm the executor is actually installed **and** authenticated — the exact commands are in `references/<tool>.md`. A silent fallback to doing it yourself defeats the purpose; a silent failure is worse. If the CLI is missing or not logged in, stop, tell the user the one-time setup command (you can't auth for them), and fall back to `execute`.

**Model:** inherit the executor's cheap default rather than pinning a model id per call (ids rot) — but **verify the default that governs headless runs is actually cheap**, and set it once if not. It may differ from what the CLI's model list labels "default" (e.g. the Cursor CLI's headless default lives in `~/.cursor/cli-config.json`, not `--list-models`). See the reference for where to set it.

## Stages

Run in order. Each gate must pass before the next.

### 1. Load and sanity-check the spec
Read the entire spec/plan. You must be able to restate, in your own words, what "done" looks like and **which checks prove it** — and you must classify each check as Tier 1 (env-independent, the executor's loop) or Tier 2 (env-dependent, yours). If the acceptance check is all Tier 2 and there's nothing cheap for the executor to iterate against, add a Tier-1 gate (at minimum "typechecks and builds") so it isn't coding blind.

**On-rails check (decide go / no-go here).** Before delegating, gut-check that a *weaker* model could satisfy this spec without having to invent decisions about **the contract or what "done" means**. (Implementation latitude is fine — even wanted, on the diversity path — *as long as the acceptance gate pins correctness*.) Walk it: is the contract concrete and the gate decisive, or are you hand-waving? A hand-wave in the contract or the gate is the (b) backfire mode — **harden the plan first** (`plan` / `writing-plans`) or do the ambiguous parts inline. Better to not delegate than to ship a thin contract and babysit a derailment.
*Gate:* you have a written spec thorough enough that a weaker model won't have to guess, **and** a concrete Tier-1 command set it can run in isolation. If not, fix the plan or keep it inline — don't proceed.

### 2. Write the delegation prompt
The executor gets one self-contained brief — it does not share your context. Include:
- **The task** — spec tightness follows your intent (see cost-vs-diversity above). For **cost**: fully determined (files, signatures, behavior) so the executor just types it. For **diversity**: the contract, interfaces, and acceptance gate, with implementation deliberately left open. Either way: surgical scope, no adjacent "improvements", and the **acceptance gate is always unambiguous** — that's what catches a wrong result regardless of how it was written.
- **Guardrails for a weaker model (vital):** embed the `karpathy-guidelines` rules directly in the prompt — surgical changes only, reuse before adding, read before writing, no speculative abstraction or defensive cruft, surface conflicts/assumptions instead of guessing, fail loud. The external executor can't load the skill, and a cheaper model drifts into slop and over-engineering without these rails — this is what keeps it from going off track. Paste the rules inline; don't just name the skill.
- **The Tier-1 gate**: the exact commands to run and the instruction to *iterate until they pass*.
- **Boundaries**: do **not** run integration/e2e tests or anything needing `.env`/services/DBs — those are verified later, elsewhere. If deps aren't installed in the worktree, install them first (e.g. `pnpm install`) so Tier-1 can run.
- **Commit when green**: once Tier-1 passes, the work gets committed in the worktree so there's a clean branch to merge — by the executor, or by you if it can't commit under its sandbox (see the executor's reference).
- **Report**: status (DONE / BLOCKED / NEEDS_CONTEXT) and what was changed.

*Gate:* the prompt is self-contained — someone with no other context could act on it.

### 3. Delegate (first pass)
Invoke the executor **headless, in an isolated worktree**, per `references/<tool>.md`. Capture whatever that tool needs for the retry loop — typically a session/chat id (to resume) and the worktree path. Tools with no native worktree are isolated via the `git-worktree` skill, pointing the executor at that path.

### 4. Verify Tier 1 yourself — don't trust the report
Re-run the Tier-1 checks in the worktree on fresh evidence. A weaker executor will report "done" optimistically; the gate is the actual command output and exit code, not the prose. Apply `verification-before-completion` discipline here.
```bash
( cd <worktree-path> && <tier-1 commands> )
```
*Gate:* Tier-1 commands pass on real output. Also read the diff — confirm it built *exactly* the spec, nothing missing, nothing extra.

### 5. Bounded retry (pre-merge only)
If Tier-1 fails or the diff is wrong, feed the specific failure back into the **same** executor session (resume — see the reference) — this is the cheap loop, so let the executor do the churning. **Run the resume with the worktree as the working directory:** a resumed session does not reliably reattach to its worktree, and launched from the wrong cwd it will edit — and can *commit* — in your main repo instead. Cap it at **N retries (default 3)**. Re-verify (Stage 4) after each. If still failing after N, **stop retrying the executor** and escalate (Stage 7) — don't loop forever feeding a model that isn't converging.

### 6. Merge — the commit point
Bring the worktree's committed branch into your working tree:
```bash
WT_BRANCH=$(git -C <worktree-path> branch --show-current)
git merge --no-ff "$WT_BRANCH"        # from your main working tree
```
Review the merged diff once more in the main tree. Everything past this line is yours — re-delegating across the merge boundary means branching a fresh worktree off updated HEAD, which isn't worth the friction.

### 7. Tier 2 — verify in the main tree (yours), and escalate on failure
Run the env-dependent verification where the env actually lives: integration/e2e, services, `/goal` acceptance.
- **Pass →** done with implementation.
- **Fail →** *you* continue the work directly in the main tree — this is the escalation the design chose ("bounded retry → main agent finishes"). It guarantees the task completes. If it's a hard bug or perf regression, use `diagnose`; a flaky/wrong-for-the-right-reason test, `de-flaking-tests`. Don't weaken the check to make it pass, and don't bounce env failures back to the executor.

### 8. Review pass, then report
Keep authoring and review separate — don't self-approve in the same breath. Run `slop-cleanup` over the diff (behavior-preserving) to strip characteristic AI slop, which a cheap executor tends to produce more of. If you get review feedback, apply `receiving-code-review` to weigh it with rigor. Then report what was implemented, which files changed, the Tier-1 evidence from the executor, and your Tier-2 evidence. **The skill stops here** — the natural follow-on is `finish` (which can also tear down the worktree).

Soft references throughout: use the named skill if installed, apply the same discipline inline if not.
