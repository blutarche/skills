---
name: scrutinize
description: "Outsider-perspective end-to-end review that produces a written findings report. Questions intent and whether a simpler approach (including doing nothing) achieves the goal, traces the actual code path — not just the diff — to verify the change does what it claims, then reports severity-ordered findings with one verdict (ship / fix-then-ship / rework / reject). Read-only: it flags issues, it does not edit. Use on /scrutinize, or when asked to review, audit, sanity-check, or get a second opinion on a PR, diff, design doc, or completed code change. For interactive plan-hardening dialogue use grill-me; to apply simplifications use simplify; to strip AI slop use slop-cleanup."
---

# Scrutinize

## Overview

A review is worthless if it only checks whether the code matches the diff. The diff is the *answer*; scrutiny starts at the *question*. Stand outside the change as someone who does not already believe it should exist.

**Core principle:** Question the intent before the implementation. Trace the real code path, not the diff. Verify the claim against evidence, not against the author's confidence. Report findings and a verdict — then stop. You diagnose; you do not operate.

## When to use this skill

Use scrutinize when there is a **concrete artifact already produced** to review:
- a PR, a diff, a commit, a completed code change
- a design doc or a written plan
- the user asks to "review", "audit", "sanity-check", or get a "second opinion"

**When NOT to use it (hand off instead):**

| Situation | Use this instead |
|---|---|
| The plan is still being formed and you want interactive back-and-forth | `grill-me` (dialogue) / `grill-with-docs` (doc-anchored) |
| You've decided the code is over-engineered and want it simplified | `simplify` (applies the change) |
| You want AI-generated slop detected and removed | `slop-cleanup` (applies the change) |
| You *received* a review and need to evaluate the feedback | `receiving-code-review` |

Scrutinize **reports**; those skills **edit**. If scrutiny surfaces over-engineering or slop, it names the finding and points to the fixer — it does not rewrite the code itself.

## The Workflow

Run these four phases **in order. Do not skip ahead.** Skipping to the report is how reviews become rubber stamps.

```
1. INTENT   — what is this for, and is there a smaller way?
2. TRACE    — follow the real code path the change participates in
3. VERIFY   — does the change actually do what it claims?
4. REPORT   — severity-ordered findings + one verdict
```

### 1. Intent

Distill the goal to **one sentence**: what is this change actually trying to achieve?

Then run **one mandatory simpler-alternative pass** — ask, in order:

```
1. Doing nothing — is the problem real and load-bearing, or speculative?
2. A smaller change — does a subset of this achieve the goal?
3. A more elegant approach — does an existing mechanism already solve it?
```

If a materially simpler path exists, that is your first finding. The simplest version of a change you cannot reject is the one you measure everything else against.

### 2. Trace

Treat the diff as the **entry point, not the scope.** Follow the actual code path the change participates in: callers, callees, the data as it flows through, the states the system can be in when this runs.

> For a design doc or plan (no code yet), trace the *proposed* path instead: walk the design end to end against the existing system — what it touches, what assumes what, which states and failure modes it must handle — and surface the gaps the doc glosses over.

```
- What calls into the changed code, and with what assumptions?
- What does the changed code call, and does it handle every return/throw?
- What inputs, concurrency, or error states reach this path that the diff doesn't show?
- What existing behaviour shares this path and could break?
```

You are reconstructing reality, not reading the author's summary of it.

### 3. Verify

For each claim the change makes ("fixes X", "is faster", "handles Y"), find the **evidence** that it is true — don't take it on confidence.

> For a design doc or plan (no code yet), there is nothing to run: replace the test/run steps with the artifact-agnostic check — for each claimed property, name the observation that would confirm or refute it, and ask what evidence the doc offers that the design holds (a worked example, a prior art reference, a failure-mode walkthrough). Treat an unsupported claim as unverified.

```
- Is there a test that fails without the change and passes with it? If not, why is the behaviour believed correct?
- Run it where you can. An empirical check beats any amount of reasoning (see: verification-before-completion).
- For each claimed property, name the observation that would confirm or refute it.
```

Beware agreement as evidence. If every reviewer "looks right" but nothing was run, the change is unverified, not verified.

### 4. Report

Produce a **severity-ordered** report: `blocker → major → nit`. Each finding has exactly these parts:

```
- Finding       — one sentence, specific. Cite file:line when applicable.
- Why it matters — the consequence, not the principle. ("This drops events under load," not "violates SRP.")
- Evidence       — the trace step or input that exposes it.
- Suggested change — concrete and minimal. Name the fixer skill if one applies.
```

End with a **single verdict** and the **one biggest reason** for it. Map severity to verdict: no blockers and no majors → `ship`; majors but no blockers → `fix-then-ship`; one or more blockers with the approach sound → `rework`; the intent or approach is wrong (a blocker that fixing the code won't cure) → `reject`.

```
VERDICT: ship | fix-then-ship | rework | reject
REASON:  <the single most important factor>
```

No finding without a consequence. No verdict without a reason.

## Specialist lenses

Sweep the trace through these five lenses before reporting. The lens *set* is the coverage floor — **name every lens and say what you found, even if "nothing"**; silently dropping a lens is how a security or contract regression ships unreviewed. What scales is *how* you run them, not *whether*:

- **Small or low-risk diff** — one deliberate pass covering all five yourself.
- **Wide or risky change** — run the lenses as **parallel read-only sub-agents if the host runtime supports them**, each with the same scope and intent; otherwise a single pass, lens by lens. Sub-agents inspect and report findings back only — they never edit, stage, or commit. (Degrade is visible: if you cannot fan out, say the review was single-pass.)

| Lens | What it hunts |
|---|---|
| **Correctness & regression** | edge cases, error handling, concurrency, unintended behavior drift outside the stated scope, broken fallback paths, contract drift between caller and callee. |
| **Security & privacy** | untrusted input, missing/weakened authz, secrets or sensitive-data exposure, injection, risky defaults, trust of unverified data. |
| **Performance & reliability** | duplicate work or redundant I/O, new cost on a hot/startup/render path, leaks, missing cleanup, retry storms, ordering/race/failure-handling fragility. |
| **Contracts & coverage** | API/schema/type/config/flag mismatches, migration or backward-compat fallout, missing or weak tests for the changed behavior, missing logs/metrics/assertions that would catch a regression. |
| **Simplification** | over-engineering, speculative generality, abstraction that earns nothing. |

Consolidate: if two lenses flag the same issue, it is one finding, ranked by its worst consequence. Report only what materially affects correctness, security, reliability, compatibility, or confidence — a missed nit beats burying the real findings in noise.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Reviewing the diff as the whole scope | Trace the real path the diff sits in |
| Accepting "it works" without running it | Find the failing-then-passing test, or run it |
| Listing principles violated | State the concrete consequence instead |
| Findings with no severity | Order blocker → major → nit; no flat lists |
| Hedging the verdict | One verdict, one biggest reason |
| Fixing the code while reviewing | Report and hand off to simplify / slop-cleanup |

## The Bottom Line

Question the intent, trace the reality, verify the claim, then report once — clearly enough that the author can act without a meeting. Diagnose; don't operate.
