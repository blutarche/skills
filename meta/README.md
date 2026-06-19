# meta

Domain-agnostic skills — about the *process of working with the agent* or general working techniques,
not tied to any one domain. Sources for adapted skills are in [`../CREDITS.md`](../CREDITS.md).

| Skill | What it does |
|-------|--------------|
| [`research`](research/SKILL.md) | Answer a single question from sources fetched this session, with a citation behind every claim — never from memory. The evidence-discipline engine. |
| [`grill-me`](grill-me/SKILL.md) | Relentlessly interview you about a plan or design until shared understanding, resolving each branch of the decision tree. Codebase-agnostic; the brownfield counterpart is the [`grill-with-docs`](../workflows/grill-with-docs/SKILL.md) workflow. |
| [`council`](council/SKILL.md) | The cross-model judge *mechanism* — convene an outside model (a different family — e.g. Codex/GPT, Gemini, or a Cursor agent pinned to a non-Claude model) to cross-examine an artifact (decision, diff, document, research answer) and adjudicate disbelieve-it-back. Mechanism only: callers bring the artifact + their own in-family review. Composed by `vet` (code), `research-council` (research), and `plan` (decisions). |
| [`handoff`](handoff/SKILL.md) | Compact the current conversation into a handoff doc for a fresh agent to pick up. |
| [`skill-creator`](skill-creator/SKILL.md) | Create, edit, and measure skills — the draft → test → eval → iterate loop, plus a description optimizer for better triggering. Pairs with [`writing-great-skills`](writing-great-skills/SKILL.md) for the design theory. |
| [`writing-great-skills`](writing-great-skills/SKILL.md) | Reference for the *craft* of writing skills well — the vocabulary and principles behind predictability (invocation vs context load, the information hierarchy, leading words, the failure-mode catalog). User-invoked (`/writing-great-skills`); the design theory `skill-creator`'s loop edits toward. |
| [`project-skill-audit`](project-skill-audit/SKILL.md) | Audit a project's real recurring work (session history + memory + existing skills) and recommend skills to create or update — evidence-grounded, prefers updates over duplicates. Reports; hands building off to [`skill-creator`](skill-creator/SKILL.md). |
