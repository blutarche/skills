---
name: grill-with-docs
description: A grilling session that also builds the project's domain model as it goes — challenging terminology against the glossary and recording decisions as ADRs the moment they crystallise. Use when you want to stress-test a plan against your project's documented language and decisions (brownfield).
license: MIT
---

# Grill with docs (workflow)

Run a `grill-me` session, but carry the `domain-modeling` discipline alongside it: as decisions crystallise, sharpen the project's terminology and write it down inline.

This is a **thin composer** — it owns no methodology of its own. `grill-me` (in `meta/`) owns the relentless interview; `domain-modeling` (in `software-development/design/`) owns the glossary/ADR discipline — `CONTEXT.md`, `docs/adr/`, and the file formats. This workflow just runs the two together; the codebase-agnostic version is `grill-me` on its own.

## How it runs

- **Drive the interview with `grill-me`.** Walk each branch of the decision tree, recommending an answer per question and resolving each branch before moving on.
- **Throughout, apply `domain-modeling`.** Challenge terms that conflict with `CONTEXT.md`, sharpen fuzzy language to a canonical term, stress-test relationships with concrete edge-case scenarios, cross-reference claims against the code, and update `CONTEXT.md` the moment a term resolves. Offer an ADR only when the decision is hard to reverse, surprising without context, and a real trade-off.

Create docs lazily — only when there's something to write. See `domain-modeling` for the file structure and the `CONTEXT.md` / ADR formats.

## Composed skills are soft references

If `domain-modeling` isn't installed, apply its discipline inline from the description above rather than skipping the doc-keeping — the point of this workflow over a plain `grill-me` is that the glossary and decisions get captured as you go.
