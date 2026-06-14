---
name: verification-before-completion
description: Before claiming work is done, fixed, or passing, run the actual verification command and confirm its output. Use when about to claim completion, commit, or open a PR, or whenever tempted to say "should work / probably / seems fine."
license: MIT
---

# Verification Before Completion

Claim results from evidence, not expectation. A change that is not verified is not done.

## The Iron Law

```
NO COMPLETION CLAIM WITHOUT FRESH VERIFICATION EVIDENCE
```

If you have not run the verification command in the current step, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim? Assume one exists — tests, build, lint, or running the original symptom. Direct inspection is the evidence ONLY when the change is genuinely non-executable (prose, docs, a config value with no test); "I couldn't think of a command" does not qualify.
2. RUN:      Execute the FULL command, fresh and complete. (For the non-executable exception only: re-read the actual changed content — not your memory of it.)
3. READ:     Read the full output / the actual content. For a command, check the exit code and count failures.
4. VERIFY:   Does the output confirm the claim?
                - If NO:  State the actual status, with evidence.
                - If YES: State the claim, with evidence.
5. ONLY THEN: Make the claim.
```

Skipping any step is guessing, not verifying.

## Common Failures

| Claim | Requires | Not sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | A previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs "look good" |
| Bug fixed | Test the original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Delegated work done | Diff shows the actual changes | A "success" report from the worker |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags — Stop

- Using "should", "probably", "seems to", "looks fine".
- Expressing satisfaction before verifying ("Great!", "Perfect!", "Done!").
- About to commit, push, or open a PR without running verification.
- Trusting a delegated worker's success report without checking the diff.
- Relying on a partial run to claim the whole thing passes.
- Thinking "just this once" or rushing to be finished.
- Any wording that implies success without having run verification.

## Rationalization Check

| Excuse | Reality |
|--------|---------|
| "Should work now" | Run the verification. |
| "I'm confident" | Confidence is not evidence. |
| "Just this once" | No exceptions. |
| "Linter passed" | Linter does not check compilation. |
| "The worker said success" | Verify independently. |
| "Partial check is enough" | Partial proves nothing. |
| "Different words, so the rule doesn't apply" | Spirit over letter. |

## Patterns

**Tests**
```
DO:  Run the test command -> see 34/34 pass -> "All tests pass."
NOT: "Should pass now." / "Looks correct."
```

**Regression test (red-green)**
```
DO:  Write test -> run (pass) -> revert the fix -> run (MUST fail).
     If it still passes, the test does not exercise the fix — rewrite it.
     Then restore the fix -> run (pass).
NOT: "I wrote a regression test" without the red-green cycle.
```

**Build**
```
DO:  Run the build -> see exit 0 -> "Build passes."
NOT: "Linter passed" (the linter does not compile).
```

**Requirements**
```
DO:  Re-read the spec -> make a checklist -> verify each item
     -> report gaps or completion.
NOT: "Tests pass, so it's complete."
```

**Delegated work**
```
DO:  Worker reports success -> inspect the diff -> verify the changes
     -> report the actual state.
NOT: Trust the report.
```

## Bottom Line

Run the command. Read the output. Then claim the result.
