---
name: post-mortem
description: Write the canonical engineering record of a fixed bug or resolved incident — root cause, mechanism, fix, validation, and how it slipped through — for other engineers and future-you. Refuses to draft until the bug is fixed and the fix is validated. Use after a debug/diagnose session lands a verified fix (pairs with diagnose), or when asked to write a post-mortem / postmortem / RCA / root-cause analysis, document a fix, or close out a bug with a writeup. For a customer-visible outage it switches to incident mode (timeline, 5 Whys, severity, action items). Blameless throughout.
---

# Post-mortem

## Overview

The canonical engineering record of a bug fix. Written **after** debugging lands a real, validated fix, **for** the next engineer (and future-you, who will have forgotten everything in six months). Code identifiers are first-class here — this is the artifact that lets the next person recover the mental model fast and grep their way back to the offending lines.

**Core principle:** Record what happened, not a hypothesis of what happened. No root cause without evidence; no validation claim broader than what you actually ran; no blame. If the facts aren't there, ask — don't fill the gap with plausible prose.

This pairs with [`diagnose`](../diagnose/SKILL.md): diagnose lands and verifies the fix, post-mortem records it. Pull the diagnose session's repro, rejected hypotheses, and the confirming experiment straight into the writeup.

## Two modes

| Mode | When | Shape |
|---|---|---|
| **Bug fix** (default) | A bug was found, fixed, and the fix validated | The structure below — root-cause-centric engineering record |
| **Incident** | A customer-visible outage / degradation | Timeline-centric: timeline reconstruction → 5 Whys → severity + blast radius → action items |

If it's an outage (users affected, downtime, data loss), confirm and switch to incident mode — it needs a timeline and blast radius the bug-fix shape doesn't capture.

## Required inputs — refuse to draft without these

Before writing a line, confirm all four. If any is missing, list what's missing and **stop**:

```
[ ] Reliable repro      — deterministic or high-rate, runnable by the next person (not "happens sometimes")
[ ] Root cause known    — the mechanism is identified, not a hypothesis
[ ] Fix identified      — PR / commit / branch pointer
[ ] Fix validated       — the original repro now passes; the failing workload/test now succeeds
```

A post-mortem of a hypothesis is worse than no post-mortem. Don't draft one.

**Skip it entirely** for trivial fixes (typo, obvious one-liner) — the PR description is the record. Don't manufacture ceremony.

## Structure (bug-fix mode)

Use these blocks in order. **Summary, Root cause, Fix, Validation are mandatory**; the rest are usually present.

1. **Summary** *(mandatory)* — one paragraph: what broke in workload terms, what fixed it in one sentence, plus ticket/PR/owner. A reader who stops here has the right answer.
2. **Symptom** — what was actually observed: test output, error, log line, perf number, customer report. Concrete identifiers, not paraphrase.
3. **Root cause** *(mandatory)* — the actual bug mechanism, code identifiers expected (functions, files, fields, branch conditions, the offending commit SHA). Walk the cause chain end to end. This is why the document exists.
4. **Why it produced the symptom** — link cause to symptom when it's non-obvious (the bug is in `prepare()` but the visible failure is a hang hours later). Let a reader who only knows the symptom connect it back without re-deriving.
5. **Fix** *(mandatory)* — what changed and **why it addresses the root cause** rather than hiding the symptom. Link the PR. If a prior fix papered over the symptom, name it and what was wrong with it.
6. **How it was found** — short: the repro that made it deterministic, the tools that cracked it, hypotheses tried and the one-line reason each was rejected, and the single experiment that confirmed the cause. For the next debugger — make it learnable.
7. **Why it slipped through** — the real reason it reached the branch/release/customer: CI gap, latent code broken by a later change, workload gap, incomplete prior fix, or review miss. If the honest answer is "we should have caught this," say so. Describe the gap, never the person.
8. **Validation** *(mandatory)* — how you know it works: failing test now passes (name/link), workload completes (id/link), perf number before→after, soak/stress duration. **State coverage honestly** — *"validated on config X; not retested on Y"* is information, not a hole. Implying broader coverage than you ran is the failure mode that breeds repeat regressions.
9. **Action items** — concrete follow-ups not already in the fix PR, each with what + owner (role) + tracking artifact. If there are none, write *"None — fix is sufficient."* Don't invent items to look thorough.

## Structure (incident mode)

1. **Header** — severity (P1/P2/P3), duration, impact (users/systems/data/revenue).
2. **Timeline** — chronological `HH:MM — event (source)`, reconstructed from `git log --since/--until`, CI runs, monitoring, and manual notes.
3. **Root cause — 5 Whys** — Problem → Why 1 (immediate) → … → Why 5 (systemic). Action items aim at the deepest Why, not the symptom.
4. **Action items** — each: action + owner (role) + deadline + which Why it prevents. Categorize: Detection / Prevention / Response / Recovery.
5. **What went well / what to improve** — what limited the blast radius, what systemic gaps remain.

## Tone

- **Code identifiers are first-class** — keep function names, paths, fields, SHAs. They're the index the next engineer greps.
- **Mechanism over narrative** — say which function skipped which step under which condition, not "a synchronization issue."
- **No hedging** — drop "we believe / appears to / may have." State it or leave it out.
- **Blameless** — describe the bug, the gap, the fix. Never "X should have caught this." The CI gap is the failure mode, not the person.
- **No advocacy** — a post-mortem records what happened and what's next. Arguing for a refactor is a separate proposal; link to it from the action items.

## Output flow

1. Confirm readiness. Bug-fix mode: confirm the four required inputs; if any is missing, list them and stop. Incident mode: confirm the incident is resolved or stabilized and the timeline/root cause rest on evidence (monitoring, git log, notes), not reconstruction-by-guess; if the cause is still a live hypothesis, say so and write only the confirmed timeline and open questions — do not assert a root cause.
2. Confirm the destination (PR description, `docs/postmortems/<id>.md`, ticket comment, wiki). The shape is the same; only the wrapping changes.
3. Produce the draft as one block.
4. **Get sign-off before posting anywhere external.** Print-only output needs no approval.

## Rules

- Refuse to draft without all four required inputs (bug-fix mode) / confirmed timeline and evidence (incident mode).
- Never invent root cause, owner, validation runs, or action items — if a section's facts aren't there, ask.

## The Bottom Line

Confirm it's actually fixed and validated, then write the mechanism down clearly enough that the next engineer recovers the whole picture without a meeting — and honestly enough that "what we didn't test" is on the page.
