---
name: receiving-code-review
description: Evaluate code-review feedback with technical rigor — verify each claim against the codebase, push back with reasons when the reviewer is wrong, then implement what is valid. Use when receiving code-review feedback, before acting on suggestions, especially when feedback seems unclear or technically questionable.
license: MIT
---

# Receiving Code Review

## Overview

Code review is a technical evaluation, not a social performance. A suggestion is a claim to be checked, not an order to obey.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code-review feedback:

1. READ      — Take in the complete feedback without reacting.
2. UNDERSTAND — Restate each item in your own words (or ask if unclear).
3. VERIFY     — Check each claim against the actual codebase.
4. EVALUATE   — Is it technically sound for this codebase?
5. RESPOND    — Technical acknowledgment, or reasoned pushback.
6. IMPLEMENT  — One item at a time, testing each.
```

## No Performative Agreement

Do not open with validation phrases ("You're absolutely right", "Great point", "Excellent feedback") or with "Let me implement that now" before you have verified the claim. They add no information and signal compliance instead of evaluation.

Instead:
- Restate the technical requirement, or
- Ask a clarifying question, or
- Push back with technical reasoning if the suggestion is wrong, or
- Just do the work and let the diff speak.

When feedback is correct, acknowledge it factually and move on:

```
GOOD: "Fixed — [what changed, where]."
GOOD: "Confirmed the off-by-one; corrected in parse()."
GOOD: [just fix it; the code shows you heard]

AVOID: "You're absolutely right!" / "Great point!" / "Thanks for catching that!"
```

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP — do not implement anything yet.
  ASK for clarification on the unclear items.

WHY: Items may be related. Partial understanding produces wrong implementation.
```

**Example:**
```
Feedback: "Fix items 1–6."
You understand 1, 2, 3, 6 but not 4, 5.

WRONG: Implement 1, 2, 3, 6 now; ask about 4, 5 later.
RIGHT: "I understand 1, 2, 3, 6. I need clarification on 4 and 5 before proceeding."
```

## Verifying a Suggestion

Before implementing any external suggestion, check:

```
1. Is it technically correct for this codebase?
2. Would it break existing functionality?
3. Is there a reason the current implementation is the way it is?
4. Does it hold across all supported platforms/versions?
5. Does the reviewer have the full context?

IF the suggestion seems wrong:
  Push back with technical reasoning.

IF you cannot easily verify it:
  Say so: "I can't verify this without [X]. Should I investigate, ask, or proceed?"

IF it conflicts with a prior decision by the project owner:
  Surface the conflict before acting.
```

Treat external feedback as suggestions to evaluate, not orders to follow. Be skeptical, but check carefully.

## YAGNI Check for "Do It Properly" Requests

```
IF a reviewer suggests "implementing this properly":
  grep the codebase for actual usage.

  IF unused:  "Nothing calls this. Remove it (YAGNI)?"
  IF used:    Then implement it properly.
```

Do not add capability that nothing needs, even when asked to make something "professional".

## When To Push Back

Push back when the suggestion:
- Breaks existing functionality
- Comes from a reviewer lacking full context
- Adds an unused feature (YAGNI)
- Is technically incorrect for this stack
- Ignores legacy/compatibility constraints
- Conflicts with an established architectural decision

**How to push back:** Use technical reasoning, not defensiveness. Ask specific questions. Reference the working tests or code that prove your point.

## When Your Pushback Was Wrong

```
GOOD: "You were right — I checked [X] and it does [Y]. Implementing now."
GOOD: "Verified; my initial read was wrong because [reason]. Fixing."

AVOID: long apologies, defending why you pushed back, over-explaining.
```

State the correction factually and continue.

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST.
  2. Then implement in this order:
       a. Blocking issues (breakage, security)
       b. Simple fixes (typos, imports)
       c. Complex fixes (refactors, logic)
  3. Test each fix individually.
  4. Verify no regressions.
```

## Replying to Inline GitHub Comments

Reply inside the comment thread, not as a new top-level PR comment:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies -f body="..."
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Performative agreement | State the requirement, or just act |
| Blind implementation | Verify against the codebase first |
| Batch fixes, no testing | One at a time, test each |
| Assuming the reviewer is right | Check whether it breaks things |
| Avoiding pushback | Technical correctness over comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State the limitation, ask for direction |
