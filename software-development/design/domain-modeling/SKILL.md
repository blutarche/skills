---
name: domain-modeling
description: Build or sharpen a project's domain model — glossary, ubiquitous language, ADRs. Use when pinning down terminology or recording an architectural decision.
license: MIT
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline — challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. Use it when you're changing the model, not merely reading `CONTEXT.md` for vocabulary.

## File structure

Most repos have a single context: one `CONTEXT.md` and a `docs/adr/` at the root. If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts: each lives in its own directory with its own `CONTEXT.md` and `docs/adr/` (context-specific decisions), while the root `docs/adr/` holds system-wide decisions. Read [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md) ("Single vs multi-context repos") for the map format and how to tell which context applies.

Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three criteria in [ADR-FORMAT.md](./ADR-FORMAT.md) ("When to offer an ADR") are true; if any is missing, skip the ADR. Read that file before offering — it holds the criteria, what qualifies, and the format.
