# meta

Domain-agnostic skills — about the *process of working with the agent* or general working techniques,
not tied to any one domain. Sources for adapted skills are in [`../CREDITS.md`](../CREDITS.md).

| Skill | What it does |
|-------|--------------|
| [`research`](research/SKILL.md) | Answer a single question from sources fetched this session, with a citation behind every claim — never from memory. The evidence-discipline engine. |
| [`grill-me`](grill-me/SKILL.md) | Relentlessly interview you about a plan or design until shared understanding, resolving each branch of the decision tree. Codebase-agnostic; the brownfield counterpart is [`grill-with-docs`](../software-development/review/grill-with-docs/SKILL.md). |
| [`council`](council/SKILL.md) | The cross-model judge *mechanism* — convene an outside model (Codex, a different family) to cross-examine an artifact (decision, diff, document, research answer) and adjudicate disbelieve-it-back. Mechanism only: callers bring the artifact + their own in-family review. Composed by `vet` (code), `research-council` (research), and `plan` (decisions). |
| [`handoff`](handoff/SKILL.md) | Compact the current conversation into a handoff doc for a fresh agent to pick up. |
| [`skill-creator`](skill-creator/SKILL.md) | Create, edit, and measure skills — the draft → test → eval → iterate loop, plus a description optimizer for better triggering. |
