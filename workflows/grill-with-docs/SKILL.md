---
name: grill-with-docs
disable-model-invocation: true
description: Grill session that also maintains the project's glossary and ADRs as decisions crystallise (brownfield).
license: MIT
---

# Grill with docs (workflow)

Run a `grill-me` session, but carry the `domain-modeling` discipline alongside it: as decisions crystallise, sharpen the project's terminology and write it down inline.

`grill-me` (in `meta/`) owns the relentless interview; `domain-modeling` (in `software-development/design/`) owns the glossary/ADR discipline — `CONTEXT.md`, `docs/adr/`, and the file formats. The codebase-agnostic version is `grill-me` on its own.

## How it runs

- **Drive the interview with `grill-me`.** Walk each branch of the decision tree, recommending an answer per question and resolving each branch before moving on.
- **Throughout, apply `domain-modeling`** — read it for the term-challenging discipline, when to offer an ADR, lazy file creation, and the `CONTEXT.md` / ADR formats. Update `CONTEXT.md` the moment a term resolves; the point of this workflow over a plain `grill-me` is that the glossary and decisions get captured as you go.

If `domain-modeling` isn't installed, apply its discipline inline instead of skipping the doc-keeping: challenge terms that conflict with `CONTEXT.md`, sharpen fuzzy language to a canonical term, stress-test relationships with concrete edge-case scenarios, cross-reference claims against the code, and update `CONTEXT.md` the moment a term resolves. Offer an ADR only when the decision is hard to reverse, surprising without context, and a real trade-off.
