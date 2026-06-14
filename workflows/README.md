# workflows

Playbooks that compose atomic skills into an end-to-end process. The **sequencing lives here**, not
inside the skills — which is what lets different workflows recombine the same atomic skills. Each
workflow's `SKILL.md` is the source of truth for its steps.

## The staged pipeline

A change moves left to right through deliberate, named stages:

```
research · plan  →  execute  →  vet  →  finish
```

A **research lane** runs alongside: [`research`](../meta/research/SKILL.md) (gathering — an atomic skill in `meta/`) and [`research-council`](research-council/SKILL.md) (cross-examining a research answer — a composer, so it lives here). Pull them in whenever a stage needs a fact established or checked, not just at the front.

| Stage | Workflow | What it does |
|-------|----------|--------------|
| plan | [`plan`](plan/SKILL.md) | Drive a raw brief through design → **council the approach** → plan → grill → **council the finished plan** to an execution-ready plan. Composes `brainstorming`, `writing-plans`, a grill skill, and `council` (cross-model blindspot diversity vs grill's self-adversarial depth). Does not write code. |
| execute | [`execute`](execute/SKILL.md) | Drive an approved plan to verified code. Picks a mode: **interactive-gated** (main agent, one task at a time, surface blockers — with the state-in-files loop discipline for long efforts) or **autonomous-subagent** (fresh implementer subagent per task + two controller-run review stages: spec-compliance, then `scrutinize` + `council`; wired to `/goal` and the `git-worktree` skill). |
| vet | [`vet`](vet/SKILL.md) | Deliberate cross-model review + gated fix loop on a finished change. Runs `scrutinize` (Claude's outsider pass) then `council` (Codex cross-model attack, which adjudicates the two disagreement-first), **stops** for a decision, then hands fixes to `receiving-code-review` → `/simplify` / `slop-cleanup` and re-reviews until clean. |
| finish | [`finish`](finish/SKILL.md) | Wrap up a finished branch: verify tests → **drain the council** (hard block on pending reviews) → present merge / open-PR / keep / discard → execute → tear down the worktree via the `git-worktree` skill. |
| (research lane) | [`research-council`](research-council/SKILL.md) | Cross-examine a research answer: run your own citation/staleness review, then compose `council` (cross-model attack + adjudication). The research analog of `vet` — same composer shape; pairs with the `research` skill in `meta/`. |

## Three composition principles

These are why the pipeline is shaped the way it is — and the rule for adding to it.

1. **Pushed workflows vs pulled skills.** A *workflow* is pushed: it owns a sequence and drives you
   through it. A *skill* is pulled: it's atomic, unaware of any sequence, and invoked when needed. The
   ordering lives in the workflow, never inside the leaf skill — that's exactly what lets several
   workflows recombine the same skills differently. Don't push sequencing logic down into a skill.

2. **Compose the official built-ins.** Where the host provides a capability — `/goal` for autonomy,
   `/review` / `/security-review`, `/simplify` — the workflow composes it rather than reimplementing
   it. Soft references: use the built-in if present, apply the same discipline inline if not.

3. **Compose our atomic skills.** The workflows are thin sequencers over this repo's own atomic skills
   (`scrutinize`, `council`, `git-worktree`, `verification-before-completion`, the fixer skills,
   …). A workflow that starts re-implementing a skill's methodology has drifted — push it back into the
   skill and call it.
