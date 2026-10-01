---
name: scrutinize
description: Outsider end-to-end review of a diff, PR, or design doc — questions intent, traces the real code path, reports severity-ordered findings with one verdict (ship / fix-then-ship / rework / reject). Read-only. Use when asked to review, audit, or sanity-check a change.
---

# Scrutinize

Stand outside the change as someone who does not already believe it should exist. The diff is the *answer*; scrutiny starts at the *question*. Report findings and a verdict, then stop: you diagnose, you do not operate.

## When to use this skill

Use scrutinize when there is a **concrete artifact already produced** to review (a PR, diff, commit, completed change, design doc, or written plan).

**When NOT to use it (hand off instead):**

| Situation | Use this instead |
|---|---|
| The plan is still being formed and you want interactive back-and-forth | `grill-me` (dialogue) / `grill-with-docs` (doc-anchored) |
| You've decided the code is over-engineered and want it simplified | `simplify` (applies the change) |
| You want AI-generated slop detected and removed | `slop-cleanup` (applies the change) |
| You *received* a review and need to evaluate the feedback | `receiving-code-review` |

Scrutinize **reports**; those skills **edit**. If scrutiny surfaces over-engineering or slop, it names the finding and points to the fixer — it does not rewrite the code itself.

## The Workflow

Run these four phases **in order. Do not skip ahead.**

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

### 3. Verify

For each claim the change makes ("fixes X", "is faster", "handles Y"), find the **evidence** that it is true — don't take it on confidence.

> For a design doc or plan (no code yet), there is nothing to run: replace the test/run steps with the artifact-agnostic check — for each claimed property, name the observation that would confirm or refute it, and ask what evidence the doc offers that the design holds (a worked example, a prior art reference, a failure-mode walkthrough). Treat an unsupported claim as unverified.

```
- Is there a test that fails without the change and passes with it? If not, why is the behaviour believed correct?
- Run it where you can. An empirical check beats any amount of reasoning — read the real output and exit code before calling it green.
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
