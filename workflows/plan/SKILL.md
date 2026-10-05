---
name: plan
disable-model-invocation: true
description: "Brief → hardened, execution-ready plan: brainstorm, write plan, grill, council. Writes no code."
---

# Plan (workflow)

Invoke each composed skill in turn and carry its output forward; there is no automatic return between skills, so you own the sequence. This workflow plans; it does not build.

For just one stage, invoke that skill directly. To shape a design, use `brainstorming`. To turn an existing spec into a plan, use `writing-plans`. To grill an existing plan, use `grill-me` (the user can also type `/grill-with-docs` for the brownfield version).

## Stages

Run in order. Finish each stage's gate before moving to the next. If a later stage exposes a flaw, return to the relevant earlier skill and re-run from there.

1. **Design: invoke `brainstorming`**
   Run `brainstorming` to its normal terminus: an approved, committed design doc. It owns the design dialogue; don't truncate it.
   *Gate:* `brainstorming`'s approved design doc exists.

2. **Council the approach: invoke `council`**
   Before building on the design, cross-examine its chosen approach. A flawed architecture is cheapest to catch now, before planning and before code. `council` decision mode needs **2–4 concrete options**. So present the design's approach **plus the leading alternatives it was weighed against** (reconstruct them from the design's rationale). Be as neutral as you can. You can't fully un-bake an approved lean, but you can lay the alternatives out fairly. Let it argue the strongest case against each and name the angle missed. Fold surviving objections back into the design before planning.
   *Gate:* the approach is cross-examined; surviving objections are resolved or recorded in the design, and the updated design doc is re-committed.

3. **Plan: invoke `writing-plans`**
   Use the approved design doc as the spec; produce a bite-sized, TDD-shaped implementation plan.
   *Gate:* the plan is saved and its self-review passed.

4. **Harden: invoke a grill skill**
   Pick by context:
   - **Brownfield** (existing codebase / docs): `grill-me` while applying `domain-modeling` discipline. Stress-test the plan against the domain model, keeping the `CONTEXT.md` glossary and ADRs current. This is what `grill-with-docs` composes; it is user-invoked, so don't invoke it.
   - **Greenfield** (nothing to grill against yet): `grill-me`.
   Fold the grilling's conclusions back into the plan file.
   *Gate:* surfaced issues are resolved or explicitly deferred in the plan.

5. **Council the finished plan: invoke `council`**
   With the plan hardened by grill, convene `council` once more on the *finished plan*. Use the brief "what's missing or unsound here?". Grill is self-adversarial depth. `council` is cross-model blindspot diversity: a different model family handed the plan cold with orders to break it. They catch different classes of flaw, so run both. Fold surviving findings into the plan.
   *Gate:* the council's surviving findings are resolved or explicitly deferred in the plan.

   **Degrade visibly:** if no outside model is reachable, `council` falls back down its own ladder. For a *plan/decision*, the in-family rung is a **critical re-read of the artifact under review**. That is the design at step 2 and the finished plan at step 5. It is not `scrutinize`, which is the code-diff methodology. Ideally, do it in a **fresh subagent**. The plan must **say so**: steps 2 and 5 lose their cross-model property and the reader needs to know. With no council at all, grill alone still hardens the plan; note that the cross-model lens was skipped.

6. **Hand off to execution**
   The plan is now execution-ready. Deliver it as a `brief` sheet of kind `plan`. Show open questions as asks, and the grill and council results as the hardening table. Show the plan's tasks with their `after` order (the build draws the waves). Show the grill's decisions as the decision table, and the plan file's path in the title block. Then reply in 3 lines at most: state, what needs you, path. The brief is the reader's copy, the plan file stays the executable artifact `execute` reads. Without `brief` installed, hand back the plan file path alone. Use short sentences and common words; see `brief`'s `lib/voice.md` when installed. **This workflow stops here**: it plans, it does not build. The natural next step is the `execute` workflow, which drives the saved plan to working code one task at a time. Hand off to whatever executes work in this environment (the user, `execute`, subagents). This is a handoff, not an auto-invoke. The next workflow is the caller's choice.
