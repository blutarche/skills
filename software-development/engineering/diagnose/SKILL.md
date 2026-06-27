---
name: diagnose
description: A disciplined loop for hard bugs and performance regressions — reproduce, build a fast deterministic feedback loop, minimise, hypothesise, instrument, fix, and add a regression test. Use when facing a hard bug, an intermittent failure, or a performance regression.
license: MIT
---

# Diagnose

A discipline for hard bugs and performance regressions. Work the phases in order. Skip a phase only when you can explicitly justify why it does not apply.

## Phase 0 — Localise (only when the bug's locus is unknown)

Phase 1 assumes you know *where* to point a loop. When the symptom is real but the responsible subsystem is unknown or ambiguous — a crash with a shallow trace, a regression with no obvious culprit, "it's slow somewhere" — spend a short, **read-only** pass localising before you build the loop. Skip this phase entirely when the locus is already obvious.

Assemble the smallest useful packet first: symptom, expected vs actual, repro steps if any, scope of impact, and whatever evidence exists (logs, traces, failing tests, recent diffs). Then investigate along four angles. **Run them as parallel read-only sub-agents if the host supports it; otherwise sweep them yourself in one pass** (degrade visibly — say which you did). Keep every investigator read-only: no edits, no new instrumentation, no commits yet.

1. **Reproduction & scope** — the narrowest reliable trigger; conditions that make it appear/disappear; whether it's local, cross-cutting, deterministic, or flaky.
2. **Code path & failure seam** — the likely execution path and the seam where behavior diverges: state transitions, caller/callee assumption mismatches, data/control-flow breaks.
3. **Recent change & regression** — diffs, config/flag/dependency/schema drift correlating with the symptom's timing; partial updates where several sites should have changed together.
4. **Proof & observability** — the smallest existing test or non-mutating command that should already fail; the most useful current logs/traces/metrics; what evidence is missing.

Synthesise into **ranked candidate loci** + the fastest non-mutating proof step for the top one. That ranking is the input to Phase 1 (build the loop at the leading locus) and a head start on Phase 4. If the evidence is too thin to rank, say so and name the leading open questions rather than forcing a guess.

## Phase 1 — Build a fast, deterministic feedback loop

**This is the core of the skill. Do it before hypothesising about causes.**

If you have a fast, deterministic, automatically-runnable pass/fail signal for the bug, you will find the cause: bisection, hypothesis-testing, and instrumentation all just consume that signal. Without one, staring at code rarely helps.

Spend disproportionate effort here. Be aggressive and creative; do not give up early.

### Ways to construct a loop — try them in roughly this order

1. **Failing test** at whatever seam reaches the bug — unit, integration, or end-to-end.
2. **HTTP request script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing output against a known-good snapshot.
4. **Headless browser script** that drives the UI and asserts on DOM, console, or network.
5. **Replay a captured trace.** Save a real request, payload, or event log to disk and replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one component, mocked dependencies) that exercises the bug path in a single call.
7. **Property or fuzz loop.** For "sometimes wrong output", run many random inputs and watch for the failure mode.
8. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "set state, check, repeat" so the search can run unattended.
9. **Differential loop.** Run the same input through two versions or two configs and diff the outputs.
10. **Human-in-the-loop, structured.** Last resort, when a human must perform a manual step. Script the surrounding steps so the human action is the only manual part, and feed the captured result back into the loop.

Build the right feedback loop and the bug is most of the way to fixed.

### Iterate on the loop itself

Treat the loop as a product. Once you have one, ask:

- Can I make it **faster**? Cache setup, skip unrelated initialisation, narrow the scope.
- Can I make the signal **sharper**? Assert on the specific symptom, not merely "did not crash".
- Can I make it **more deterministic**? Pin time, seed randomness, isolate the filesystem, freeze the network.

A 30-second flaky loop is barely better than no loop. A 2-second deterministic one is worth real effort to build.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger many times, parallelise, add load, narrow timing windows, inject delays. A 50%-reproducible bug is debuggable; a 1% one is not — raise the rate until it is.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried, then ask for one of: access to an environment that reproduces it; a captured artifact (request capture, log dump, core dump, timestamped recording); or permission to add temporary instrumentation closer to where it occurs. Do **not** hypothesise without a loop.

Do not proceed to Phase 2 until you have a loop you trust.

## Phase 2 — Reproduce

Run the loop and watch the bug appear. Confirm:

- [ ] The loop produces the failure mode **as described**, not a different nearby failure. Wrong bug means wrong fix.
- [ ] The failure is reproducible across multiple runs (or, for non-deterministic bugs, at a high enough rate to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow timing) so later phases can verify the fix addresses it.

Do not proceed until you reproduce the bug.

## Phase 3 — Minimise

Shrink the reproduction to the smallest input and shortest code path that still triggers the failure. Remove unrelated setup, data, and steps one at a time, re-running the loop after each removal. A minimal repro narrows the search space and often reveals the cause on its own.

## Phase 4 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them. Generating a single hypothesis anchors you on the first plausible idea.

Each hypothesis must be **falsifiable** — state the prediction it makes:

> "If X is the cause, then changing Y will make the bug disappear (or changing Z will make it worse)."

If you cannot state the prediction, the hypothesis is a guess — sharpen or discard it.

If a person with domain knowledge is available, share the ranked list before testing; they may re-rank it instantly or point out hypotheses already ruled out. Do not block on this — proceed with your own ranking if no one responds.

For an **ambiguous, cross-layer** bug where several hypotheses stay plausible, gather evidence in parallel instead of anchoring on the top one: one read-only subagent per hypothesis, each collecting evidence for its own and trying to disprove the others — the hypothesis that survives the cross-attack is your leading cause. (Hosts with agent teams can run this as a live debate; worth the extra cost only when disproving one hypothesis bears on the others.) After the survivor emerges, resume at Phase 5 — confirm it with real probes before fixing.

## Phase 5 — Instrument

Each probe must map to a specific prediction from Phase 4. **Change one variable at a time.**

Tool preference:

1. **Debugger or REPL inspection** when the environment supports it. One breakpoint beats ten log lines.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every temporary log** with a unique prefix (e.g. `[DEBUG-a4f2]`) so cleanup later is a single search. Untagged logs tend to survive; tagged logs are easy to remove.

**Performance regressions:** logs are usually the wrong tool. Establish a baseline measurement (timing harness, profiler, query plan), then bisect against it. Measure first, fix second.

## Phase 6 — Fix and add a regression test

Write the regression test **before the fix** — but only if there is a **correct seam** for it.

A correct seam exercises the **real bug pattern** as it occurs at the call site. A seam that is too shallow (a single-caller test when the bug needs multiple callers, or a unit test that cannot replicate the triggering chain) gives false confidence.

If no correct seam exists, that itself is a finding: note it. The architecture is preventing the bug from being locked down.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 loop against the original (un-minimised) scenario.

## Cleanup and post-mortem

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] Regression test passes (or the absence of a correct seam is documented).
- [ ] All tagged instrumentation removed (search for the prefix).
- [ ] Throwaway harnesses and prototypes deleted or clearly marked.
- [ ] The hypothesis that proved correct is recorded in the commit or change description, so the next person learns from it.

Finally, ask: **what would have prevented this bug?** Record the answer after the fix is in — you know more now than when you started.
