---
name: slop-cleanup
description: Strip AI-generated slop from code, scoped to a diff by default. Use when cleaning up generated code or tidying a diff before review.
license: MIT
---

# Slop cleanup

Remove the tell-tale residue of AI-generated code while keeping behavior identical. The default scope is the current change set, not the whole repository.

## Scope

By default, work only on what changed:

```
git diff main...HEAD
```

If the change set has a different base branch or you were given an explicit file list, use that instead. Do not expand into surrounding code that the diff didn't touch unless explicitly asked — that includes adjacent hygiene like adding a `.gitignore` or reformatting untouched code. Flag those in the report instead of fixing them. One standing exception: adding or extending tests to lock current behavior (step 1 below) is always in scope, even when the test files aren't part of the diff.

## What slop looks like

Judge every candidate against the surrounding file and the conventions of *this* codebase — not against generic style rules. Something is slop when it deviates from how this area is normally written.

- **Defensive checks abnormal for this area.** Null guards, existence checks, and `try/catch` blocks added where the surrounding code trusts its inputs. Be especially suspicious on internal, already-validated codepaths: if every other caller in this layer passes data straight through, a new guard is usually slop, not safety.
- **Escape-hatch type casts.** Casts to `any` (or the language's equivalent) used to silence the type checker rather than model the real type. Replace with the correct type, or surface the type error honestly.
- **Style inconsistent with the file.** Naming, formatting, import ordering, or structural patterns that don't match the file they live in.

When in doubt about whether a guard or check is load-bearing, treat it as behavior and protect it with a test before deciding (see below).

## Comments: judge each one on its own

Comment slop is the most common residue and the easiest to misjudge, in both directions.

**Pick the right baseline.** A file that predates this diff sets its own baseline — some areas (parsers, crypto, gnarly math) legitimately carry dense explanation. But a file the AI wrote wholesale has no trustworthy local baseline — "consistent with the rest of the file" will argue for keeping all of it — so compare against how the *repo* comments equivalent code. Either way, put each comment through the value test below, individually; density is never itself a reason to delete.

**The value test:** a comment earns its place only if it tells the reader something the code cannot — an invariant or caller contract, a non-obvious *why*, an external system's quirk, or a plain actionable TODO. Everything else goes:

- narration of what the next line plainly does
- archaeological / change-narration comments ("previously…", "updated to…", "this used to live in…") — the diff is the change log, the file is not
- authoring-conversation leakage ("as requested…", "per the requirements…")
- essay blocks that re-describe the function in prose, and hedges ("should cover most cases")
- boilerplate `Args:`/`Returns:` docstrings that restate a trivial signature — unless the repo's docstring convention (public API docs, Sphinx/pydoc pipelines) requires them
- section banners

Two hard carve-outs before anything else: comments that machines read — lint and type-checker directives (`eslint-disable`, `noqa`, `ts-expect-error`), coverage pragmas, doc-generator markers, doctests — and license/copyright headers are never slop; deleting them changes builds, generated docs, or legal standing, not just prose.

For everything human-read, the value test protects the keepers too: ordinary tests almost never fail when a comment disappears, so you are the only gate. Before deleting a *why*-comment, ask whether a future reader would plausibly "simplify" the code into a bug without it (delete a `sorted()` call, "fix" a status-code check). If yes, it's load-bearing: keep it — trimming or rewording is fine, deleting is not.

## Workflow

Run the cleanup as a regression-safe sequence, not a single sweeping edit.

1. **Lock behavior first.** Identify what must not change. Run the existing tests for the touched area; add the narrowest regression tests needed to pin down behavior you're unsure about. If tests genuinely aren't feasible, write down an explicit verification plan before editing.

2. **Make a small plan.** List the specific smells you intend to remove, bounded to the diff. Order them safest-first (deletions before consolidations).

3. **Classify what you find.** Sort candidates into:
   - **Duplication** — repeated logic, copy-paste branches, redundant helpers.
   - **Dead code** — unused symbols, unreachable branches, stale flags, debug leftovers.
   - **Needless abstraction** — pass-through wrappers, speculative indirection, single-use helper layers.
   - **Boundary violations** — misplaced responsibilities, wrong-layer imports, hidden coupling or side effects. Report-only by default: untangling these usually moves behavior; name them in the report and fix only when explicitly asked.
   - **Missing tests** — behavior left unprotected, weak coverage, untested edge cases.

   On a **large, multi-file** diff the per-file *scan* is read-only, so you may **fan out one read-only sub-agent per file (non-overlapping scopes) to harvest candidates** — faster slop-spotting. But a per-file pass only sees **file-local** smells; the **cross-file** ones (duplication, boundary violations, missing tests) are invisible from inside one file, so follow the fan-out with **one global classification pass** (step 3 above) over the merged candidates before any edit. The editing below does **not** parallelize. (On a small diff, just scan it yourself — the coordination isn't worth it.)

4. **One pass per smell.** Make a single focused pass at a time, each addressing one category plus the slop patterns above. Prefer deletion over rewriting. Reuse existing utilities before adding anything, and add no new dependencies unless the user asks. Don't bundle unrelated refactors into the same edit. **Apply serially — never parallel writers** (concurrent edits to the same tree conflict, and each pass must clear the verify gate before the next).

5. **Verify after every pass.** Re-run the regression tests, plus the relevant lint, type check, and unit/integration checks for the area. If a gate fails, fix it or back the risky change out — never force it through.

6. **Report.** Close with a concise summary: which files changed, what you removed or simplified, what you deliberately kept and why, how behavior was verified, and any risks left open. If the caller asked for a specific deliverable (a summary file, a PR comment), produce that deliverable — the chat summary supplements it, never replaces it.

Related (advisory, not auto-invoked): surgical, read-before-write execution discipline prevents slop at write-time.
