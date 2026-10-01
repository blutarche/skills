# software-development

Atomic, single-purpose skills for building software with an agent, grouped by **phase**
(design → planning → review → engineering, plus frontend, verification, and languages). Each skill does one job and is unaware of the others —
sequencing lives in [`workflows/`](../workflows/README.md), not here. Sources for adapted skills are in
[`../CREDITS.md`](../CREDITS.md).

## design — shape intent into a design

| Skill | What it does |
|-------|--------------|
| [`brainstorming`](design/brainstorming/SKILL.md) | Turn a brief or vague idea into an approved design doc via one-question-at-a-time dialogue. |
| [`domain-modeling`](design/domain-modeling/SKILL.md) | Actively build and sharpen the project's domain model — challenge terms against the glossary, sharpen fuzzy language, and write `CONTEXT.md` + ADRs inline as decisions crystallise. Composed by the [`grill-with-docs`](../workflows/grill-with-docs/SKILL.md) workflow. |

## planning — turn a design/spec into an actionable plan

| Skill | What it does |
|-------|--------------|
| [`writing-plans`](planning/writing-plans/SKILL.md) | Expand a spec into a bite-sized, TDD-shaped implementation plan with exact files, code, and commands. |

## review — stress-test a plan, or clean up / evaluate produced code

| Skill | What it does |
|-------|--------------|
| [`walkthrough`](review/walkthrough/SKILL.md) | Build a shareable browser walkthrough with every PR Lens architecture/data-flow view, conceptual diff chapters, and git-validated line numbers. Explains, never grades. |
| [`pr-lens`](review/pr-lens/SKILL.md) | Draw a code change or codebase as a validated, animated architecture or data-flow diagram, kept local by default. |
| [`scrutinize`](review/scrutinize/SKILL.md) | Outsider end-to-end review of a produced PR/diff/design doc: question intent → trace the real code path → verify the claim → severity-ordered findings + one verdict. Read-only (hands off edits to `simplify`/`slop-cleanup`). |
| [`receiving-code-review`](review/receiving-code-review/SKILL.md) | Evaluate review feedback with rigor — verify each claim, push back when wrong, implement what holds up. |
| [`slop-cleanup`](review/slop-cleanup/SKILL.md) | Detect and remove characteristic AI-generated slop from a diff, behavior-preserving. |

## engineering — write, debug, and test code well

| Skill | What it does |
|-------|--------------|
| [`diagnose`](engineering/diagnose/SKILL.md) | A feedback-loop-first loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix → regression-test. Also covers flaky tests. |
| [`post-mortem`](engineering/post-mortem/SKILL.md) | Write the canonical record of a fixed bug (or resolved incident) — root cause, mechanism, fix, validation, how it slipped through. Refuses until the fix is validated; blameless. Pairs with `diagnose`. |
| [`git-commit`](engineering/git-commit/SKILL.md) | Turn a working tree into clean, atomic, bisect-safe commits — Conventional-Commit messages, no co-author trailer, push left to the user. |
| [`git-worktree`](engineering/git-worktree/SKILL.md) | Create/enter an isolated feature worktree and bootstrap-or-surface its environment (setup), then remove/prune it (teardown). Use when starting or wrapping up isolated agentic work. |
| [`delegate-coding`](engineering/delegate-coding/SKILL.md) | When the plan is clear enough for a cheaper agent to execute, delegate the coding to a headless executor CLI — `cursor-agent`, `codex`, or a cheaper `claude` — while your expensive "brain" model only plans, verifies, and owns the merge. Executor self-loops on env-independent checks in its worktree; you own env-dependent checks post-merge; bounded retries, then you finish. Per-tool invocation in `references/`. |

## frontend — UI motion and feel

| Skill | What it does |
|-------|--------------|
| [`animate`](frontend/animate/SKILL.md) | Build a web animation in decision order: should it animate, purpose, tool, properties, curve/duration, interruption, reduced motion. |
| [`review-animations`](frontend/review-animations/SKILL.md) | Strict review of motion code against Emil Kowalski's craft bar. Explicit invocation only. |
| [`mobile-native`](frontend/mobile-native/SKILL.md) | Fixes that make a web app feel native on a phone: sticky hover, 100vh, input zoom, safe areas, tap delay. |
| [`prototype`](frontend/prototype/SKILL.md) | Build several genuinely different variants of a UI piece behind a live picker. Explicit invocation only. |

## verification — prove the running app works the way a user sees it

| Skill | What it does |
|-------|--------------|
| [`create-verification-skill`](verification/create-verification-skill/SKILL.md) | Generate a project-local `verify-<app>` skill (launch, doctor, drive, evidence, cleanup) plus a per-feature map, then prove it by running it once. Manual `/command` only. |
| [`maintain-verification-skill`](verification/maintain-verification-skill/SKILL.md) | Audit a `verify-<app>` skill: per-feature source readers in parallel, one live pass driving every feature, one local commit of proven map/harness fixes. Manual `/command` only. |

## languages — idiomatic code per language

| Skill | What it does |
|-------|--------------|
| [`write-swift`](languages/write-swift/SKILL.md) | Write modern Swift: value types, Swift 6 concurrency and Sendable, generics (`some` vs `any`), API design, ARC, Swift Testing. |
