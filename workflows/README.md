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
| plan | [`plan`](plan/SKILL.md) | Brief → execution-ready plan: design, council, plan, grill, council; writes no code. |
| execute | [`execute`](execute/SKILL.md) | Approved plan → verified code, interactive-gated or autonomous-subagent. |
| vet | [`vet`](vet/SKILL.md) | Cross-model review (`scrutinize` + `council`) of a finished change or a document, then a gated fix loop. |
| finish | [`finish`](finish/SKILL.md) | Get the branch ready (sync base, verify, one review, hand over the diff); then `land`, `pr`, or `discard` on request and tear down the worktree. |
| (research lane) | [`research-council`](research-council/SKILL.md) | Cross-examine a research answer with `council`; the research analog of `vet`. |
| (plan lane) | [`grill-with-docs`](grill-with-docs/SKILL.md) | Grill session that also maintains the glossary and ADRs; the brownfield counterpart to `grill-me`. |

## Three composition principles

These are why the pipeline is shaped the way it is — and the rule for adding to it.

1. **Pushed workflows vs pulled skills.** A *workflow* is pushed: it owns a sequence and drives you
   through it. A *skill* is pulled: it's atomic, unaware of any sequence, and invoked when needed. The
   ordering lives in the workflow, never inside the leaf skill — that's exactly what lets several
   workflows recombine the same skills differently. Don't push sequencing logic down into a skill.

2. **Compose the official built-ins.** Where the host provides a capability — `/goal` for autonomy,
   `/code-review` / `/security-review`, `/simplify` — the workflow composes it rather than reimplementing
   it. Soft references: use the built-in if present, apply the same discipline inline if not.

3. **Compose our atomic skills.** The workflows are thin sequencers over this repo's own atomic skills
   (`scrutinize`, `council`, `git-worktree`, `diagnose`, the fixer skills,
   …). A workflow that starts re-implementing a skill's methodology has drifted — push it back into the
   skill and call it.
