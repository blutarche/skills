# software-development

Atomic, single-purpose skills for building software with an agent. Most are grouped by **phase**
(design → … → verification); the **`stack/`** group is orthogonal — knowledge tied to the tech you
build on, not a phase. Each skill does one job and is unaware of the others — sequencing lives in
[`workflows/`](../workflows/README.md), not here. Sources for adapted skills are in
[`../CREDITS.md`](../CREDITS.md).

## design — shape intent into a design

| Skill | What it does |
|-------|--------------|
| [`brainstorming`](design/brainstorming/SKILL.md) | Turn a brief or vague idea into an approved design doc via one-question-at-a-time dialogue. |

## planning — turn a design/spec into an actionable plan

| Skill | What it does |
|-------|--------------|
| [`writing-plans`](planning/writing-plans/SKILL.md) | Expand a spec into a bite-sized, TDD-shaped implementation plan with exact files, code, and commands. |

## review — stress-test a plan, or clean up / evaluate produced code

| Skill | What it does |
|-------|--------------|
| [`scrutinize`](review/scrutinize/SKILL.md) | Outsider end-to-end review of a produced PR/diff/design doc: question intent → trace the real code path → verify the claim → severity-ordered findings + one verdict. Read-only (hands off edits to `simplify`/`slop-cleanup`). |
| [`grill-with-docs`](review/grill-with-docs/SKILL.md) | Grill a plan against your codebase's domain model + ADRs, sharpening terminology inline (brownfield). The codebase-agnostic counterpart is [`grill-me`](../meta/grill-me/SKILL.md) in `meta/`. |
| [`receiving-code-review`](review/receiving-code-review/SKILL.md) | Evaluate review feedback with rigor — verify each claim, push back when wrong, implement what holds up. |
| [`slop-cleanup`](review/slop-cleanup/SKILL.md) | Detect and remove characteristic AI-generated slop from a diff, behavior-preserving. |

## engineering — write, debug, and test code well

| Skill | What it does |
|-------|--------------|
| [`karpathy-guidelines`](engineering/karpathy-guidelines/SKILL.md) | Behavioral guidelines to reduce common LLM coding mistakes. |
| [`diagnose`](engineering/diagnose/SKILL.md) | A feedback-loop-first loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test. |
| [`post-mortem`](engineering/post-mortem/SKILL.md) | Write the canonical record of a fixed bug (or resolved incident) — root cause, mechanism, fix, validation, how it slipped through. Refuses until the fix is validated; blameless. Pairs with `diagnose`. |
| [`de-flaking-tests`](engineering/de-flaking-tests/SKILL.md) | Make flaky tests deterministic (condition-based waiting) and kill tests that pass for the wrong reason (mock theater, incomplete mocks). |
| [`git-commit`](engineering/git-commit/SKILL.md) | Turn a working tree into clean, atomic, bisect-safe commits — Conventional-Commit messages, no co-author trailer, push left to the user. |

## verification — prove work is actually done

| Skill | What it does |
|-------|--------------|
| [`verification-before-completion`](verification/verification-before-completion/SKILL.md) | Gate before any "done / fixed / passing" claim: run the real command, read the output + exit code, then claim. |

## stack — specific to the tech you work in

Orthogonal to the phase groups above: knowledge tied to the technologies you build on (LLM/AI,
frameworks, tooling) rather than a general SWE phase. Prefer **durable playbooks** (principles +
links to official docs) over version-pinned API references, which rot.

| Skill | What it does |
|-------|--------------|
| [`llm-cost-optimization`](stack/llm-cost-optimization/SKILL.md) | Cut token/$ cost of LLM pipelines: measure → cache → tier → trim → batch → cap → verify. |
