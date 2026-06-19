---
name: slop-cleanup
description: Detect and remove characteristic AI-generated "slop" from code, scoped to a diff by default. Use when cleaning up AI-generated code, removing slop, or tidying a diff before review.
license: MIT
---

# Slop cleanup

Remove the tell-tale residue of AI-generated code while keeping behavior identical. The default scope is the current change set, not the whole repository.

## Scope

By default, work only on what changed:

```
git diff main...HEAD
```

If the change set has a different base branch or you were given an explicit file list, use that instead. Do not expand into surrounding code that the diff didn't touch unless explicitly asked.

## What slop looks like

Judge every candidate against the surrounding file and the conventions of *this* codebase — not against generic style rules. Something is slop when it deviates from how this area is normally written.

- **Comments that narrate the obvious.** Lines that restate what the code plainly does, or comment density that is out of step with the rest of the file. If neighboring functions carry no running commentary, new ones shouldn't either.
- **Defensive checks abnormal for this area.** Null guards, existence checks, and `try/catch` blocks added where the surrounding code trusts its inputs. Be especially suspicious on internal, already-validated codepaths: if every other caller in this layer passes data straight through, a new guard is usually slop, not safety.
- **Escape-hatch type casts.** Casts to `any` (or the language's equivalent) used to silence the type checker rather than model the real type. Replace with the correct type, or surface the type error honestly.
- **Style inconsistent with the file.** Naming, formatting, import ordering, or structural patterns that don't match the file they live in.

When in doubt about whether a guard or check is load-bearing, treat it as behavior and protect it with a test before deciding (see below).

## Workflow

Run the cleanup as a regression-safe sequence, not a single sweeping edit.

1. **Lock behavior first.** Identify what must not change. Run the existing tests for the touched area; add the narrowest regression tests needed to pin down behavior you're unsure about. If tests genuinely aren't feasible, write down an explicit verification plan before editing.

2. **Make a small plan.** List the specific smells you intend to remove, bounded to the diff. Order them safest-first (deletions before consolidations).

3. **Classify what you find.** Sort candidates into:
   - **Duplication** — repeated logic, copy-paste branches, redundant helpers.
   - **Dead code** — unused symbols, unreachable branches, stale flags, debug leftovers.
   - **Needless abstraction** — pass-through wrappers, speculative indirection, single-use helper layers.
   - **Boundary violations** — misplaced responsibilities, wrong-layer imports, hidden coupling or side effects.
   - **Missing tests** — behavior left unprotected, weak coverage, untested edge cases.

   On a **large, multi-file** diff the per-file *scan* is read-only, so you may **fan out one read-only sub-agent per file (non-overlapping scopes) to harvest candidates** — faster slop-spotting. But a per-file pass only sees **file-local** smells; the **cross-file** ones (duplication, boundary violations, missing tests) are invisible from inside one file, so follow the fan-out with **one global classification pass** (step 3 above) over the merged candidates before any edit. The editing below does **not** parallelize. (On a small diff, just scan it yourself — the coordination isn't worth it.)

4. **One pass per smell.** Make a single focused pass at a time, each addressing one category plus the slop patterns above. Prefer deletion over rewriting. Reuse existing utilities before adding anything. Don't bundle unrelated refactors into the same edit. **Apply serially — never parallel writers** (concurrent edits to the same tree conflict, and each pass must clear the verify gate before the next).

5. **Verify after every pass.** Re-run the regression tests, plus the relevant lint, type check, and unit/integration checks for the area. If a gate fails, fix it or back the risky change out — never force it through.

6. **Report.** Close with a concise summary: which files changed, what you removed or simplified, how behavior was verified, and any risks left open.

## Principles

- Preserve behavior unless a behavior change was explicitly requested.
- Deletion beats addition; the best cleanup removes code.
- No new dependencies unless the user asks for them.
- Keep diffs small and reversible.

Related (advisory, not auto-invoked): `karpathy-guidelines` prevents slop at write-time; this skill removes it after the fact.
