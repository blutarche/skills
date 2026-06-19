---
name: plan
description: "End-to-end planning workflow — take a raw brief, feature request, or app idea and drive it to a hardened, execution-ready implementation plan. Use when you want the full pipeline (design → plan → stress-test), not just one step. Composes the brainstorming, writing-plans, grill, and council skills in order. Does NOT write production code."
---

# Plan (workflow)

Drives a raw brief to an execution-ready, hardened plan by running the planning skills in order.

This is a **linear playbook**, not a router. You (the agent) stay in control: move through the stages, invoke each composed skill in turn, and carry its output forward to the next stage. There is no automatic return between skills — you own the sequence. This workflow plans; it does not build.

## When to use this vs a single skill

- **Use this workflow** when you have a vague idea and want the whole journey to a ready-to-build plan.
- **Invoke a single skill directly** when you only need one stage — e.g. just shape a design (`brainstorming`), just turn an existing spec into a plan (`writing-plans`), or just grill an existing plan (`grill-me` / `grill-with-docs`).

## Stages

Run in order. Finish each stage's gate before moving to the next.

1. **Design — invoke `brainstorming`**
   Run `brainstorming` to its normal terminus — an approved, committed design doc. It owns the design dialogue; don't truncate it.
   *Gate:* `brainstorming`'s approved design doc exists.

2. **Council the approach — invoke `council`**
   Before building on the design, cross-examine its chosen approach — architecture is the expensive-to-reverse class, and catching a flawed approach now (pre-planning, pre-code) is the cheapest it ever gets. `council` decision mode needs **2–4 concrete options**, so present the design's approach **plus the leading alternatives it was weighed against** (reconstruct them from the design's rationale), as neutrally as you can — you can't fully un-bake an approved lean, but you can lay the alternatives out fairly. Let it argue the strongest case against each and name the angle missed. Fold surviving objections back into the design before planning.
   *Gate:* the approach is cross-examined; surviving objections are resolved or recorded in the design, and the updated design doc is re-committed.

3. **Plan — invoke `writing-plans`**
   Use the approved design doc as the spec; produce a bite-sized, TDD-shaped implementation plan.
   *Gate:* the plan is saved and its self-review passed.

4. **Harden — invoke a grill skill**
   Pick by context:
   - **Brownfield** (existing codebase / docs): `grill-with-docs` — stress-test the plan against the domain model and ADRs.
   - **Greenfield** (nothing to grill against yet): `grill-me`.
   Fold the grilling's conclusions back into the plan file.
   *Gate:* surfaced issues are resolved or explicitly deferred in the plan.

5. **Council the finished plan — invoke `council`**
   With the plan hardened by grill, convene `council` once more on the *finished plan* with the brief "what's missing or unsound here?". This is the complementary lens to grill: **grill is self-adversarial depth** — your own model digging into its own plan until each branch resolves — and **`council` is cross-model blindspot diversity** — a different model family that doesn't share your blind spots, handed the plan cold with orders to break it. The two catch different classes of flaw, so run both. Fold surviving findings into the plan.
   *Gate:* the council's surviving findings are resolved or explicitly deferred in the plan.

   **Degrade visibly:** if no outside model is reachable (no cross-model CLI installed/authed, or you're not at the top level), `council` falls back down its ladder — for a *plan/decision* the in-family review is a **critical re-read of the artifact under review** (the design at step 2, the finished plan at step 5; not `scrutinize`, which is the code-diff methodology), ideally in a **fresh subagent** for clean context. The plan must **say so**: a same-family review can't see the blind spots you share, so steps 2 and 5 lose their cross-model property and the reader needs to know. With no council at all, grill alone still hardens the plan; note that the cross-model lens was skipped.

6. **Hand off to execution**
   The plan is now execution-ready. **This workflow stops here** — it plans, it does not build. The natural next step is the `execute` workflow, which drives the saved plan to working code one task at a time; `verification-before-completion` is the closer once code is written. Hand off to whatever executes work in this environment (the user, `execute`, subagents). This is a handoff, not an auto-invoke — the next workflow is the caller's choice.

## Rules

- One stage at a time. Don't skip a gate. If a later stage exposes a flaw, return to the relevant earlier skill and re-run from there.
- The composed skills are **atomic and unaware of this sequence** — the ordering lives here, on purpose, so other workflows can recombine the same skills differently. Don't push sequencing logic back down into the leaf skills.
- Terminal state is a hardened plan + handoff. Do not start writing production code from this workflow.
