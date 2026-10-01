---
name: receiving-code-review
description: Verify each review claim against the code, push back with reasons where wrong, implement what is valid. Use when acting on code-review feedback.
license: MIT
---

# Receiving Code Review

A suggestion is a claim to be checked, not an order to obey. Read all the feedback before reacting, restate each item in your own words (or ask if unclear), verify each claim against the actual codebase, and push back with technical reasoning where it is wrong.

Do not open with validation phrases ("You're absolutely right", "Great point") or with "Let me implement that now" before you have verified the claim. Restate the requirement, ask a question, push back, or just do the work. When feedback is correct, acknowledge it factually ("Fixed — [what changed, where]") and move on. When your own pushback was wrong, say so the same way ("You were right — I checked [X] and it does [Y]") without long apologies or defending the pushback.

## Handling Unclear Feedback

If any item is unclear, stop: do not implement anything yet, and ask for clarification on the unclear items. Items may be related, and partial understanding produces wrong implementation.

## Verifying a Suggestion

Before implementing any external suggestion, check:

1. Is it technically correct for this codebase?
2. Would it break existing functionality?
3. Is there a reason the current implementation is the way it is?
4. Does it hold across all supported platforms/versions?
5. Does the reviewer have the full context?

If any check fails, push back with technical reasoning. If you cannot easily verify a claim, say so: "I can't verify this without [X]. Should I investigate, ask, or proceed?"

If it conflicts with a prior decision by the project owner, surface the conflict before acting.

**Verifying many items — fan out the independent ones.** Most items verify **independently** — a read-only check against the codebase — so on a multi-item review don't grind them one by one. But **group the coupled items first**: where one comment invalidates another, shares its code path, or hinges on which fix you'll pick, those aren't independent — keep each such group together and verify it as a unit. Then dispatch **one read-only sub-agent per independent item or group** if the host supports it — each runs the five checks above on its item and reports back, never editing — collect the verdicts, and **reconcile the coupled ones yourself** before responding. Only verification parallelizes; responding and implementing stay **serial** on the main thread (one fix at a time, tested each — see Implementation Order), and clarifying unclear items still comes first. If you can't fan out, sweep them yourself in one pass and say the verification was single-threaded.

## YAGNI Check for "Do It Properly" Requests

If a reviewer suggests "implementing this properly", grep the codebase for actual usage. If unused: "Nothing calls this. Remove it (YAGNI)?" If used, implement it properly. Do not add capability that nothing needs, even when asked to make something "professional".

## Implementation Order

For multi-item feedback, once everything unclear is clarified, implement in this order:

1. Blocking issues (breakage, security)
2. Simple fixes (typos, imports)
3. Complex fixes (refactors, logic)

Test each fix individually, then verify no regressions.

## Replying to Inline GitHub Comments

Reply inside the comment thread, not as a new top-level PR comment:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies -f body="..."
```
